"""Arquivamento (fatia F4) — e os caminhos de leitura que ele destrava.

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

Por que o teste central não é "arquivar grava a linha"
------------------------------------------------------
Gravar a linha é a parte fácil. O que esta fatia conserta é que **o lado da
leitura já estava inteiro e em produção, sem nada do outro lado**: seis lugares
de `dashboard.py` contam arquivados, o portal do cidadão diz "concluído", e
`PrazoInfo` deriva `data_conclusao` — todos por
`Movimentacao.id_arquivamento IS NOT NULL`, que nenhum caminho preenchia.

Então os testes que valem são os que provam que aqueles leitores **mudam de
resposta**. Um teste que só conferisse a linha nova passaria mesmo se o formato
gravado não fosse o que eles esperam — que é exatamente o modo de falha
perigoso aqui, já que não há tipo nenhum ligando as duas pontas.

`test_pr5b_prazos.py::_arquivar` simulava isso com SQL cru porque não havia
service. A existência daquele helper era a pista de que faltava algo.

O que estes testes NÃO cobrem
-----------------------------
**O bloqueio do workflow strict.** `arquivar` chama `validar_acao_strict(acao=
"arquivar")`, que barra quando o estado atual do workflow não é final. Os
processos daqui não têm instância de workflow, então caem no ramo "sem
instância → libera" e o bloqueio nunca é exercitado. Cobri-lo exige montar
`WorkflowDefinition` + `WorkflowInstance` em estado não-final, que é bateria de
outro arquivo. Fica registrado para não passar por coberto.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Movimentacao,
    Processo,
    TipoProcesso,
    Usuario,
)
from app.models.processo import Acao
from app.schemas.processo import ArquivarRequest
from app.services.acoes_processo import AcaoError, arquivar
from app.services.processos import get_processo_detail
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Tenant com um processo aberto há 5 dias e um operador comum."""
    slug = f"f4-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref F4", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )

    async with _sm(admin_engine)() as s:
        unidade = (
            await s.execute(
                text(
                    "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        id_tipo_manif = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        usuario_id = (
            await s.execute(
                select(Usuario.id).where(Usuario.tenant_id == tenant.id).limit(1)
            )
        ).scalar_one()

        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral", exige_processo_pai=False,
            ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manif, nome="Maria",
            ativo=True, excluido=False,
        )
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(
            tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        abertura = datetime.now() - timedelta(days=5)
        processo = Processo(
            tenant_id=tenant.id,
            id_assunto=assunto.id,
            virtual=True,
            data_hora_abertura=abertura,
            numero_processo=f"{slug}-0001",
            id_unidade_proprietaria=unidade,
            id_manifestante=manif.id,
            id_local_atual=unidade,
            nivel_sigilo="ostensivo",
            # Prazo generoso: o processo é arquivado 5 dias após a abertura, e
            # o teste do prazo precisa cair em `concluido_no_prazo`.
            prazo_servico_dias_snapshot=30,
            ativo=True,
            excluido=False,
        )
        s.add(processo)
        await s.flush()

        acao_abertura = (
            await s.execute(select(Acao).where(Acao.flag == "ABERTURA"))
        ).scalars().first()
        s.add(
            Movimentacao(
                tenant_id=tenant.id, id_processo=processo.id,
                id_unidade_responsavel=unidade, id_acao=acao_abertura.id,
                id_usuario=usuario_id, data_hora_movimentacao=abertura,
                ativo=True, excluido=False,
            )
        )
        await s.commit()
        dados = {
            "tenant": tenant, "processo_id": processo.id,
            "unidade": unidade, "usuario_id": usuario_id,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL, id_usuario_responsavel=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.arquivamento WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": dados["tenant"].id})
        await s.commit()


async def _arquiva(engine, cen, **kw):
    async with _sm(engine)() as s:
        return await arquivar(
            s,
            cen["processo_id"],
            ArquivarRequest(motivo=kw.pop("motivo", "Demanda atendida"), **kw),
            tenant_id=cen["tenant"].id,
            usuario_id=cen["usuario_id"],
            is_super_usuario=True,
        )


# --------------------------------------------------------------------------
# O catálogo, que faltava
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_garante_acao_e_status(admin_engine):
    """Sem estes dois o arquivamento estoura por FK.

    Nenhum dos dois era garantido pelo `seed_bootstrap` antes desta fatia —
    `test_pr5b_prazos.py` criava a ação à mão, e o status só existia no banco
    de dev por acidente do legado.
    """
    async with _sm(admin_engine)() as s:
        acao = (
            await s.execute(
                text(
                    "SELECT 1 FROM protocolos.acao WHERE flag='ARQUIVAMENTO' "
                    "AND ativo=true AND excluido=false LIMIT 1"
                )
            )
        ).first()
        status = (
            await s.execute(
                text(
                    "SELECT 1 FROM protocolos.status_arquivamento "
                    "WHERE ativo=true AND excluido=false LIMIT 1"
                )
            )
        ).first()
    assert acao is not None, "ação ARQUIVAMENTO ausente — rode o seed_bootstrap"
    assert status is not None, "status_arquivamento vazio — rode o seed_bootstrap"


# --------------------------------------------------------------------------
# O formato gravado — e os leitores que dependem dele
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grava_no_formato_que_os_leitores_esperam(admin_engine, cen):
    """`Movimentacao` com `id_acao=ARQUIVAMENTO` E `id_arquivamento` preenchido.

    Os seis leitores do dashboard filtram por `id_arquivamento IS NOT NULL` e
    NÃO olham a ação. Gravar só a ação (ou só o vínculo) deixaria metade deles
    cega, e nenhum tipo do Python pegaria isso.
    """
    arq = await _arquiva(admin_engine, cen, motivo="Objeto concluído", local="Caixa 12")

    async with _sm(admin_engine)() as s:
        mov = (
            await s.execute(
                select(Movimentacao).where(
                    Movimentacao.id_processo == cen["processo_id"],
                    Movimentacao.id_arquivamento.is_not(None),
                )
            )
        ).scalar_one()
        acao = (
            await s.execute(select(Acao).where(Acao.id == mov.id_acao))
        ).scalar_one()

    assert mov.id_arquivamento == arq.id
    assert acao.flag == "ARQUIVAMENTO"
    assert arq.motivo == "Objeto concluído"
    assert arq.local == "Caixa 12"
    # Vínculo de volta: a tabela legada tem `movimentacao_id` e há relatório
    # que parte do arquivamento para achar a movimentação.
    assert arq.movimentacao_id == mov.id


@pytest.mark.asyncio
async def test_prazo_passa_a_ter_conclusao(admin_engine, cen):
    """`concluido_no_prazo` era INALCANÇÁVEL antes desta fatia.

    `PrazoInfo.concluido_em` vem de `data_conclusao`, que
    `services/processos.py` deriva da movimentação de arquivamento. Sem
    ninguém arquivando, `concluido_em` era sempre `None` e os dois status
    `concluido_*` não podiam acontecer em produção.
    """
    async with _sm(admin_engine)() as s:
        antes = await get_processo_detail(
            s, cen["processo_id"], tenant_id=cen["tenant"].id
        )
    assert antes is not None
    assert antes.prazo.concluido_em is None
    assert antes.prazo.status == "dentro_do_prazo"

    await _arquiva(admin_engine, cen)

    async with _sm(admin_engine)() as s:
        depois = await get_processo_detail(
            s, cen["processo_id"], tenant_id=cen["tenant"].id
        )
    assert depois is not None
    assert depois.prazo.concluido_em is not None
    assert depois.prazo.status == "concluido_no_prazo"


@pytest.mark.asyncio
async def test_permanencia_fecha_o_processo(admin_engine, cen):
    """F1 só consegue dizer `em_curso=false` depois que a F4 existe.

    O nó de arquivamento tem `status_movimentacao='final'`, que é o que
    `services/permanencia.py` usa para encerrar a contagem. Antes desta fatia
    nenhum processo chegava lá.
    """
    async with _sm(admin_engine)() as s:
        antes = await get_processo_detail(
            s, cen["processo_id"], tenant_id=cen["tenant"].id
        )
    assert antes is not None and antes.permanencia.em_curso is True

    await _arquiva(admin_engine, cen)

    async with _sm(admin_engine)() as s:
        depois = await get_processo_detail(
            s, cen["processo_id"], tenant_id=cen["tenant"].id
        )
    assert depois is not None
    assert depois.permanencia.em_curso is False

    arqui = next(
        m for m in depois.movimentacoes if m.acao_flag == "ARQUIVAMENTO"
    )
    # Parado após o arquivamento não acumula permanência.
    assert arqui.permanencia.natureza == "encerrado"
    assert arqui.permanencia.segundos == 0


@pytest.mark.asyncio
async def test_dashboard_passa_a_contar_arquivados(admin_engine, cen):
    """O KPI estava zerado POR CONSTRUÇÃO, não por falta de dado.

    Consulta escrita com o mesmo critério do `dashboard.py` em vez de chamar o
    serviço: o dashboard agrega por janela e por filtros de gestor, e montar
    tudo isso aqui testaria o agregador, não a fatia. O que importa provar é
    que a linha gravada CASA com o critério.
    """
    criterio = text(
        "SELECT count(*) FROM protocolos.movimentacao m "
        "JOIN protocolos.processo p ON p.id = m.id_processo "
        "WHERE m.tenant_id = :t AND m.id_arquivamento IS NOT NULL "
        "  AND p.excluido = false"
    )
    async with _sm(admin_engine)() as s:
        antes = (await s.execute(criterio, {"t": cen["tenant"].id})).scalar_one()
    assert antes == 0

    await _arquiva(admin_engine, cen)

    async with _sm(admin_engine)() as s:
        depois = (await s.execute(criterio, {"t": cen["tenant"].id})).scalar_one()
    assert depois == 1


@pytest.mark.asyncio
async def test_observacao_vira_despacho_na_linha_do_tempo(admin_engine, cen):
    """Texto livre reusa `Despacho`, que a timeline já renderiza."""
    await _arquiva(admin_engine, cen, observacao="Arquivado conforme parecer 12/2026")

    async with _sm(admin_engine)() as s:
        d = await get_processo_detail(
            s, cen["processo_id"], tenant_id=cen["tenant"].id
        )
    assert d is not None
    arqui = next(m for m in d.movimentacoes if m.acao_flag == "ARQUIVAMENTO")
    assert arqui.despacho is not None
    assert "parecer 12/2026" in arqui.despacho.despacho


@pytest.mark.asyncio
async def test_arquivar_duas_vezes_e_recusado(admin_engine, cen):
    """Não é idempotente de propósito: dois eventos de conclusão fariam o
    "tempo médio de conclusão" contar o mesmo processo duas vezes."""
    await _arquiva(admin_engine, cen)
    with pytest.raises(AcaoError, match="já está arquivado"):
        await _arquiva(admin_engine, cen)


@pytest.mark.asyncio
async def test_nao_mexe_em_processo_ativo(admin_engine, cen):
    """`processo.ativo` fica como estava, e isso é decisão registrada.

    Nada no app escreve esse campo, e o filtro `apenas_ativos` da lista o
    consulta. Acoplá-lo ao arquivamento mudaria em silêncio o que as listas
    existentes mostram, apoiado numa suposição sobre o que `ativo` significa.
    Se um dia a decisão for acoplar, é aqui que este teste tem de mudar — de
    propósito.
    """
    await _arquiva(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        p = (
            await s.execute(
                select(Processo).where(Processo.id == cen["processo_id"])
            )
        ).scalar_one()
    assert p.ativo is True


@pytest.mark.asyncio
async def test_motivo_e_obrigatorio():
    """Ato que encerra o processo tem de dizer por quê.

    Mesmo princípio de `apensamento.motivo` NOT NULL: campo opcional vira
    campo vazio, e o histórico deixa de responder "por que isto foi encerrado".
    """
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        ArquivarRequest(motivo="")
    with pytest.raises(pydantic.ValidationError):
        ArquivarRequest()  # type: ignore[call-arg]


# --------------------------------------------------------------------------
# A borda HTTP
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_arquiva_e_devolve_o_detalhe(admin_engine, cen):
    t = cen["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(
                    select(Usuario).where(Usuario.id == cen["usuario_id"])
                )
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            f"/api/v2/processos/{cen['processo_id']}/arquivar",
            json={"motivo": "Demanda atendida", "permanente": True},
        )
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["prazo"]["concluido_em"] is not None
        assert corpo["permanencia"]["em_curso"] is False
        assert any(
            m["acao_flag"] == "ARQUIVAMENTO" for m in corpo["movimentacoes"]
        )

        # Segunda vez: 400 com a razão, não 500.
        r2 = await client.post(
            f"/api/v2/processos/{cen['processo_id']}/arquivar",
            json={"motivo": "Demanda atendida"},
        )
        assert r2.status_code == 400, r2.text
        assert "arquivado" in r2.json()["detail"]

        # Motivo vazio é 422 na borda, antes de chegar ao service.
        r3 = await client.post(
            f"/api/v2/processos/{cen['processo_id']}/arquivar", json={"motivo": ""}
        )
        assert r3.status_code == 422, r3.text

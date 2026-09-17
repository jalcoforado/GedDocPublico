"""Permanência na costura: fluxo real de tramitação → detalhe → HTTP.

Por que este arquivo existe ao lado de `test_permanencia.py`
------------------------------------------------------------
Aquele testa o cálculo, que é função pura e onde mora a lógica. Este testa a
**costura**, e são defeitos de classes diferentes:

- o cálculo pode estar certo e o service alimentá-lo com o campo errado;
- o service pode estar certo e o `response_model` não expor o bloco;
- a timeline vem em ordem DECRESCENTE, e parear por índice em vez de por id
  entregaria números plausíveis nas linhas trocadas — verde no cálculo,
  errado na tela.

Nenhum deles aparece num teste que constrói `No` à mão.

Exercita `encaminhar` e `receber` de verdade, e não carimbos inventados: é o
que garante que a hipótese central da fatia continua valendo — a de que
receber cria movimentação própria com o mesmo instante do recebimento, e que
por isso espera e análise são nós VIZINHOS, não pedaços de um nó. Se alguém
mudar `acoes_processo` para não criar a movimentação de `RECEBIMENTO`, é aqui
que aparece.

Efeito colateral deliberado: até esta fatia, `encaminhar`/`receber` não tinham
nenhum teste. Continuam sem um arquivo próprio — consertar isso é maior que F1
e não foi pedido —, mas pelo menos o caminho feliz passa a ser exercitado.
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
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Movimentacao,
    Prioridade,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from app.models.processo import Acao
from app.schemas.processo import EncaminharRequest
from app.services.acoes_processo import encaminhar, receber
from app.services.processos import get_processo_detail
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def cenario(admin_engine):
    """Tenant com um processo aberto, pronto para ser encaminhado.

    A abertura é carimbada 3 h atrás para que as permanências tenham valor
    mensurável — com tudo "agora" todos os trechos dariam zero e os testes
    passariam sem distinguir nada.
    """
    slug = _slug("perm-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref Permanência",
            admin_email=f"{slug}@t.local",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )

    async with _sm(admin_engine)() as s:
        origem = (
            await s.execute(
                text(
                    "SELECT id FROM utils.unidade_trabalho "
                    "WHERE tenant_id=:t ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        tipo_unidade = (
            await s.execute(
                text(
                    "SELECT id_tipo_unidade_trabalho FROM utils.unidade_trabalho "
                    "WHERE id=:u"
                ),
                {"u": origem},
            )
        ).scalar_one()
        id_tipo_manifestante = (
            await s.execute(
                text(
                    "SELECT id FROM protocolos.tipo_manifestante "
                    "WHERE tenant_id=:t ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()
        usuario_id = (
            await s.execute(
                select(Usuario.id).where(Usuario.tenant_id == tenant.id).limit(1)
            )
        ).scalar_one()

        # `UnidadeTrabalho` não tem `ativo` — só `excluido`. É tabela legada
        # (`utils.unidade_trabalho`) e não segue a convenção dos modelos nossos.
        destino = UnidadeTrabalho(
            tenant_id=tenant.id,
            unidade_trabalho="Setor de Análise",
            id_tipo_unidade_trabalho=tipo_unidade,
            excluido=False,
        )
        tp = TipoProcesso(
            tenant_id=tenant.id,
            tipo_processo="Geral",
            exige_processo_pai=False,
            ativo=True,
            excluido=False,
        )
        # `Prioridade` é catálogo GLOBAL (como `Acao`): sem `tenant_id`. Por
        # isso a limpeza lá embaixo a apaga pelo id, e não pelo tenant — apagar
        # `protocolos.prioridade WHERE tenant_id=...` nem compilaria, e apagar
        # tudo levaria junto as prioridades de outros testes rodando ao lado.
        prio = Prioridade(
            prioridade="Normal", fator=1, cor="#999999", ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id,
            id_tipo_manifestante=id_tipo_manifestante,
            nome="Maria",
            ativo=True,
            excluido=False,
        )
        s.add_all([destino, tp, prio, manif])
        await s.flush()

        assunto = Assunto(
            tenant_id=tenant.id,
            assunto="Solicitação",
            id_tipo_processo=tp.id,
            exige_processo_pai=False,
            ativo=True,
            excluido=False,
        )
        s.add(assunto)
        await s.flush()

        abertura = datetime.now() - timedelta(hours=3)
        processo = Processo(
            tenant_id=tenant.id,
            id_assunto=assunto.id,
            virtual=True,
            data_hora_abertura=abertura,
            numero_processo=f"{slug}-0001",
            id_unidade_proprietaria=origem,
            id_manifestante=manif.id,
            id_local_atual=origem,
            nivel_sigilo="ostensivo",
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
                tenant_id=tenant.id,
                id_processo=processo.id,
                id_unidade_responsavel=origem,
                id_acao=acao_abertura.id,
                id_usuario=usuario_id,
                data_hora_movimentacao=abertura,
                ativo=True,
                excluido=False,
            )
        )
        await s.commit()

        dados = {
            "tenant": tenant,
            "processo_id": processo.id,
            "origem": origem,
            "destino": destino.id,
            "prioridade": prio.id,
            "usuario_id": usuario_id,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            # `processo.id_ultima_movimentacao` referencia `movimentacao`
            # (fk_pro_id_ultima_movimentacao), então tem de ser anulado ANTES —
            # senão o DELETE das movimentações viola a FK. Vale o mesmo para
            # `id_local_atual`, por simetria.
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.encaminhamento WHERE tenant_id=:t",
            "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
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
        # Por último: `encaminhamento.id_prioridade` referencia esta linha, e o
        # catálogo é global, então ela não sai junto com o tenant.
        await s.execute(
            text("DELETE FROM protocolos.prioridade WHERE id=:p"),
            {"p": dados["prioridade"]},
        )
        await s.commit()


async def _recua(engine, tenant_id: int, flag: str, horas: float) -> None:
    """Recua o carimbo da movimentação mais recente da ação `flag`.

    Os serviços carimbam com `datetime.now()`, então sem isto todos os trechos
    dariam zero segundo e o teste não distinguiria espera de análise.
    """
    async with _sm(engine)() as s:
        await s.execute(
            text(
                "UPDATE protocolos.movimentacao SET data_hora_movimentacao = "
                "  data_hora_movimentacao - make_interval(secs => :seg) "
                "WHERE tenant_id = :t AND id = ("
                "  SELECT m.id FROM protocolos.movimentacao m "
                "  JOIN protocolos.acao a ON a.id = m.id_acao "
                "  WHERE m.tenant_id = :t AND a.flag = :f "
                "  ORDER BY m.id DESC LIMIT 1)"
            ),
            {"t": tenant_id, "f": flag, "seg": horas * 3600},
        )
        await s.commit()


@pytest.mark.asyncio
async def test_encaminhar_e_receber_viram_espera_e_analise(admin_engine, cenario):
    """O caminho completo: abertura → encaminhamento → recebimento.

    Linha do tempo montada: abertura em T-3h, encaminhamento em T-2h,
    recebimento agora. Logo 1 h de análise com quem abriu, 2 h de espera na
    fila do destino, e o nó do recebimento aberto.
    """
    t = cenario["tenant"]

    async with _sm(admin_engine)() as s:
        await encaminhar(
            s,
            cenario["processo_id"],
            EncaminharRequest(
                id_unidade_destino=cenario["destino"],
                id_prioridade=cenario["prioridade"],
                quantidade_folhas=0,
            ),
            tenant_id=t.id,
            usuario_id=cenario["usuario_id"],
            is_super_usuario=True,
        )
        await s.commit()

    # O encaminhamento acabou de ser carimbado com `now()`; recua 2 h para que
    # a espera tenha duração.
    await _recua(admin_engine, t.id, "ENCAMINHAMENTO", horas=2)

    async with _sm(admin_engine)() as s:
        await receber(
            s,
            cenario["processo_id"],
            tenant_id=t.id,
            usuario_id=cenario["usuario_id"],
            is_super_usuario=True,
        )
        await s.commit()

    async with _sm(admin_engine)() as s:
        detalhe = await get_processo_detail(s, cenario["processo_id"], tenant_id=t.id)

    assert detalhe is not None
    por_flag = {m.acao_flag: m for m in detalhe.movimentacoes}
    assert set(por_flag) == {"ABERTURA", "ENCAMINHAMENTO", "RECEBIMENTO"}

    # A hipótese central da fatia, verificada contra o fluxo real.
    assert por_flag["ENCAMINHAMENTO"].permanencia.natureza == "espera"
    assert por_flag["RECEBIMENTO"].permanencia.natureza == "analise"
    assert por_flag["ABERTURA"].permanencia.natureza == "analise"

    # Tolerância de 60 s: os carimbos vêm de `now()` em momentos distintos.
    assert abs(por_flag["ENCAMINHAMENTO"].permanencia.segundos - 2 * 3600) < 60
    assert abs(por_flag["ABERTURA"].permanencia.segundos - 3600) < 60

    # Só o último nó está aberto.
    assert por_flag["RECEBIMENTO"].permanencia.aberto is True
    assert por_flag["ABERTURA"].permanencia.aberto is False
    assert por_flag["ENCAMINHAMENTO"].permanencia.aberto is False

    assert detalhe.permanencia.tramitacoes == 1
    assert abs(detalhe.permanencia.espera_segundos - 2 * 3600) < 60
    assert detalhe.permanencia.em_curso is True
    assert (
        detalhe.permanencia.total_ativo_segundos
        == detalhe.permanencia.espera_segundos + detalhe.permanencia.analise_segundos
    )


@pytest.mark.asyncio
async def test_encaminhado_e_nao_recebido_conta_espera_ate_agora(
    admin_engine, cenario
):
    """Processo parado na fila: a espera corre, e é o número que interessa.

    É o caso que a fatia existe para tornar visível — hoje a tela não diz há
    quanto tempo ninguém pega o processo.
    """
    t = cenario["tenant"]

    async with _sm(admin_engine)() as s:
        await encaminhar(
            s,
            cenario["processo_id"],
            EncaminharRequest(
                id_unidade_destino=cenario["destino"],
                id_prioridade=cenario["prioridade"],
                quantidade_folhas=0,
            ),
            tenant_id=t.id,
            usuario_id=cenario["usuario_id"],
            is_super_usuario=True,
        )
        await s.commit()

    await _recua(admin_engine, t.id, "ENCAMINHAMENTO", horas=2)

    async with _sm(admin_engine)() as s:
        detalhe = await get_processo_detail(s, cenario["processo_id"], tenant_id=t.id)

    assert detalhe is not None
    enc = next(m for m in detalhe.movimentacoes if m.acao_flag == "ENCAMINHAMENTO")
    assert enc.permanencia.aberto is True
    assert abs(enc.permanencia.segundos - 2 * 3600) < 60
    assert detalhe.permanencia.analise_segundos > 0  # a hora com quem abriu
    assert abs(detalhe.permanencia.espera_segundos - 2 * 3600) < 60


@pytest.mark.asyncio
async def test_detalhe_http_entrega_o_bloco_de_permanencia(admin_engine, cenario):
    """A borda HTTP: o bloco tem de chegar ao front, com os nomes que ele usa.

    `request<T>()` no `lib/api.ts` faz cast sem validar — tipo divergente do
    `response_model` fica verde no `tsc` e quebra no navegador. Este teste é o
    lado do backend dessa dupla: garante que as chaves existem no JSON.
    """
    t = cenario["tenant"]

    async def _get_user():
        async with _sm(admin_engine)() as s:
            return (
                await s.execute(
                    select(Usuario).where(Usuario.id == cenario["usuario_id"])
                )
            ).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/v2/processos/{cenario['processo_id']}")

    assert r.status_code == 200, r.text
    corpo = r.json()

    assert set(corpo["permanencia"]) == {
        "total_ativo_segundos",
        "espera_segundos",
        "analise_segundos",
        "tramitacoes",
        "em_curso",
    }
    assert corpo["permanencia"]["em_curso"] is True

    assert corpo["movimentacoes"], "processo sem movimentação no detalhe"
    for mov in corpo["movimentacoes"]:
        assert set(mov["permanencia"]) == {"segundos", "natureza", "aberto"}
        assert mov["permanencia"]["natureza"] in {"espera", "analise", "encerrado"}
        assert mov["permanencia"]["segundos"] >= 0

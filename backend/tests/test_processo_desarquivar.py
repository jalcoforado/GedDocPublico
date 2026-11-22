"""Desarquivar processo — SI-60, RF-01 do documento "GEDPub – Requisitos de
evolução v1.0" (18/11/2026).

O que estes testes provam
-------------------------
Gravar a movimentação nova é a parte fácil. O risco desta fatia está nos
LEITORES: até aqui "arquivado" queria dizer "já foi arquivado alguma vez", e
caixas, lista, detalhe, prazo, relatórios e dashboard liam assim. Um
desarquivamento que só gravasse a linha deixaria o processo reaberto contando
como encerrado em todos eles. Por isso os testes centrais conferem que cada
leitor MUDA de resposta — e que o arquivamento antigo continua no histórico.

O cenário é o de `test_processo_caixas.py`: o processo `arquivado` está na
unidade A, arquivado pelo caminho real; `saindo` está em trânsito de A para B;
`na_mesa` está parado em A. `operador` é usuário comum (não-SU) lotado em A.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select, text

from app.auth.deps import get_current_user
from app.main import app
from app.models import Movimentacao, Processo
from app.models.processo import Acao, Arquivamento
from app.models.workflow import WorkflowDefinition, WorkflowInstance
from app.schemas.processo import (
    ArquivarRequest,
    CaixaProcesso,
    DesarquivarRequest,
    EncaminharRequest,
)
from app.services.acoes_processo import (
    AcaoError,
    WorkflowStrictBlock,
    arquivar,
    desarquivar,
    encaminhar,
)
from app.services.processos import get_processo_detail
from app.services.relatorios_comum import situacao, situacao_prazo
from tests.conftest import arreio_tenant_http
from tests.test_processo_caixas import _como, _ids, _sm, cen  # noqa: F401 — fixture

JUSTIFICATIVA = "Cidadão trouxe documento novo"


async def _desarquiva(engine, cen, rotulo: str = "arquivado", **kw):
    async with _sm(engine)() as s:
        return await desarquivar(
            s,
            cen["procs"][rotulo],
            DesarquivarRequest(justificativa=kw.pop("justificativa", JUSTIFICATIVA)),
            tenant_id=kw.pop("tenant_id", cen["tenant"].id),
            usuario_id=cen["operador"],
        )


async def _detalhe(engine, cen, rotulo: str = "arquivado"):
    async with _sm(engine)() as s:
        d = await get_processo_detail(s, cen["procs"][rotulo], tenant_id=cen["tenant"].id)
    assert d is not None
    return d


async def _concede_desarquivar(engine, usuario_id: int, tenant_id: int) -> None:
    """Dá ao grupo do usuário a transação `processo_desarquivar` (0139)."""
    async with _sm(engine)() as s:
        await s.execute(text("""
            INSERT INTO utils.grupo_transacao
                (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
            SELECT :t, ug.id_grupo, tr.id, true, true, true, false
              FROM utils.usuario_grupo ug, utils.transacao tr
             WHERE ug.id_usuario = :u AND ug.excluido = false
               AND tr.codigo = 'processo_desarquivar' AND tr.excluido = false
        """), {"t": tenant_id, "u": usuario_id})
        await s.commit()


# --------------------------------------------------------------------------
# Catálogo
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_garante_acao_e_transacao(admin_engine):
    """Sem a ação o desarquivamento estoura em `_get_acao`; sem a transação,
    ninguém além do super-usuário consegue desarquivar."""
    async with _sm(admin_engine)() as s:
        acao = (await s.execute(text(
            "SELECT status_movimentacao FROM protocolos.acao "
            "WHERE flag='DESARQUIVAMENTO' AND ativo AND NOT excluido"
        ))).scalar_one_or_none()
        transacao = (await s.execute(text(
            "SELECT 1 FROM utils.transacao WHERE codigo='processo_desarquivar' "
            "AND NOT excluido"
        ))).scalar_one_or_none()
    assert acao == "recebido", "ação DESARQUIVAMENTO ausente — rode o seed_bootstrap"
    assert transacao is not None, "transação ausente — rode `alembic upgrade head`"


# --------------------------------------------------------------------------
# O processo volta a andar — e cada leitor percebe
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_volta_para_a_caixa_da_unidade_e_sai_dos_arquivados(admin_engine, cen):
    assert "arquivado" in await _ids(admin_engine, cen, CaixaProcesso.arquivados)
    assert "arquivado" not in await _ids(admin_engine, cen, CaixaProcesso.analise)

    await _desarquiva(admin_engine, cen)

    assert "arquivado" not in await _ids(admin_engine, cen, CaixaProcesso.arquivados)
    assert "arquivado" in await _ids(admin_engine, cen, CaixaProcesso.analise)
    d = await _detalhe(admin_engine, cen)
    assert d.arquivado is False
    assert d.local_atual == "A"
    assert d.permanencia.em_curso is True


@pytest.mark.asyncio
async def test_historico_guarda_o_arquivamento_e_mostra_o_desarquivamento(admin_engine, cen):
    """Nada é apagado: a movimentação do arquivamento continua na linha do
    tempo (desativada) e entra a do desarquivamento, com quem fez e a
    justificativa."""
    mov = await _desarquiva(admin_engine, cen)

    d = await _detalhe(admin_engine, cen)
    flags = [m.acao_flag for m in d.movimentacoes]
    assert "ARQUIVAMENTO" in flags and "DESARQUIVAMENTO" in flags
    desarq = next(m for m in d.movimentacoes if m.acao_flag == "DESARQUIVAMENTO")
    assert desarq.despacho is not None and desarq.despacho.despacho == JUSTIFICATIVA

    async with _sm(admin_engine)() as s:
        arq_mov = (await s.execute(select(Movimentacao).where(
            Movimentacao.id_processo == cen["procs"]["arquivado"],
            Movimentacao.id_arquivamento.is_not(None),
        ))).scalar_one()
        arq = (await s.execute(select(Arquivamento).where(
            Arquivamento.id == arq_mov.id_arquivamento))).scalar_one()
        trilha = (await s.execute(text(
            "SELECT id_usuario, payload->>'justificativa' FROM aprimora_py.audit_log "
            "WHERE tenant_id=:t AND acao='processo.desarquivado'"
        ), {"t": cen["tenant"].id})).one()
        p = (await s.execute(select(Processo).where(
            Processo.id == cen["procs"]["arquivado"]))).scalar_one()
    assert arq_mov.ativo is False and arq_mov.excluido is False
    assert arq.ativo is False
    assert tuple(trilha) == (cen["operador"], JUSTIFICATIVA)
    assert p.id_ultima_movimentacao == mov.id


@pytest.mark.asyncio
async def test_prazo_reinicia_a_partir_do_desarquivamento(admin_engine, cen):
    """Decisão do PO (22/11/2026). Processo aberto há 60 dias, com prazo de
    30, arquivado: ao desarquivar, deixa de estar concluído e ganha 30 dias
    contados de agora — não "atrasado há 30 dias". Confere o detalhe e o
    espelho SQL dos relatórios, que a lista usa para filtrar."""
    pid = cen["procs"]["arquivado"]
    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "UPDATE protocolos.processo SET prazo_servico_dias_snapshot=30, "
            "data_hora_abertura=:a WHERE id=:p"
        ), {"a": datetime.now() - timedelta(days=60), "p": pid})
        await s.commit()

    antes = await _detalhe(admin_engine, cen)
    assert antes.prazo.status == "concluido_atrasado"

    await _desarquiva(admin_engine, cen)

    depois = await _detalhe(admin_engine, cen)
    assert depois.prazo.status == "dentro_do_prazo"
    assert depois.prazo.concluido_em is None
    falta = depois.prazo.prazo_previsto_em - datetime.now()
    assert timedelta(days=29) < falta <= timedelta(days=30)
    # O destaque da caixa usa a mesma origem do prazo, e reinicia junto.
    assert depois.prazo_caixa_status == "dentro_do_prazo"

    from app.utils.relogio import agora_utc

    async with _sm(admin_engine)() as s:
        sql = (await s.execute(
            select(situacao_prazo(cen["tenant"].id, agora_utc()), situacao(cen["tenant"].id))
            .where(Processo.id == pid)
        )).one()
    assert tuple(sql) == ("dentro_do_prazo", "em_andamento")


@pytest.mark.asyncio
async def test_pode_ser_arquivado_de_novo(admin_engine, cen):
    """Desarquivado volta a ser processo comum: arquivar de novo vale, e a
    conclusão passa a ser a do arquivamento novo."""
    await _desarquiva(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        await arquivar(
            s, cen["procs"]["arquivado"], ArquivarRequest(motivo="Concluído de novo"),
            tenant_id=cen["tenant"].id, usuario_id=cen["operador"],
        )
    d = await _detalhe(admin_engine, cen)
    assert d.arquivado is True
    assert d.prazo.concluido_em is not None
    assert "arquivado" in await _ids(admin_engine, cen, CaixaProcesso.arquivados)


@pytest.mark.asyncio
async def test_dashboard_deixa_de_contar_o_desarquivado(admin_engine, cen):
    """O KPI "arquivados" e o "tempo médio de conclusão" do dashboard leem a
    movimentação do arquivamento; desativada, ela não é mais conclusão."""
    from app.services.dashboard import kpis

    async def _arquivados() -> int:
        async with _sm(admin_engine)() as s:
            r = await kpis(s, tenant_id=cen["tenant"].id, periodo_dias=7)
        return r["conclusao"]["arquivados_periodo"]

    assert await _arquivados() == 1
    await _desarquiva(admin_engine, cen)
    assert await _arquivados() == 0


# --------------------------------------------------------------------------
# O que é bloqueado, e com qual mensagem
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_processo_nao_arquivado_nao_se_desarquiva(admin_engine, cen):
    with pytest.raises(AcaoError, match="não está arquivado"):
        await _desarquiva(admin_engine, cen, "na_mesa")


@pytest.mark.asyncio
async def test_segundo_clique_nao_desarquiva_duas_vezes(admin_engine, cen):
    await _desarquiva(admin_engine, cen)
    with pytest.raises(AcaoError, match="não está arquivado"):
        await _desarquiva(admin_engine, cen)
    async with _sm(admin_engine)() as s:
        n = (await s.execute(
            select(Movimentacao.id)
            .join(Acao, Acao.id == Movimentacao.id_acao)
            .where(Movimentacao.id_processo == cen["procs"]["arquivado"],
                   Acao.flag == "DESARQUIVAMENTO")
        )).all()
    assert len(n) == 1


@pytest.mark.asyncio
async def test_processo_de_outra_prefeitura_nao_e_achado(admin_engine, cen, two_tenants):
    outro, _ = two_tenants
    with pytest.raises(AcaoError, match="não encontrado"):
        await _desarquiva(admin_engine, cen, tenant_id=outro)
    assert (await _detalhe(admin_engine, cen)).arquivado is True


@pytest.mark.asyncio
async def test_fluxo_rigido_sem_regra_de_retomada_bloqueia(admin_engine, cen):
    """O strict só deixa arquivar em estado final, e chegar ao final ENCERRA a
    instância. Por isso o teste monta a instância já encerrada: é o caso real,
    e é o que um teste com instância ativa deixaria passar."""
    t = cen["tenant"].id
    async with _sm(admin_engine)() as s:
        wf = WorkflowDefinition(
            tenant_id=t, slug="rigido", nome="Rígido", versao=1, ativo=True,
            dsl={"strict": True, "estados": [{"slug": "fim", "final": True}],
                 "transicoes": []},
            criado_em=datetime.now(),
        )
        s.add(wf)
        await s.flush()
        s.add(WorkflowInstance(
            tenant_id=t, id_workflow_definition=wf.id,
            id_processo=cen["procs"]["arquivado"], entidade_tipo="processo",
            entidade_id=cen["procs"]["arquivado"], estado_atual="fim", ativa=False,
            iniciada_em=datetime.now(), finalizada_em=datetime.now(),
        ))
        await s.commit()
    try:
        with pytest.raises(WorkflowStrictBlock, match="fluxo rígido"):
            await _desarquiva(admin_engine, cen)
        assert (await _detalhe(admin_engine, cen)).arquivado is True
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "DELETE FROM aprimora_py.workflow_instance WHERE tenant_id=:t"), {"t": t})
            await s.execute(text(
                "DELETE FROM aprimora_py.workflow_definition WHERE tenant_id=:t"), {"t": t})
            await s.commit()


@pytest.mark.asyncio
async def test_arquivado_nao_pode_ser_encaminhado(admin_engine, cen):
    """Correção pedida no próprio card: só a tela barrava."""
    async with _sm(admin_engine)() as s:
        with pytest.raises(AcaoError, match="arquivado não pode ser encaminhado"):
            await encaminhar(
                s, cen["procs"]["arquivado"],
                EncaminharRequest(id_unidade_destino=cen["b"], id_prioridade=cen["prioridade"]),
                tenant_id=cen["tenant"].id, usuario_id=cen["operador"],
            )


@pytest.mark.asyncio
async def test_em_transito_nao_pode_ser_arquivado(admin_engine, cen):
    """`saindo` está encaminhado de A para B e ainda não foi recebido."""
    async with _sm(admin_engine)() as s:
        with pytest.raises(AcaoError, match="em trânsito não pode ser arquivado"):
            await arquivar(
                s, cen["procs"]["saindo"], ArquivarRequest(motivo="Encerrar"),
                tenant_id=cen["tenant"].id, usuario_id=cen["operador"],
            )


def test_justificativa_e_obrigatoria_e_espaco_nao_conta():
    for ruim in ("", "    ", "abc"):
        with pytest.raises(ValidationError):
            DesarquivarRequest(justificativa=ruim)
    assert DesarquivarRequest(justificativa="  Pedido novo  ").justificativa == "Pedido novo"


# --------------------------------------------------------------------------
# A borda HTTP, com usuário comum
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_usuario_comum_sem_a_transacao_leva_403(admin_engine, cen):
    """`operador` tem `processo` com inserir/atualizar/excluir — tramita tudo —
    e mesmo assim não desarquiva: o RF-01 pede permissão específica."""
    t = cen["tenant"]
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/v2/processos/{cen['procs']['arquivado']}/desarquivar",
            json={"justificativa": JUSTIFICATIVA},
        )
    assert r.status_code == 403, r.text
    assert (await _detalhe(admin_engine, cen)).arquivado is True


@pytest.mark.asyncio
async def test_http_usuario_comum_com_a_transacao_desarquiva(admin_engine, cen):
    t = cen["tenant"]
    await _concede_desarquivar(admin_engine, cen["operador"], t.id)
    app.dependency_overrides[get_current_user] = _como(admin_engine, cen["operador"])
    arreio_tenant_http(t.id, t.slug)
    pid = cen["procs"]["arquivado"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        sem = await client.post(f"/api/v2/processos/{pid}/desarquivar",
                                json={"justificativa": "  "})
        assert sem.status_code == 422, sem.text

        r = await client.post(f"/api/v2/processos/{pid}/desarquivar",
                              json={"justificativa": JUSTIFICATIVA})
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["arquivado"] is False
        assert any(m["acao_flag"] == "DESARQUIVAMENTO" for m in corpo["movimentacoes"])

        de_novo = await client.post(f"/api/v2/processos/{pid}/desarquivar",
                                    json={"justificativa": JUSTIFICATIVA})
        assert de_novo.status_code == 400, de_novo.text
        assert "não está arquivado" in de_novo.json()["detail"]


@pytest.mark.asyncio
async def test_http_de_outra_prefeitura_e_404(admin_engine, cen, two_tenants):
    """Servidor da prefeitura B, com o Protocolo contratado e a transação
    `processo_desarquivar`, pede para desarquivar um processo da A: 404, que
    não confirma que o processo existe, e o processo continua arquivado."""
    from tests.test_permissoes_modulo import _cria_usuario_comum as _usuario_com

    outro, _ = two_tenants
    async with _sm(admin_engine)() as s:
        # Sem o módulo o gate de contratação barra antes (403) e o teste não
        # chega ao que importa.
        await s.execute(text(
            "INSERT INTO aprimora_py.tenant_modulo (tenant_id, id_modulo) "
            "SELECT :t, id FROM aprimora_py.modulo WHERE slug='protocolo'"), {"t": outro})
        alheio = await _usuario_com(s, outro, codigo_transacao="processo_desarquivar")
        await s.commit()
    app.dependency_overrides[get_current_user] = _como(admin_engine, alheio)
    arreio_tenant_http(outro)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                f"/api/v2/processos/{cen['procs']['arquivado']}/desarquivar",
                json={"justificativa": JUSTIFICATIVA},
            )
    finally:
        # A limpeza de `two_tenants` não conhece grupo, usuário nem contratação.
        async with _sm(admin_engine)() as s:
            for tabela in ("utils.grupo_transacao", "utils.usuario_grupo", "utils.grupo",
                           "aprimora_py.audit_log", "utils.usuario",
                           "aprimora_py.tenant_modulo"):
                await s.execute(text(f"DELETE FROM {tabela} WHERE tenant_id=:t"), {"t": outro})
            await s.commit()
    assert r.status_code == 404, r.text
    assert (await _detalhe(admin_engine, cen)).arquivado is True

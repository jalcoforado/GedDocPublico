"""Relatórios de protocolo — quem vê o quê (SI-34).

Os três relatórios (processos, tramitação, assinaturas) listavam processos sem
olhar a credencial de sigilo de quem consulta: um processo reservado aparecia
na tela, no CSV e no PDF para qualquer usuário com a transação `processo`. A
listagem de processos (`GET /processos`) já filtrava; os relatórios, não.

Aqui:
- usuário COMUM (credencial `interno`, nível != 0) não vê processo acima da
  credencial em nenhum dos três relatórios, em JSON nem em CSV;
- super-usuário continua vendo tudo;
- rascunho de outra pessoa não entra em relatório (SI-16: rascunho é de quem
  o criou);
- dados de outra prefeitura não aparecem, nem pedindo a unidade dela;
- o PDF de tramitação em segundo plano leva a credencial de quem pediu.

Teste HTTP de propósito: a costura router↔service é onde o filtro some, e o
bypass de super-usuário esconde defeito de usuário comum (CLAUDE.md).
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from tests.conftest import admin_id_do_tenant, as_user_dependency, provisionar_tenant_de_teste
from tests.test_processo_responsavel import _cria_usuario_comum


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _cenario(admin_engine, prefixo: str) -> dict:
    """Prefeitura com um processo de cada nível que importa, um rascunho de
    outra pessoa e uma solicitação de assinatura em cada processo."""
    t = await provisionar_tenant_de_teste(admin_engine, prefixo)
    async with _sm(admin_engine)() as s:
        q = lambda sql, **p: s.execute(text(sql), {"t": t.id, **p})  # noqa: E731
        unidade = (await q(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t ORDER BY id LIMIT 1"
        )).scalar_one()
        tipo_manif = (await q(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"
        )).scalar_one()
        manif = (await q(
            "INSERT INTO protocolos.manifestante (tenant_id, id_tipo_manifestante, nome, ativo, excluido) "
            "VALUES (:t, :tm, 'Maria Relatorio', true, false) RETURNING id", tm=tipo_manif,
        )).scalar_one()
        tipo_proc = (await q(
            "INSERT INTO protocolos.tipo_processo (tenant_id, tipo_processo, ativo, excluido) "
            "VALUES (:t, 'Geral', true, false) RETURNING id"
        )).scalar_one()
        assunto = (await q(
            "INSERT INTO protocolos.assunto (tenant_id, assunto, id_tipo_processo, ativo, excluido) "
            "VALUES (:t, 'Solicitação', :tp, true, false) RETURNING id", tp=tipo_proc,
        )).scalar_one()
        admin = await admin_id_do_tenant(admin_engine, t.id)
        comum = await _cria_usuario_comum(s, t.id, unidade_id=unidade)
        # O helper cria o operador com credencial `ultrassecreto` (o teste de
        # origem não trata de sigilo). Aqui ele tem a credencial padrão de
        # servidor, `interno`: vê ostensivo e interno, não reservado.
        await q(
            "UPDATE utils.usuario SET nivel_acesso_sigilo = 'interno' WHERE id = :u", u=comum
        )

        processos: dict[str, tuple[int, str]] = {}
        for chave, nivel, situacao in (
            ("ostensivo", "ostensivo", "protocolado"),
            ("interno", "interno", "protocolado"),
            ("reservado", "reservado", "protocolado"),
            ("rascunho_do_admin", "ostensivo", "rascunho"),
        ):
            numero = None if situacao == "rascunho" else f"R{uuid.uuid4().hex[:6]}/2026"
            pid = (await q(
                """
                INSERT INTO protocolos.processo
                    (tenant_id, id_assunto, id_manifestante, id_unidade_proprietaria,
                     id_local_atual, numero_processo, nivel_sigilo, situacao, id_usuario,
                     virtual, externo, ativo, excluido, migrado, data_hora_abertura)
                VALUES (:t, :a, :m, :u, :u, :n, :nivel, :sit, :usr,
                        true, false, true, false, false, NOW())
                RETURNING id
                """,
                a=assunto, m=manif, u=unidade, n=numero, nivel=nivel, sit=situacao, usr=admin,
            )).scalar_one()
            processos[chave] = (pid, numero or "")
            await q(
                "INSERT INTO protocolos.solicitacao_assinatura "
                "(tenant_id, id_processo, id_solicitante, id_usuario, dt_inicio) "
                "VALUES (:t, :p, :usr, :usr, NOW())", p=pid, usr=admin,
            )
        await s.commit()
    return {"tenant": t, "unidade": unidade, "admin": admin, "comum": comum, "processos": processos}


async def _cliente_como(admin_engine, cen: dict, usuario: str) -> AsyncClient:
    t = cen["tenant"]
    as_user_dependency(admin_engine, cen[usuario], t.id, t.slug)()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _fechar():
    app.dependency_overrides.clear()
    from app.database import engine

    await engine.dispose()


def _ids(cen: dict, *chaves: str) -> set[int]:
    return {cen["processos"][c][0] for c in chaves}


# ---------------------------------------------------------------- processos


@pytest.mark.asyncio
async def test_relatorio_de_processos_respeita_o_sigilo_de_quem_consulta(admin_engine):
    cen = await _cenario(admin_engine, "relsig")
    try:
        async with await _cliente_como(admin_engine, cen, "comum") as c:
            r = await c.get("/api/v2/relatorios/processos.json")
            csv = await c.get("/api/v2/relatorios/processos.csv")
        assert r.status_code == 200, r.text
        assert {p["id"] for p in r.json()["processos"]} == _ids(cen, "ostensivo", "interno")
        # os totais contam o mesmo recorte da lista, não o banco inteiro
        assert r.json()["totais"]["total"] == 2
        assert csv.status_code == 200, csv.text
        assert cen["processos"]["reservado"][1] not in csv.text
        assert cen["processos"]["ostensivo"][1] in csv.text
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_super_usuario_continua_vendo_todos_os_niveis(admin_engine):
    cen = await _cenario(admin_engine, "relsu")
    try:
        async with await _cliente_como(admin_engine, cen, "admin") as c:
            r = await c.get("/api/v2/relatorios/processos.json")
        assert {p["id"] for p in r.json()["processos"]} == _ids(
            cen, "ostensivo", "interno", "reservado"
        )
    finally:
        await _fechar()


# --------------------------------------------------------------- tramitação


@pytest.mark.asyncio
async def test_relatorio_de_tramitacao_respeita_o_sigilo(admin_engine):
    cen = await _cenario(admin_engine, "reltram")
    try:
        async with await _cliente_como(admin_engine, cen, "comum") as c:
            r = await c.get("/api/v2/relatorios/tramitacao.json")
            csv = await c.get("/api/v2/relatorios/tramitacao.csv")
        assert r.status_code == 200, r.text
        assert {p["id"] for p in r.json()["processos"]} == _ids(cen, "ostensivo", "interno")
        assert cen["processos"]["reservado"][1] not in csv.text
    finally:
        await _fechar()


@pytest.mark.asyncio
async def test_pdf_de_tramitacao_em_segundo_plano_leva_a_credencial(admin_engine, monkeypatch):
    """O worker não tem usuário: quem pediu decide os níveis, no ato do pedido."""
    cen = await _cenario(admin_engine, "reljob")
    chamadas: list[tuple] = []
    from app.tasks import relatorio_tramitacao_bg

    monkeypatch.setattr(
        relatorio_tramitacao_bg.run, "delay", lambda *a, **k: chamadas.append((a, k))
    )
    try:
        async with await _cliente_como(admin_engine, cen, "comum") as c:
            r = await c.post("/api/v2/jobs/relatorio-tramitacao", json={})
        assert r.status_code == 202, r.text
        args, kwargs = chamadas[0]
        niveis = kwargs.get("niveis_permitidos", args[5] if len(args) > 5 else None)
        assert niveis is not None and "reservado" not in niveis
    finally:
        await _fechar()


# --------------------------------------------------------------- assinaturas


@pytest.mark.asyncio
async def test_relatorio_de_assinaturas_respeita_sigilo_e_rascunho(admin_engine):
    cen = await _cenario(admin_engine, "relass")
    try:
        async with await _cliente_como(admin_engine, cen, "comum") as c:
            r = await c.get("/api/v2/relatorios/assinaturas.json")
            csv = await c.get("/api/v2/relatorios/assinaturas.csv")
        assert r.status_code == 200, r.text
        assert {s["id_processo"] for s in r.json()["solicitacoes"]} == _ids(
            cen, "ostensivo", "interno"
        )
        assert cen["processos"]["reservado"][1] not in csv.text
    finally:
        await _fechar()


# ------------------------------------------------------------- prefeituras


@pytest.mark.asyncio
async def test_relatorios_nao_mostram_dados_de_outra_prefeitura(admin_engine):
    nossa = await _cenario(admin_engine, "relpa")
    outra = await _cenario(admin_engine, "relpb")
    try:
        async with await _cliente_como(admin_engine, nossa, "admin") as c:
            tudo = await c.get("/api/v2/relatorios/processos.json")
            # pedir a unidade da outra prefeitura não abre a porta
            unidade_alheia = await c.get(
                "/api/v2/relatorios/processos.json", params={"id_unidade": outra["unidade"]}
            )
            tram = await c.get("/api/v2/relatorios/tramitacao.json")
            ass = await c.get("/api/v2/relatorios/assinaturas.json")
        alheios = _ids(outra, "ostensivo", "interno", "reservado")
        assert not alheios & {p["id"] for p in tudo.json()["processos"]}
        assert unidade_alheia.json()["processos"] == []
        assert unidade_alheia.json()["totais"]["total"] == 0
        assert not alheios & {p["id"] for p in tram.json()["processos"]}
        assert not alheios & {s["id_processo"] for s in ass.json()["solicitacoes"]}
    finally:
        await _fechar()

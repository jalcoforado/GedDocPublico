"""Minuta tem de respeitar o sigilo do processo dono (SI-62).

O defeito, encontrado em 2026-11-22 na análise do SI-58: as 11 rotas de
minuta filtravam a prefeitura e mais nada. Qualquer servidor com
`processo.atualizar` lia `GET /minutas/{id}` — o corpo do documento — de
processo reservado ou secreto acima da credencial dele, iterando o id; e
editava, finalizava e apagava do mesmo jeito. É a classe do download de anexo
(`test_guarda_anexo_sigiloso.py`), que ficou aberto sete meses.

O SI-62 depende disto: o rascunho do despacho é uma minuta, e "só o autor vê
o rascunho" não vale nada se a rota da minuta não confere nem o sigilo.

Duas partes:
- GUARDA estática: toda rota com `minuta_id` chama `obter_minuta_autorizada`;
  toda rota de minuta por processo chama `exigir_acesso_ao_processo`; nenhum
  router usa o carregador cru `obter_minuta`.
- HTTP com usuário COMUM (não super-usuário, que passa por cima do sigilo):
  o mesmo operador abre a minuta do processo ostensivo — controle que prova
  que o cenário funciona — e leva 404 em todas as rotas da minuta do
  processo reservado, da outra prefeitura e do rascunho de outra pessoa.
"""
from __future__ import annotations

import ast
import uuid
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Assunto, Manifestante, Minuta, Processo, TipoProcesso, Usuario
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name
ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"
SEGREDO = "TEXTO-SIGILOSO-DA-MINUTA"


# --------------------------------------------------------------------------
# Guarda estática
# --------------------------------------------------------------------------


def _funcoes_de_rota():
    """(arquivo, função, nomes dos parâmetros, chamadas feitas no corpo)."""
    for arq in sorted(ROUTERS.glob("*.py")):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.AsyncFunctionDef):
                continue
            if not any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                       and d.func.attr in {"get", "post", "put", "delete", "patch"}
                       for d in no.decorator_list):
                continue
            params = {a.arg for a in no.args.args}
            chamadas = {
                c.func.attr if isinstance(c.func, ast.Attribute) else getattr(c.func, "id", "")
                for c in ast.walk(no) if isinstance(c, ast.Call)
            }
            yield arq.name, no.name, params, chamadas


# Serviços que recebem o id de UMA minuta. Rota que chama algum deles mexe
# numa minuta, mesmo sem `minuta_id` na assinatura: o callback do Google lia o
# id do `state` do OAuth e copiava a minuta para a conta Google de quem pediu.
SERVICOS_POR_MINUTA = {
    "atualizar_minuta", "excluir_minuta", "finalizar_minuta", "listar_historico_minuta",
    "criar_google_doc_para_minuta", "sincronizar_google_doc_para_minuta",
    "arquivar_google_doc_para_minuta", "aplicar_modelo_na_minuta",
}


# Rota com `minuta_id` que NÃO serve conteúdo, com a razão ao lado. Entrada
# nova aqui pede a mesma justificativa.
EXCECOES = {
    # Só grava o id no `state` do OAuth; quem copia a minuta para o Google é
    # o callback, e ele confere. Conferir aqui também mudava o erro do início
    # do fluxo para minuta inexistente (o teste do redirect usa id 123).
    "auth.py::initiate_google_oauth",
}


def test_toda_rota_que_mexe_numa_minuta_autoriza_antes():
    rotas = [r for r in _funcoes_de_rota()
             if ("minuta_id" in r[2] or r[3] & SERVICOS_POR_MINUTA)
             and f"{r[0]}::{r[1]}" not in EXCECOES]
    # Sem isto, um erro no parser deixaria a guarda verde sem olhar nada.
    assert len(rotas) >= 10, rotas
    faltando = [f"{a}::{f}" for a, f, _, ch in rotas if "obter_minuta_autorizada" not in ch]
    assert faltando == [], f"rota de minuta sem conferir sigilo: {faltando}"


def test_excecao_continua_sem_tocar_na_minuta():
    """A isenção vale enquanto a rota não lê nem altera a minuta."""
    isentas = [r for r in _funcoes_de_rota() if f"{r[0]}::{r[1]}" in EXCECOES]
    assert len(isentas) == len(EXCECOES), "exceção aponta para rota que não existe mais"
    tocam = [f"{a}::{f}" for a, f, _, ch in isentas
             if ch & (SERVICOS_POR_MINUTA | {"obter_minuta"})]
    assert tocam == [], f"rota isenta passou a mexer na minuta: {tocam}"


def test_rota_de_minuta_por_processo_confere_o_processo():
    rotas = [r for r in _funcoes_de_rota()
             if r[0] == "minutas.py" and "processo_id" in r[2]]
    assert len(rotas) >= 2, rotas
    faltando = [f for _, f, _, ch in rotas if "exigir_acesso_ao_processo" not in ch]
    assert faltando == [], f"rota de minuta por processo sem conferir sigilo: {faltando}"


def test_nenhum_router_usa_o_carregador_cru():
    crus = [f"{a}::{f}" for a, f, _, ch in _funcoes_de_rota() if "obter_minuta" in ch]
    assert crus == [], f"use obter_minuta_autorizada: {crus}"


# --------------------------------------------------------------------------
# Cenário HTTP
# --------------------------------------------------------------------------


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _usuario_comum(s, tenant_id: int, unidade_id: int, credencial: str) -> int:
    """Operador não-SU com `processo` (inserir/atualizar/excluir) — mesmo
    padrão de `test_marcadores_favoritos.py::_cria_usuario_comum`."""
    sistema_id = (await s.execute(text(
        "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
    ), {"app": APP})).scalar_one()
    nivel_id = (await s.execute(text(
        "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
    ))).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (await s.execute(text(
            "INSERT INTO utils.nivel (nivel, valor, excluido) "
            "VALUES ('Operacional', 1, false) RETURNING id"
        ))).scalar_one()
    transacao_id = (await s.execute(text(
        "SELECT id FROM utils.transacao WHERE codigo = 'processo' AND excluido = false LIMIT 1"
    ))).scalar_one()
    uid = (await s.execute(text("""
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo, excluido,
                                   app, nivel_acesso_sigilo, id_unidade_trabalho)
        VALUES (:t, 'Operador', :e, '', :c, true, false, :app, :cred, :u) RETURNING id
    """), {"t": tenant_id, "e": f"op-{uuid.uuid4().hex[:8]}@minuta.test",
           "c": uuid.uuid4().hex[:11], "app": APP, "cred": credencial, "u": unidade_id})).scalar_one()
    gid = (await s.execute(text(
        "INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido) "
        "VALUES (:t, :n, :s, 'Grupo Minuta', false) RETURNING id"
    ), {"t": tenant_id, "n": nivel_id, "s": sistema_id})).scalar_one()
    await s.execute(text(
        "INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app) "
        "VALUES (:t, :u, :g, true, false, :app)"
    ), {"t": tenant_id, "u": uid, "g": gid, "app": APP})
    await s.execute(text(
        "INSERT INTO utils.grupo_transacao "
        "(tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido) "
        "VALUES (:t, :g, :tr, true, true, true, false)"
    ), {"t": tenant_id, "g": gid, "tr": transacao_id})
    return uid


async def _prefeitura(admin_engine, prefixo: str) -> dict:
    slug = f"{prefixo}{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome=f"Pref {slug}", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    async with _sm(admin_engine)() as s:
        unidade = (await s.execute(text(
            "SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t ORDER BY id LIMIT 1"
        ), {"t": tenant.id})).scalar_one()
        tipo_manif = (await s.execute(text(
            "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t ORDER BY id LIMIT 1"
        ), {"t": tenant.id})).scalar_one()
        tp = TipoProcesso(tenant_id=tenant.id, tipo_processo="Geral",
                          exige_processo_pai=False, ativo=True, excluido=False)
        manif = Manifestante(tenant_id=tenant.id, id_tipo_manifestante=tipo_manif,
                             nome="Maria", ativo=True, excluido=False)
        s.add_all([tp, manif])
        await s.flush()
        assunto = Assunto(tenant_id=tenant.id, assunto="Solicitação", id_tipo_processo=tp.id,
                          exige_processo_pai=False, ativo=True, excluido=False)
        s.add(assunto)
        await s.flush()
        operador = await _usuario_comum(s, tenant.id, unidade, "interno")
        outro = await _usuario_comum(s, tenant.id, unidade, "ultrassecreto")

        def processo(nivel: str, *, rascunho_de: int | None = None) -> Processo:
            return Processo(
                tenant_id=tenant.id, id_assunto=assunto.id, virtual=True,
                data_hora_abertura=datetime.now(),
                numero_processo=None if rascunho_de else f"{slug}-{uuid.uuid4().hex[:6]}",
                situacao="rascunho" if rascunho_de else "protocolado",
                id_usuario=rascunho_de,
                id_unidade_proprietaria=unidade, id_manifestante=manif.id,
                id_local_atual=unidade, nivel_sigilo=nivel, ativo=True, excluido=False,
            )

        ostensivo, reservado, rascunho_alheio = (
            processo("ostensivo"), processo("reservado"), processo("ostensivo", rascunho_de=outro)
        )
        s.add_all([ostensivo, reservado, rascunho_alheio])
        await s.flush()

        def minuta(p: Processo) -> Minuta:
            return Minuta(
                tenant_id=tenant.id, id_processo=p.id, titulo="Parecer", origem="interno",
                status="rascunho", versao=1, corpo_html=f"<p>{SEGREDO}</p>",
                id_usuario_criacao=outro, criado_em=datetime.now(), ativo=True, excluido=False,
            )

        m_ost, m_res, m_rasc = minuta(ostensivo), minuta(reservado), minuta(rascunho_alheio)
        s.add_all([m_ost, m_res, m_rasc])
        await s.flush()
        await s.commit()
        return {
            "tenant": tenant, "operador": operador,
            "p_ostensivo": ostensivo.id, "p_reservado": reservado.id,
            "p_rascunho_alheio": rascunho_alheio.id,
            "m_ostensivo": m_ost.id, "m_reservado": m_res.id, "m_rascunho_alheio": m_rasc.id,
        }


async def _limpar(admin_engine, tenant_id: int) -> None:
    async with _sm(admin_engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.minuta_historico WHERE tenant_id=:t",
            "DELETE FROM protocolos.minuta WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL, "
            "  id_local_atual=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest_asyncio.fixture
async def cen(admin_engine):
    a = await _prefeitura(admin_engine, "minsig-a-")
    b = await _prefeitura(admin_engine, "minsig-b-")
    yield {"a": a, "b": b}
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    await _limpar(admin_engine, a["tenant"].id)
    await _limpar(admin_engine, b["tenant"].id)


def _cliente(admin_engine, pref: dict) -> AsyncClient:
    """Operador comum (credencial "interno") da prefeitura `pref`."""
    async def _usuario():
        async with _sm(admin_engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == pref["operador"]))).scalar_one()

    app.dependency_overrides[get_current_user] = _usuario
    arreio_tenant_http(pref["tenant"].id, pref["tenant"].slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


ROTAS_DA_MINUTA = [
    ("GET", "/api/v2/minutas/{id}", None),
    ("GET", "/api/v2/minutas/{id}/historico", None),
    ("PUT", "/api/v2/minutas/{id}", {"titulo": "Alterado", "versao": 1}),
    # SI-67 — trocar o modelo reescreve o corpo: não pode alcançar minuta alheia.
    ("POST", "/api/v2/minutas/{id}/aplicar-modelo", {"id_template": None, "versao": 1}),
    ("DELETE", "/api/v2/minutas/{id}", None),
    ("POST", "/api/v2/minutas/{id}/finalizar", None),
    ("GET", "/api/v2/minutas/{id}/google-editor-url", None),
    ("POST", "/api/v2/minutas/{id}/criar-em-google", None),
    ("POST", "/api/v2/minutas/{id}/sincronizar-google", None),
    ("DELETE", "/api/v2/minutas/{id}/arquivar-google", None),
]


async def _todas_dao_404(cli: AsyncClient, minuta_id: int) -> list[str]:
    erradas = []
    for metodo, rota, corpo in ROTAS_DA_MINUTA:
        r = await cli.request(metodo, rota.format(id=minuta_id), json=corpo)
        if r.status_code != 404 or SEGREDO in r.text:
            erradas.append(f"{metodo} {rota} -> {r.status_code}")
    return erradas


@pytest.mark.asyncio
async def test_controle_operador_abre_a_minuta_do_processo_ostensivo(admin_engine, cen):
    """Sem este, um cenário quebrado deixaria os 404 abaixo verdes sem provar nada."""
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        r = await cli.get(f"/api/v2/minutas/{a['m_ostensivo']}")
        assert r.status_code == 200, r.text
        assert SEGREDO in r.text
        r = await cli.get(f"/api/v2/processos/{a['p_ostensivo']}/minutas")
        assert r.status_code == 200, r.text
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_minuta_de_processo_acima_da_credencial_da_404_em_toda_rota(admin_engine, cen):
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        assert await _todas_dao_404(cli, a["m_reservado"]) == []
        r = await cli.get(f"/api/v2/processos/{a['p_reservado']}/minutas")
        assert r.status_code == 404, r.text
        r = await cli.post(f"/api/v2/processos/{a['p_reservado']}/minutas",
                           json={"titulo": "Nova"})
        assert r.status_code == 404, r.text
    # Nada mudou na minuta: nem edição, nem exclusão, nem finalização.
    async with _sm(admin_engine)() as s:
        m = (await s.execute(select(Minuta).where(Minuta.id == a["m_reservado"]))).scalar_one()
        assert (m.titulo, m.status, m.excluido) == ("Parecer", "rascunho", False)


@pytest.mark.asyncio
async def test_minuta_de_outra_prefeitura_da_404_em_toda_rota(admin_engine, cen):
    a, b = cen["a"], cen["b"]
    async with _cliente(admin_engine, a) as cli:
        assert await _todas_dao_404(cli, b["m_ostensivo"]) == []
        r = await cli.get(f"/api/v2/processos/{b['p_ostensivo']}/minutas")
        assert r.status_code == 404 or r.json() == [], r.text


@pytest.mark.asyncio
async def test_minuta_de_rascunho_de_outra_pessoa_da_404(admin_engine, cen):
    a = cen["a"]
    async with _cliente(admin_engine, a) as cli:
        assert await _todas_dao_404(cli, a["m_rascunho_alheio"]) == []
        r = await cli.get(f"/api/v2/processos/{a['p_rascunho_alheio']}/minutas")
        assert r.status_code == 404, r.text

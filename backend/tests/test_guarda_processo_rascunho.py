"""Rascunho = processo sem número (E3, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §5 E3.
Desenho: `docs/superpowers/specs/2026-09-19-e3-rascunho-sem-numero-design.md`.

Por que este arquivo existe
----------------------------
Antes de E3 não existia NENHUM teste garantindo "numero_processo sempre
presente" — a garantia era 100% estrutural (`NOT NULL` no banco + `str` não-
Optional no Pydantic). Agora que a coluna é nullable, o invariante que
substitui aquela garantia estrutural — `situacao='rascunho' <=>
numero_processo IS NULL` — precisa de teste próprio, porque o CHECK do banco
é a única coisa que ainda o impõe.

**Usuário comum.** A suíte inteira deste repositório tende a exercitar
super-usuário, e o bypass de SU em `auth/perms.py` retorna ANTES de olhar
`action` — foi assim que 10 rotas do transporte devolveram 500 pra operador
sem nenhum teste vermelho. O teste HTTP daqui usa usuário comum de propósito.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import (
    Assunto,
    Manifestante,
    Prioridade,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from app.services.apensamento import ApensamentoError, apensar
from app.services.cidadao_processos import listar_meus
from app.services.numeracao_processo import emitir_numero
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _cria_usuario_comum(session, tenant_id: int, *, unidade_id: int) -> int:
    """Cópia verbatim de test_processo_responsavel.py::_cria_usuario_comum."""
    sistema_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.sistema WHERE app = :app AND excluido = false LIMIT 1"
            ),
            {"app": APP},
        )
    ).scalar_one()
    nivel_id = (
        await session.execute(
            text("SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1")
        )
    ).scalar_one_or_none()
    if nivel_id is None:
        nivel_id = (
            await session.execute(
                text(
                    "INSERT INTO utils.nivel (nivel, valor, excluido) "
                    "VALUES ('Operacional', 1, false) RETURNING id"
                )
            )
        ).scalar_one()
    transacao_id = (
        await session.execute(
            text(
                "SELECT id FROM utils.transacao WHERE codigo = 'processo' "
                "AND excluido = false LIMIT 1"
            )
        )
    ).scalar_one()
    uid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                   excluido, app, nivel_acesso_sigilo,
                                   id_unidade_trabalho)
        VALUES (:t, 'Operador E3', :email, '', :cpf, true, false, :app,
                'ultrassecreto', :u)
        RETURNING id
    """
            ),
            {
                "t": tenant_id,
                "email": f"op-{uuid.uuid4().hex[:8]}@e3.test",
                "cpf": uuid.uuid4().hex[:11],
                "app": APP,
                "u": unidade_id,
            },
        )
    ).scalar_one()
    gid = (
        await session.execute(
            text(
                """
        INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
        VALUES (:t, :n, :s, 'Grupo E3', false) RETURNING id
    """
            ),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id},
        )
    ).scalar_one()
    await session.execute(
        text(
            """
        INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
        VALUES (:t, :u, :g, true, false, :app)
    """
        ),
        {"t": tenant_id, "u": uid, "g": gid, "app": APP},
    )
    await session.execute(
        text(
            """
        INSERT INTO utils.grupo_transacao
            (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
        VALUES (:t, :g, :tr, true, true, true, false)
    """
        ),
        {"t": tenant_id, "g": gid, "tr": transacao_id},
    )
    return uid


@pytest_asyncio.fixture
async def cen(admin_engine):
    """Tenant com origem+destino, assunto, manifestante, prioridade global e
    um usuário comum com a transação `processo` concedida."""
    slug = _slug("e3-")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref E3", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )

    async with _sm(admin_engine)() as s:
        origem = (
            await s.execute(
                text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
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
                    "SELECT id FROM protocolos.tipo_manifestante WHERE tenant_id=:t "
                    "ORDER BY id LIMIT 1"
                ),
                {"t": tenant.id},
            )
        ).scalar_one()

        destino = UnidadeTrabalho(
            tenant_id=tenant.id, unidade_trabalho="Setor de Destino",
            id_tipo_unidade_trabalho=tipo_unidade, excluido=False,
        )
        tp = TipoProcesso(
            tenant_id=tenant.id, tipo_processo="Geral E3",
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        # Prioridade é catálogo GLOBAL (sem tenant_id) — mesma nota de
        # test_permanencia_processo.py: limpeza é por id, não por tenant.
        prio = Prioridade(
            prioridade="Normal E3", fator=1, cor="#999999", ativo=True, excluido=False,
        )
        manif = Manifestante(
            tenant_id=tenant.id, id_tipo_manifestante=id_tipo_manifestante,
            nome="Maria", cpf_cnpj=uuid.uuid4().hex[:11], ativo=True, excluido=False,
        )
        s.add_all([destino, tp, prio, manif])
        await s.flush()

        assunto = Assunto(
            tenant_id=tenant.id, assunto="Solicitação E3", id_tipo_processo=tp.id,
            exige_processo_pai=False, ativo=True, excluido=False,
        )
        s.add(assunto)
        await s.flush()

        operador = await _cria_usuario_comum(s, tenant.id, unidade_id=origem)
        await s.commit()

        dados = {
            "tenant": tenant,
            "origem": origem,
            "destino": destino.id,
            "assunto": assunto.id,
            "manifestante": manif.id,
            "prioridade": prio.id,
            "operador": operador,
        }

    yield dados

    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(admin_engine)() as s:
        for stmt in (
            "UPDATE protocolos.processo SET id_ultima_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.encaminhamento WHERE tenant_id=:t",
            "DELETE FROM protocolos.despacho WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo_apensamento WHERE tenant_id=:t",
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
        await s.execute(
            text("DELETE FROM protocolos.prioridade WHERE id=:p"),
            {"p": dados["prioridade"]},
        )
        await s.commit()


def _as_operador(engine, uid: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)


@pytest.mark.asyncio
async def test_http_usuario_comum_cria_rascunho_e_tramitacao_emite_numero(
    admin_engine, cen
):
    """Fluxo completo pela borda HTTP, com usuário comum (não SU).

    Cobre o núcleo do desenho: nasce sem número, tramitar emite número (+
    muda situacao), e um audit log registra o evento.
    """
    t = cen["tenant"]
    _as_operador(admin_engine, cen["operador"], t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r_criar = await client.post(
            "/api/v2/processos",
            json={
                "id_assunto": cen["assunto"],
                "id_manifestante": cen["manifestante"],
                "id_unidade_proprietaria": cen["origem"],
                "rascunho": True,
            },
        )
        assert r_criar.status_code == 201, r_criar.text
        rascunho = r_criar.json()
        assert rascunho["numero_processo"] is None
        assert rascunho["nup"] is None
        assert rascunho["situacao"] == "rascunho"
        pid = rascunho["id"]

        r_enc = await client.post(
            f"/api/v2/processos/{pid}/encaminhamentos",
            json={
                "id_unidade_destino": cen["destino"],
                "id_prioridade": cen["prioridade"],
            },
        )
        assert r_enc.status_code == 200, r_enc.text
        protocolado = r_enc.json()
        assert protocolado["numero_processo"] is not None
        assert protocolado["situacao"] == "protocolado"

    async with _sm(admin_engine)() as s:
        acao = (
            await s.execute(
                text(
                    "SELECT acao FROM aprimora_py.audit_log WHERE tenant_id=:t "
                    "AND id_entidade=:p ORDER BY id DESC"
                ),
                {"t": t.id, "p": pid},
            )
        ).scalars().all()
    assert "processo.numerado_na_tramitacao" in acao


@pytest.mark.asyncio
async def test_criar_direto_sem_rascunho_numera_na_hora(admin_engine, cen):
    """`rascunho` ausente (default False) preserva o comportamento de hoje —
    não é uma mudança silenciosa pra quem não pediu rascunho."""
    t = cen["tenant"]
    _as_operador(admin_engine, cen["operador"], t.id, t.slug)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/v2/processos",
            json={
                "id_assunto": cen["assunto"],
                "id_manifestante": cen["manifestante"],
                "id_unidade_proprietaria": cen["origem"],
            },
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["numero_processo"] is not None
    assert body["situacao"] == "protocolado"


@pytest.mark.asyncio
async def test_check_constraint_barra_situacao_inconsistente(admin_engine, cen):
    """O CHECK do banco (`ck_processo_situacao_numero`) é o único mecanismo
    que hoje garante o invariante — sem teste, uma migration futura poderia
    derrubá-lo sem ninguém notar."""
    t = cen["tenant"]

    async with _sm(admin_engine)() as s:
        rascunho_com_numero = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo="P000999/2026",
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add(rascunho_com_numero)
        with pytest.raises(IntegrityError, match="ck_processo_situacao_numero"):
            await s.flush()
        await s.rollback()

    async with _sm(admin_engine)() as s:
        protocolado_sem_numero = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="protocolado", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add(protocolado_sem_numero)
        with pytest.raises(IntegrityError, match="ck_processo_situacao_numero"):
            await s.flush()
        await s.rollback()


@pytest.mark.asyncio
async def test_emitir_numero_e_idempotente(admin_engine, cen):
    """Segunda chamada sobre processo já numerado não faz nada — chamador
    não precisa checar `situacao` antes de chamar."""
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        p = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add(p)
        await s.flush()
        tenant_row = t
        await emitir_numero(
            s, p, tenant=tenant_row, usuario_id=cen["operador"], now=datetime.now()
        )
        primeiro_numero = p.numero_processo
        assert primeiro_numero is not None

        await emitir_numero(
            s, p, tenant=tenant_row, usuario_id=cen["operador"], now=datetime.now()
        )
        assert p.numero_processo == primeiro_numero
        await s.rollback()


@pytest.mark.asyncio
async def test_pdf_recusa_gerar_para_rascunho(admin_engine, cen):
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        p = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add(p)
        await s.commit()
        await s.refresh(p)
        pid = p.id

    _as_operador(admin_engine, cen["operador"], t.id, t.slug)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get(f"/api/v2/processos/{pid}/capa.pdf")
        assert r.status_code == 409, r.text
    finally:
        async with _sm(admin_engine)() as s:
            await s.execute(
                text("DELETE FROM protocolos.processo WHERE id=:p"), {"p": pid}
            )
            await s.commit()


@pytest.mark.asyncio
async def test_listagem_exclui_rascunho_por_padrao_e_filtro_devolve(admin_engine, cen):
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        rascunho = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        protocolado = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo="P000998/2026",
            situacao="protocolado", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add_all([rascunho, protocolado])
        await s.commit()
        await s.refresh(rascunho)
        await s.refresh(protocolado)

    _as_operador(admin_engine, cen["operador"], t.id, t.slug)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r_default = await client.get("/api/v2/processos", params={"page_size": 100})
            ids_default = {i["id"] for i in r_default.json()["items"]}
            assert rascunho.id not in ids_default
            assert protocolado.id in ids_default

            r_rascunho = await client.get(
                "/api/v2/processos", params={"page_size": 100, "situacao": "rascunho"}
            )
            ids_rascunho = {i["id"] for i in r_rascunho.json()["items"]}
            assert ids_rascunho == {rascunho.id}

            r_todos = await client.get(
                "/api/v2/processos", params={"page_size": 100, "situacao": "todos"}
            )
            ids_todos = {i["id"] for i in r_todos.json()["items"]}
            assert {rascunho.id, protocolado.id} <= ids_todos
    finally:
        async with _sm(admin_engine)() as s:
            for pid in (rascunho.id, protocolado.id):
                await s.execute(
                    text("DELETE FROM protocolos.processo WHERE id=:p"), {"p": pid}
                )
            await s.commit()


@pytest.mark.asyncio
async def test_apensar_rascunho_e_recusado(admin_engine, cen):
    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        rascunho = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        principal = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo="P000997/2026",
            situacao="protocolado", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add_all([rascunho, principal])
        await s.commit()
        await s.refresh(rascunho)
        await s.refresh(principal)

    try:
        async with _sm(admin_engine)() as s:
            with pytest.raises(ApensamentoError, match="rascunho"):
                await apensar(
                    s, tenant_id=t.id, usuario_id=cen["operador"],
                    id_processo_apensado=rascunho.id,
                    id_processo_principal=principal.id, motivo="teste",
                )
    finally:
        async with _sm(admin_engine)() as s:
            for pid in (rascunho.id, principal.id):
                await s.execute(
                    text("DELETE FROM protocolos.processo WHERE id=:p"), {"p": pid}
                )
            await s.commit()


@pytest.mark.asyncio
async def test_cidadao_nao_ve_rascunho_do_mesmo_manifestante(admin_engine, cen):
    """Achado do desenho original: o portal lista por CPF do manifestante,
    não por quem abriu — um rascunho aberto internamente pro mesmo
    manifestante vazaria sem o filtro em `_base_select`
    (services/cidadao_processos.py)."""
    from app.models import UsuarioExterno

    t = cen["tenant"]
    async with _sm(admin_engine)() as s:
        manif = (
            await s.execute(select(Manifestante).where(Manifestante.id == cen["manifestante"]))
        ).scalar_one()
        rascunho = Processo(
            tenant_id=t.id, id_assunto=cen["assunto"], virtual=True,
            data_hora_abertura=datetime.now(), numero_processo=None,
            situacao="rascunho", id_unidade_proprietaria=cen["origem"],
            id_manifestante=cen["manifestante"], nivel_sigilo="ostensivo",
            ativo=True, excluido=False,
        )
        s.add(rascunho)
        await s.commit()
        await s.refresh(rascunho)

        cidadao = UsuarioExterno(
            tenant_id=t.id, cpf_cnpj=manif.cpf_cnpj, nome="Maria Cidadã",
            email=f"cid-{uuid.uuid4().hex[:8]}@e3.test", senha="", ativo=True,
            excluido=False, uid=uuid.uuid4(), data_criacao=datetime.now(),
        )
        s.add(cidadao)
        await s.commit()
        await s.refresh(cidadao)

        try:
            vistos = await listar_meus(s, cidadao, tenant_id=t.id)
            assert rascunho.id not in {p.id for p in vistos}
        finally:
            await s.execute(
                text("DELETE FROM protocolos.processo WHERE id=:p"), {"p": rascunho.id}
            )
            await s.execute(
                text("DELETE FROM utils.usuario_externo WHERE id=:u"), {"u": cidadao.id}
            )
            await s.commit()

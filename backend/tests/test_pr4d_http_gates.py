"""PR 4d-fix — Testes HTTP de autorização/permissão para complementação.

Testa os 5 endpoints do PR 4d via FastAPI ASGI (sem rede real) usando
`app.dependency_overrides` para forçar identidade e tenant, em vez de
emitir JWT/Host reais. Foco: gates `require_permission("processo","atualizar")`,
`require_acesso_processo` (servidor) e `_verificar_dono` (cidadão).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import (
    get_current_cidadao,
    get_current_user,
    require_tenant_id,
    require_tenant_slug,
)
from app.main import app
from app.models import Servico, UsuarioExterno
from app.schemas.cidadao import AbrirPorServicoRequest
from app.schemas.servico import ServicoCreate
from app.services import complementacao_documental as comp_svc
from app.services import servico as servico_svc
from app.services.cidadao_processos import abrir_processo_por_servico
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine, *, prefix="pr4dhttp"):
    slug = _slug(prefix)
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref HTTP", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _unidade_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.unidade_trabalho WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _su_id(engine, tenant_id: int) -> int:
    """Id do super-usuário do tenant (criado por `provisionar_tenant`)."""
    async with _sm(engine)() as s:
        return int((await s.execute(
            text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
            {"t": tenant_id},
        )).scalar_one())


async def _criar_servidor_sem_perm(engine, tenant_id: int) -> int:
    """Cria um servidor neste tenant SEM grupo SU e SEM transação
    'processo' — fica sem permissão de atualizar processo."""
    async with _sm(engine)() as s:
        # Sem id_unidade_trabalho específico (não relevante aqui).
        uid = int((await s.execute(
            text(
                "INSERT INTO utils.usuario (tenant_id, nome, email, senha, "
                "cpf, data_criacao, id_unidade_trabalho, ativo, excluido, uid) "
                "VALUES (:t, 'Sem Perm', :e, '', :c, NOW(), :u, true, false, "
                "gen_random_uuid()) RETURNING id"
            ),
            {
                "t": tenant_id,
                "e": f"sem-perm-{uuid.uuid4().hex[:8]}@t.local",
                "c": uuid.uuid4().hex[:11],
                "u": await _unidade_id(engine, tenant_id),
            },
        )).scalar_one())
        await s.commit()
    return uid


async def _criar_assunto(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        await s.execute(text(
            "INSERT INTO protocolos.tipo_processo "
            "(tenant_id, tipo_processo, exige_processo_pai, ativo, excluido) "
            "VALUES (:t, 'Geral', false, true, false) RETURNING id"
        ), {"t": tenant_id})
        tpid = int((await s.execute(text(
            "SELECT id FROM protocolos.tipo_processo WHERE tenant_id=:t "
            "ORDER BY id DESC LIMIT 1"
        ), {"t": tenant_id})).scalar_one())
        aid = int((await s.execute(text(
            "INSERT INTO protocolos.assunto "
            "(tenant_id, assunto, id_tipo_processo, exige_processo_pai, "
            "ativo, excluido) "
            "VALUES (:t, 'Sol', :tp, false, true, false) RETURNING id"
        ), {"t": tenant_id, "tp": tpid})).scalar_one())
        await s.commit()
    return aid


async def _criar_cidadao(engine, tenant_id: int, cpf: str | None = None) -> int:
    cpf = cpf or uuid.uuid4().hex[:11]
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id, nome="Maria", cpf_cnpj=cpf, email="m@x",
            ativo=True, excluido=False, uid=uuid.uuid4(),
            data_criacao=datetime.now(), login_govbr=False,
            telefone_whatsapp=False,
        )
        s.add(c); await s.commit()
        return c.id


async def _abrir_processo(engine, tenant, sv_id: int, cid: int) -> int:
    async with _sm(engine)() as s:
        cidadao = (await s.execute(
            select(UsuarioExterno).where(UsuarioExterno.id == cid)
        )).scalar_one()
        servico = (await s.execute(
            select(Servico).where(Servico.id == sv_id)
        )).scalar_one()
        p = await abrir_processo_por_servico(
            s, cidadao, servico,
            AbrirPorServicoRequest(corpo="Pedido de teste."),
            tenant_id=tenant.id,
        )
        return p.id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM protocolos.complementacao_documental WHERE tenant_id=:t",
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id=:t",
            "DELETE FROM protocolos.processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.anexo WHERE tenant_id=:t",
            "DELETE FROM protocolos.servico WHERE tenant_id=:t",
            "DELETE FROM protocolos.assunto WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id=:t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_externo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest_asyncio.fixture
async def http_setup(admin_engine):
    """Provisiona tenant A com SU, servidor sem-perm e cidadão dono;
    serviço com docs; processo aberto + complementação aberta."""
    tenant = await _provisionar(admin_engine)
    su_id = await _su_id(admin_engine, tenant.id)
    sem_perm_id = await _criar_servidor_sem_perm(admin_engine, tenant.id)
    uid = await _unidade_id(admin_engine, tenant.id)
    id_assunto = await _criar_assunto(admin_engine, tenant.id)
    async with _sm(admin_engine)() as s:
        sv = await servico_svc.criar_servico(
            s, tenant_id=tenant.id, payload=ServicoCreate(
                nome="X", slug=_slug("sv-"),
                id_assunto_padrao=id_assunto,
                id_unidade_responsavel=uid,
                documentos_exigidos=[
                    {"nome": "RG", "obrigatorio": True},
                    {"nome": "CPF", "obrigatorio": True},
                ],
            ),
        )
    dono_cpf = uuid.uuid4().hex[:11]
    dono_id = await _criar_cidadao(admin_engine, tenant.id, dono_cpf)
    alheio_cpf = uuid.uuid4().hex[:11]
    alheio_id = await _criar_cidadao(admin_engine, tenant.id, alheio_cpf)
    pid = await _abrir_processo(admin_engine, tenant, sv.id, dono_id)
    # Abre uma complementação para testar listar/responder
    async with _sm(admin_engine)() as s:
        comp = await comp_svc.solicitar(
            s, tenant_id=tenant.id, processo_id=pid,
            id_usuario_solicitante=su_id, mensagem="Envie RG e CPF.",
            documentos_solicitados_keys=["rg"],
        )
        await s.commit()
    try:
        yield {
            "tenant_id": tenant.id,
            "tenant_slug": tenant.slug,
            "su_id": su_id,
            "sem_perm_id": sem_perm_id,
            "processo_id": pid,
            "complementacao_id": comp.id,
            "dono_id": dono_id,
            "dono_cpf": dono_cpf,
            "alheio_id": alheio_id,
            "alheio_cpf": alheio_cpf,
        }
    finally:
        await _cleanup(admin_engine, tenant.id)


def _as_servidor(admin_engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    """Builder para overrides do FastAPI emulando JWT de servidor."""

    async def _get_user():
        async with _sm(admin_engine)() as s:
            from app.models import Usuario
            user = (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id)
            )).scalar_one()
            return user

    def _setup():
        app.dependency_overrides[get_current_user] = _get_user
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup


def _as_cidadao(admin_engine, cidadao_id: int, tenant_id: int, tenant_slug: str):
    """Builder para overrides emulando JWT de cidadão."""

    async def _get_cid():
        async with _sm(admin_engine)() as s:
            cid = (await s.execute(
                select(UsuarioExterno).where(UsuarioExterno.id == cidadao_id)
            )).scalar_one()
            return cid

    def _setup():
        app.dependency_overrides[get_current_cidadao] = _get_cid
        app.dependency_overrides[require_tenant_id] = lambda: tenant_id
        app.dependency_overrides[require_tenant_slug] = lambda: tenant_slug

    return _setup


def _clear_overrides():
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    _clear_overrides()
    # pytest-asyncio cria event loop novo por função; o engine global da app
    # acumula conexões asyncpg ligadas ao loop morto. dispose() entre testes
    # evita "Event loop is closed" no próximo teste.
    from app.database import engine as app_engine
    await app_engine.dispose()


# ============ Servidor ============

async def test_http_servidor_su_solicita_complementacao_201(admin_engine, http_setup, client):
    """Servidor SU (bypass de permissão) abre nova complementação via HTTP."""
    s = http_setup
    # Cancela a aberta primeiro p/ poder abrir nova
    async with _sm(admin_engine)() as sess:
        await comp_svc.cancelar(
            sess, tenant_id=s["tenant_id"], processo_id=s["processo_id"],
            complementacao_id=s["complementacao_id"],
            id_usuario_responsavel=s["su_id"], motivo=None,
        )
        await sess.commit()
    _as_servidor(admin_engine, s["su_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/processos/{s['processo_id']}/complementacoes",
        json={"mensagem": "Envie", "documentos_solicitados": ["cpf"]},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "aberta"
    assert any(d["key"] == "cpf" for d in body["documentos_solicitados"])


async def test_http_servidor_sem_processo_atualizar_403_solicitar(
    admin_engine, http_setup, client
):
    """Servidor sem permissão `processo:atualizar` recebe 403 ao solicitar."""
    s = http_setup
    _as_servidor(admin_engine, s["sem_perm_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/processos/{s['processo_id']}/complementacoes",
        json={"mensagem": "x", "documentos_solicitados": ["cpf"]},
    )
    assert r.status_code == 403


async def test_http_servidor_sem_perm_403_cancelar(
    admin_engine, http_setup, client
):
    """Servidor sem permissão `processo:atualizar` recebe 403 ao cancelar."""
    s = http_setup
    _as_servidor(admin_engine, s["sem_perm_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/processos/{s['processo_id']}/complementacoes/"
        f"{s['complementacao_id']}/cancelar",
        json={"motivo": None},
    )
    assert r.status_code == 403


async def test_http_servidor_su_outro_tenant_nao_acessa(
    admin_engine, http_setup, client
):
    """Servidor SU do tenant B não acessa processo do tenant A — 404
    (require_acesso_processo dispara via tenant filter)."""
    s = http_setup
    tenant_b = await _provisionar(admin_engine, prefix="pr4dhttpB")
    try:
        su_b = await _su_id(admin_engine, tenant_b.id)
        _as_servidor(admin_engine, su_b, tenant_b.id, tenant_b.slug)()
        r = await client.get(
            f"/api/v2/processos/{s['processo_id']}/complementacoes",
        )
        # Cross-tenant: processo não existe sob tenant B
        assert r.status_code == 404
    finally:
        await _cleanup(admin_engine, tenant_b.id)


async def test_http_servidor_lista_complementacoes_200(
    admin_engine, http_setup, client
):
    s = http_setup
    _as_servidor(admin_engine, s["su_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get(
        f"/api/v2/processos/{s['processo_id']}/complementacoes",
    )
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list) and len(arr) >= 1
    assert arr[0]["id"] == s["complementacao_id"]


# ============ Cidadão ============

async def test_http_cidadao_dono_lista_complementacoes_200(
    admin_engine, http_setup, client
):
    s = http_setup
    _as_cidadao(admin_engine, s["dono_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes",
    )
    assert r.status_code == 200
    arr = r.json()
    assert len(arr) == 1
    assert arr[0]["status"] == "aberta"


async def test_http_cidadao_alheio_lista_404(admin_engine, http_setup, client):
    """Cidadão alheio não vê complementação de processo de outro cidadão."""
    s = http_setup
    _as_cidadao(admin_engine, s["alheio_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.get(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes",
    )
    assert r.status_code == 404


async def test_http_cidadao_alheio_nao_responde_404(admin_engine, http_setup, client):
    """Cidadão alheio não responde complementação de outro cidadão (404
    via `_verificar_dono` — não vaza existência)."""
    s = http_setup
    _as_cidadao(admin_engine, s["alheio_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes/"
        f"{s['complementacao_id']}/responder",
    )
    assert r.status_code == 404


async def test_http_cidadao_dono_responde_200(admin_engine, http_setup, client):
    s = http_setup
    _as_cidadao(admin_engine, s["dono_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes/"
        f"{s['complementacao_id']}/responder",
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "respondida"


async def test_http_cidadao_nao_responde_cancelada_409(
    admin_engine, http_setup, client
):
    """Cidadão dono tenta responder complementação já cancelada → 409."""
    s = http_setup
    # cancela primeiro (via service direto, fora do HTTP)
    async with _sm(admin_engine)() as sess:
        await comp_svc.cancelar(
            sess, tenant_id=s["tenant_id"], processo_id=s["processo_id"],
            complementacao_id=s["complementacao_id"],
            id_usuario_responsavel=s["su_id"], motivo=None,
        )
        await sess.commit()
    _as_cidadao(admin_engine, s["dono_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes/"
        f"{s['complementacao_id']}/responder",
    )
    assert r.status_code == 409


async def test_http_cidadao_nao_responde_respondida_409(
    admin_engine, http_setup, client
):
    """Cidadão dono tenta responder uma já respondida → 409."""
    s = http_setup
    async with _sm(admin_engine)() as sess:
        await comp_svc.responder(
            sess, tenant_id=s["tenant_id"], processo_id=s["processo_id"],
            complementacao_id=s["complementacao_id"],
        )
        await sess.commit()
    _as_cidadao(admin_engine, s["dono_id"], s["tenant_id"], s["tenant_slug"])()
    r = await client.post(
        f"/api/v2/cidadao/processos/{s['processo_id']}/complementacoes/"
        f"{s['complementacao_id']}/responder",
    )
    assert r.status_code == 409

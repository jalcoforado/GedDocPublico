"""Preferência de notificação por evento (fatia F9, benchmark SUiTE).

Plano: `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md`.

Escopo decidido (achado durante a implementação, não estava no plano
original): o único evento hoje endereçado a `utils.usuario` — e portanto o
único em que "preferência do usuário" significa algo — é `sla_estourado`. Os
demais tipos de notificação do sistema (recadastramento.*, denuncia_decidida)
vão para o regulado/denunciante externo, sem `id_usuario`. Ver
`services/notificacoes.py::EVENTOS_NOTIFICACAO`.

O teste que mais importa não é o CRUD de preferência — é `test_enviar_respeita_
preferencia_por_evento`: prova que `enviar()` de fato lê a tabela nova, não só
que o endpoint grava nela.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import Usuario
from app.services.notificacoes import (
    Destinatario,
    EventoDesconhecidoError,
    enviar,
    listar_preferencias,
    set_preferencia_evento,
)
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _provisionar(engine):
    slug = f"f9-{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s,
            slug=slug,
            nome="Pref F9",
            admin_email=f"{slug}@e2e.test",
            admin_nome="Adm",
            admin_cpf=uuid.uuid4().hex[:11],
            plano="basico",
        )
    return tenant


async def _admin_do_tenant(engine, tenant_id: int) -> Usuario:
    async with _sm(engine)() as s:
        return (
            await s.execute(select(Usuario).where(Usuario.tenant_id == tenant_id))
        ).scalars().first()


async def _cleanup(engine, tenant_id: int) -> None:
    """Higiene do app entre testes: solta os `dependency_overrides` e descarta o pool do engine
    global (senão ele sobrevive ao event loop do teste e o seguinte quebra). Os dados do tenant
    saem em `_limpa_tenants_do_modulo` (conftest); os parâmetros ficam só para não mexer nos
    pontos de chamada."""
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()


@pytest.mark.asyncio
async def test_listar_preferencias_traz_defaults_sem_row(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            linhas = await listar_preferencias(s, tenant_id=tenant.id, id_usuario=admin.id)
        assert len(linhas) == 1  # só o catálogo real: sla_estourado
        linha = linhas[0]
        assert linha["evento"] == "sla_estourado"
        assert linha["in_app"] is True
        assert linha["email"] is True
        assert linha["whatsapp"] is False  # DEFAULT_PREFS
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_set_preferencia_evento_upsert_e_persiste(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            linha = await set_preferencia_evento(
                s, tenant_id=tenant.id, id_usuario=admin.id,
                evento="sla_estourado", whatsapp=True,
            )
        assert linha["whatsapp"] is True
        assert linha["in_app"] is True  # não mexido, mantém default

        # Segunda chamada: idempotente no sentido de não duplicar a linha.
        async with _sm(admin_engine)() as s:
            await set_preferencia_evento(
                s, tenant_id=tenant.id, id_usuario=admin.id,
                evento="sla_estourado", in_app=False,
            )
        async with _sm(admin_engine)() as s:
            n = (
                await s.execute(
                    text(
                        "SELECT count(*) FROM aprimora_py.notificacao_preferencia_evento "
                        "WHERE tenant_id=:t AND id_usuario=:u"
                    ),
                    {"t": tenant.id, "u": admin.id},
                )
            ).scalar_one()
        assert n == 1

        async with _sm(admin_engine)() as s:
            linhas = await listar_preferencias(s, tenant_id=tenant.id, id_usuario=admin.id)
        linha = linhas[0]
        assert linha["in_app"] is False
        assert linha["whatsapp"] is True  # preservado da chamada anterior
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_set_preferencia_evento_desconhecido_levanta(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(EventoDesconhecidoError):
                await set_preferencia_evento(
                    s, tenant_id=tenant.id, id_usuario=admin.id,
                    evento="evento_que_nao_existe",
                )
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_enviar_respeita_preferencia_por_evento(admin_engine):
    """O teste que prova o motivo de existir a tabela nova: desligar
    `whatsapp` só para `sla_estourado` não gera notificação nesse canal,
    mas continua gerando em `in_app`/`email` — e um evento HIPOTÉTICO
    diferente (mesmo usuário) não seria afetado por essa preferência, porque
    a chave agora é (usuário, evento), não só usuário."""
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await set_preferencia_evento(
                s, tenant_id=tenant.id, id_usuario=admin.id,
                evento="sla_estourado", whatsapp=False,
            )

        async with _sm(admin_engine)() as s:
            criadas = await enviar(
                s,
                tenant_id=tenant.id,
                destinatarios=[Destinatario(id_usuario=admin.id)],
                canais=["in_app", "email", "whatsapp"],
                tipo="sla_estourado",
                titulo="SLA estourado",
                mensagem="teste",
            )
        canais_criados = sorted(n.canal for n in criadas)
        assert canais_criados == ["email", "in_app"]  # whatsapp filtrado
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _client_como(engine, usuario_id: int, tenant_id: int, tenant_slug: str):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, tenant_slug)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_http_get_preferencias_lista_o_catalogo(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _client_como(admin_engine, admin.id, tenant.id, tenant.slug) as client:
            r = await client.get("/api/v2/notificacoes/preferencias")
            assert r.status_code == 200, r.text
            body = r.json()
            assert len(body) == 1
            assert body[0]["evento"] == "sla_estourado"
            assert body[0]["label"]
    finally:
        app.dependency_overrides.clear()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_put_preferencia_evento_atualiza(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _client_como(admin_engine, admin.id, tenant.id, tenant.slug) as client:
            r = await client.put(
                "/api/v2/notificacoes/preferencias/sla_estourado",
                json={"whatsapp": True},
            )
            assert r.status_code == 200, r.text
            assert r.json()["whatsapp"] is True
    finally:
        app.dependency_overrides.clear()
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_http_put_preferencia_evento_desconhecido_e_404(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        admin = await _admin_do_tenant(admin_engine, tenant.id)
        async with _client_como(admin_engine, admin.id, tenant.id, tenant.slug) as client:
            r = await client.put(
                "/api/v2/notificacoes/preferencias/evento_que_nao_existe",
                json={"whatsapp": True},
            )
            assert r.status_code == 404, r.text
    finally:
        app.dependency_overrides.clear()
        await _cleanup(admin_engine, tenant.id)

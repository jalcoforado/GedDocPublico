"""Transporte Regulado P3.2 — Responsáveis de Alvarás.

Cobre adição, leitura e remoção de responsáveis (usuários do sistema) vinculados
a alvarás com isolamento RLS tenant-scoped, validação de FK para alvará/usuário,
e soft-delete.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraResponsavelCreate,
    PermissionarioCreate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("alvresp")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Alv Resp", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


async def _permissionario(admin_engine, tenant_id):
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome="Permissionário", cpf=_cpf(), tipo_servico="taxi",
            ),
        )


async def _alvara(admin_engine, tenant_id):
    perm = await _permissionario(admin_engine, tenant_id)
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_alvara(
            s, tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=f"ALV-{uuid.uuid4().hex[:8].upper()}",
                data_validade=datetime.utcnow().date() + timedelta(days=365),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )


async def _usuario_admin(admin_engine, tenant_id):
    """Obter um usuário ativo da tenant para usar como responsável."""
    async with _sm(admin_engine)() as s:
        from sqlalchemy import select
        from app.models import Usuario

        # Obter primeiro usuário ativo da tenant
        stmt = select(Usuario).where(Usuario.ativo.is_(True)).limit(1)
        result = (await s.execute(stmt)).scalar_one_or_none()
        return result


# ========================= Testes de Responsáveis =============================


@pytest.mark.asyncio
async def test_alvara_responsavel_adicionar_basico(admin_engine):
    """Adicionar usuário como responsável de alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(
                id_usuario=usuario.id,
                cargo_funcao="Gerente",
            ),
        )

    assert resp.id is not None
    assert resp.tenant_id == tenant.id
    assert resp.id_alvara == alvara.id
    assert resp.id_usuario == usuario.id
    assert resp.cargo_funcao == "Gerente"
    assert resp.excluido is False


@pytest.mark.asyncio
async def test_alvara_responsavel_adicionar_sem_cargo(admin_engine):
    """Adicionar responsável sem cargo_funcao (opcional)."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(id_usuario=usuario.id),
        )

    assert resp.cargo_funcao is None


@pytest.mark.asyncio
async def test_alvara_responsavel_adicionar_alvara_nao_existe(admin_engine):
    """Adicionar responsável para alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.adicionar_responsavel(
                s, tenant_id=tenant.id, alvara_id=99999,
                payload=AlvaraResponsavelCreate(id_usuario=usuario.id),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_responsavel_adicionar_usuario_nao_existe(admin_engine):
    """Adicionar responsável com usuário inexistente retorna erro."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        # Pode ser HTTPException ou IntegrityError (FK constraint violation)
        try:
            await tr_svc.adicionar_responsavel(
                s, tenant_id=tenant.id, alvara_id=alvara.id,
                payload=AlvaraResponsavelCreate(id_usuario=99999),
            )
            # Se não houver erro, falhar o teste
            pytest.fail("Expected exception when adding non-existent user")
        except (HTTPException, Exception) as e:
            # FK violation is expected
            pass


@pytest.mark.asyncio
async def test_alvara_responsavel_obter_basico(admin_engine):
    """Obter responsável por ID."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(
                id_usuario=usuario.id,
                cargo_funcao="Operador",
            ),
        )
        resp_id = resp.id

        obtido = await tr_svc.obter_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)

    assert obtido.id == resp_id
    assert obtido.id_usuario == usuario.id
    assert obtido.cargo_funcao == "Operador"


@pytest.mark.asyncio
async def test_alvara_responsavel_obter_nao_existe(admin_engine):
    """Obter responsável inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_responsavel(s, tenant_id=tenant.id, responsavel_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_responsavel_obter_excluido(admin_engine):
    """Obter responsável soft-deletado retorna 404."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(id_usuario=usuario.id),
        )
        resp_id = resp.id

        # Soft-delete
        await tr_svc.remover_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)

        # Tentar obter
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_responsavel_listar_basico(admin_engine):
    """Listar responsáveis de um alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp1 = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(
                id_usuario=usuario.id,
                cargo_funcao="Gerente",
            ),
        )

        # Mesmo usuário pode ser adicionado novamente? Não — unique constraint
        # Deixa apenas um responsável para este teste

        resps, _ = await tr_svc.listar_responsaveis(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(resps) == 1
    assert resps[0].id == resp1.id


@pytest.mark.asyncio
async def test_alvara_responsavel_listar_vazio(admin_engine):
    """Listar responsáveis de alvará sem responsáveis retorna vazio."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resps, _ = await tr_svc.listar_responsaveis(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(resps) == 0


@pytest.mark.asyncio
async def test_alvara_responsavel_listar_ignora_excluidos(admin_engine):
    """Listar responsáveis ignora soft-deletados."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(id_usuario=usuario.id),
        )
        resp_id = resp.id

        # Soft-delete
        await tr_svc.remover_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)

        resps, _ = await tr_svc.listar_responsaveis(s, tenant_id=tenant.id, alvara_id=alvara.id)

    assert len(resps) == 0


@pytest.mark.asyncio
async def test_alvara_responsavel_remover_basico(admin_engine):
    """Soft-delete responsável de alvará."""
    tenant = await _provisionar(admin_engine)
    alvara = await _alvara(admin_engine, tenant.id)
    usuario = await _usuario_admin(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant.id, alvara_id=alvara.id,
            payload=AlvaraResponsavelCreate(id_usuario=usuario.id),
        )
        resp_id = resp.id

        # Remover
        await tr_svc.remover_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)

        # Verificar que está marcado como excluído
        with pytest.raises(HTTPException):
            await tr_svc.obter_responsavel(s, tenant_id=tenant.id, responsavel_id=resp_id)


@pytest.mark.asyncio
async def test_alvara_responsavel_remover_nao_existe(admin_engine):
    """Remover responsável inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.remover_responsavel(s, tenant_id=tenant.id, responsavel_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_responsavel_rls_cross_tenant(admin_engine):
    """RLS: Responsável de um tenant não visível em outro."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    alvara1 = await _alvara(admin_engine, tenant1.id)
    usuario1 = await _usuario_admin(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        resp = await tr_svc.adicionar_responsavel(
            s, tenant_id=tenant1.id, alvara_id=alvara1.id,
            payload=AlvaraResponsavelCreate(id_usuario=usuario1.id),
        )
        resp_id = resp.id

    # Tentar acessar como tenant2
    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_responsavel(s, tenant_id=tenant2.id, responsavel_id=resp_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_responsavel_listar_alvara_nao_existe(admin_engine):
    """Listar responsáveis de alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.listar_responsaveis(s, tenant_id=tenant.id, alvara_id=99999)

    assert exc.value.status_code == 404

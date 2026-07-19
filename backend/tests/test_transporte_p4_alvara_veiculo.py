"""Transporte P4.1 — Integração Veicular: alvará ↔ múltiplos veículos.

Cobre o serviço de domínio (`services/transporte_regulado.py`): vínculo de
veículos a alvarás, isolamento cross-tenant, testes de duplicata, listagem.
Padrão: provisionar_tenant + admin_engine (como Frota PR-6).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import AlvaraVeiculoCreate
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("p4v")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref P4 Veiculo", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _criar_permissionario(engine, tenant_id: int, cpf: str = None):
    """Helper: cria permissionário para vincular empresa."""
    from app.schemas.transporte_regulado import PermissionarioCreate

    if cpf is None:
        import random
        cpf = "".join(str(random.randint(0, 9)) for _ in range(11))

    async with _sm(engine)() as db:
        perm = await tr_svc.criar_permissionario(
            db,
            tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome="Perm Teste", cpf=cpf, telefone="1199999999", email="perm@t.local",
                tipo_servico="taxi"
            ),
        )
    return perm.id


async def _criar_empresa(engine, tenant_id: int, cnpj: str = None):
    """Helper: cria empresa."""
    from app.schemas.transporte_regulado import EmpresaCreate
    import random

    if cnpj is None:
        cnpj = "".join(str(random.randint(0, 9)) for _ in range(14))

    async with _sm(engine)() as db:
        empresa = await tr_svc.criar_empresa(
            db,
            tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social="Empresa Teste", cnpj=cnpj, email="emp@t.local", telefone="1199999999",
                tipo_servico="taxi"
            ),
        )
    return empresa.id


async def _criar_veiculo(engine, tenant_id: int, empresa_id: int, placa: str = None):
    """Helper: cria veículo."""
    from app.schemas.transporte_regulado import VeiculoReguladoCreate

    if placa is None:
        placa = f"AAA{uuid.uuid4().hex[:4].upper()}"

    async with _sm(engine)() as db:
        v = await tr_svc.criar_veiculo(
            db,
            tenant_id=tenant_id,
            payload=VeiculoReguladoCreate(
                placa=placa, tipo="taxi", id_empresa=empresa_id, cor="branco",
                marca="Toyota", modelo="Corolla", tipo_servico="taxi"
            ),
        )
    return v.id


async def _criar_alvara(engine, tenant_id: int, perm_id: int, numero: str = None):
    """Helper: cria alvará."""
    from app.schemas.transporte_regulado import AlvaraCreate
    from datetime import date

    if numero is None:
        numero = f"ALV-{uuid.uuid4().hex[:6].upper()}"

    async with _sm(engine)() as db:
        a = await tr_svc.criar_alvara(
            db,
            tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=numero,
                tipo_servico="taxi",
                id_permissionario=perm_id,
                data_inicio=date.today(),
                data_validade=None,
            ),
        )
    return a.id


@pytest.mark.asyncio
async def test_vincular_veiculo_alvara(admin_engine):
    """Vincular um veículo a um alvará."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    empresa_id = await _criar_empresa(admin_engine, tenant.id)
    veiculo_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        av = await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=veiculo_id
        )

        assert av.id_alvara == alvara_id
        assert av.id_veiculo == veiculo_id
        assert av.tenant_id == tenant.id


@pytest.mark.asyncio
async def test_vincular_veiculo_duplicado_retorna_409(admin_engine):
    """Vincular veículo já vinculado retorna 409."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    empresa_id = await _criar_empresa(admin_engine, tenant.id)
    veiculo_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Primeiro vínculo OK
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=veiculo_id
        )

        # Segundo vínculo deve retornar 409
        with pytest.raises(HTTPException) as exc_info:
            await tr_svc.vincular_veiculo_alvara(
                db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=veiculo_id
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_vincular_veiculo_inexistente_retorna_404(admin_engine):
    """Vincular veículo que não existe retorna 404."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as exc_info:
            await tr_svc.vincular_veiculo_alvara(
                db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=99999
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_desvincular_veiculo_alvara(admin_engine):
    """Desvincular um veículo de um alvará."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    empresa_id = await _criar_empresa(admin_engine, tenant.id)
    veiculo_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Vincular
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=veiculo_id
        )

        # Desvincular
        await tr_svc.desvincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=veiculo_id
        )

        # Verificar que foi deletado
        veiculos = await tr_svc.listar_veiculos_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id
        )
        assert len(veiculos) == 0


@pytest.mark.asyncio
async def test_desvincular_inexistente_retorna_404(admin_engine):
    """Desvincular vínculo que não existe retorna 404."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as exc_info:
            await tr_svc.desvincular_veiculo_alvara(
                db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=99999
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_listar_veiculos_alvara(admin_engine):
    """Listar veículos vinculados a um alvará."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    empresa_id = await _criar_empresa(admin_engine, tenant.id)
    alvara_id = await _criar_alvara(admin_engine, tenant.id, perm_id)

    # Criar 3 veículos
    v1_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id, placa="AAA0001")
    v2_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id, placa="AAA0002")
    v3_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id, placa="AAA0003")

    async with _sm(admin_engine)() as db:
        # Vincular 2 dos 3
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=v1_id
        )
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, veiculo_id=v2_id
        )

        # Listar
        veiculos = await tr_svc.listar_veiculos_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id
        )

        assert len(veiculos) == 2
        ids = {v.id_veiculo for v in veiculos}
        assert v1_id in ids
        assert v2_id in ids
        assert v3_id not in ids


@pytest.mark.asyncio
async def test_listar_alvaras_veiculo(admin_engine):
    """Listar alvarás vinculados a um veículo."""
    tenant = await _provisionar(admin_engine)
    perm_id = await _criar_permissionario(admin_engine, tenant.id)
    empresa_id = await _criar_empresa(admin_engine, tenant.id)
    veiculo_id = await _criar_veiculo(admin_engine, tenant.id, empresa_id)

    # Criar 3 alvarás
    a1_id = await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-0001")
    a2_id = await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-0002")
    a3_id = await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-0003")

    async with _sm(admin_engine)() as db:
        # Vincular veículo a 2 dos 3
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=a1_id, veiculo_id=veiculo_id
        )
        await tr_svc.vincular_veiculo_alvara(
            db, tenant_id=tenant.id, alvara_id=a2_id, veiculo_id=veiculo_id
        )

        # Listar
        alvaras = await tr_svc.listar_alvaras_veiculo(
            db, tenant_id=tenant.id, veiculo_id=veiculo_id
        )

        assert len(alvaras) == 2
        ids = {a.id_alvara for a in alvaras}
        assert a1_id in ids
        assert a2_id in ids
        assert a3_id not in ids


@pytest.mark.asyncio
async def test_cross_tenant_isolation_vincular(admin_engine):
    """Cross-tenant: não vincular veículo de outro tenant."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)

    perm1_id = await _criar_permissionario(admin_engine, tenant1.id)
    empresa2_id = await _criar_empresa(admin_engine, tenant2.id)
    veiculo2_id = await _criar_veiculo(admin_engine, tenant2.id, empresa2_id)
    alvara1_id = await _criar_alvara(admin_engine, tenant1.id, perm1_id)

    async with _sm(admin_engine)() as db:
        # Tentar vincular veículo de tenant2 a alvará de tenant1
        with pytest.raises(HTTPException) as exc_info:
            await tr_svc.vincular_veiculo_alvara(
                db, tenant_id=tenant1.id, alvara_id=alvara1_id, veiculo_id=veiculo2_id
            )
        assert exc_info.value.status_code == 404

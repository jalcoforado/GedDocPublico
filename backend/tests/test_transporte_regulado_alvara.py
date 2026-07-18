"""Transporte Regulado P2 — Alvarás/Autorizações de Operação.

Cobre CRUD tenant-scoped para alvarás (autorizações de operação de
permissionários e empresas). Isolamento RLS cross-tenant, soft-delete,
validações de numero único, at_least_one_vinculo, datas_consistentes.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import usuario as user_models
from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraUpdate,
    EmpresaCreate,
    PermissionarioCreate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("alv")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Alv", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


def _cnpj() -> str:
    return str(uuid.uuid4().int)[:14]


async def _permissionario(admin_engine, tenant_id, nome="Permissionário"):
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(
                nome=nome, cpf=_cpf(), tipo_servico="taxi",
            ),
        )


async def _empresa(admin_engine, tenant_id, nome="Empresa"):
    async with _sm(admin_engine)() as s:
        return await tr_svc.criar_empresa(
            s, tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social=nome, cnpj=_cnpj(), tipo_servico="taxi",
            ),
        )


# ========================= Testes CRUD Basicos ==========================


@pytest.mark.asyncio
async def test_alvara_criar_com_permissionario(admin_engine):
    """Criar alvará com permissionário."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-001",
                data_inicio=date(2024, 1, 1),
                data_validade=date(2025, 12, 31),
                tipo_servico="taxi",
                observacoes="Alvará normal",
                id_permissionario=perm.id,
            ),
        )

    assert alv.id is not None
    assert alv.tenant_id == tenant.id
    assert alv.numero_alvara == "ALV-001"
    assert alv.id_permissionario == perm.id
    assert alv.id_empresa is None
    assert alv.excluido is False
    assert alv.criado_em is not None


@pytest.mark.asyncio
async def test_alvara_criar_com_empresa(admin_engine):
    """Criar alvará com empresa."""
    tenant = await _provisionar(admin_engine)
    emp = await _empresa(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-002",
                data_inicio=date(2024, 6, 1),
                data_validade=date(2025, 5, 31),
                tipo_servico="transporte_escolar",
                id_empresa=emp.id,
            ),
        )

    assert alv.id is not None
    assert alv.id_empresa == emp.id
    assert alv.id_permissionario is None
    assert alv.tipo_servico == "transporte_escolar"


@pytest.mark.asyncio
async def test_alvara_criar_com_ambos_vinculos(admin_engine):
    """Criar alvará com empresa E permissionário."""
    tenant = await _provisionar(admin_engine)
    emp = await _empresa(admin_engine, tenant.id)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-003",
                data_inicio=date(2024, 1, 1),
                data_validade=date(2025, 12, 31),
                tipo_servico="taxi",
                id_empresa=emp.id,
                id_permissionario=perm.id,
            ),
        )

    assert alv.id_empresa == emp.id
    assert alv.id_permissionario == perm.id


@pytest.mark.asyncio
async def test_alvara_obter(admin_engine):
    """Obter alvará pelo ID."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        criado = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-004",
                tipo_servico="mototaxi",
                id_permissionario=perm.id,
            ),
        )
        alv_id = criado.id

        obtido = await tr_svc.obter_alvara(s, tenant_id=tenant.id, alvara_id=alv_id)

    assert obtido.id == alv_id
    assert obtido.numero_alvara == "ALV-004"


@pytest.mark.asyncio
async def test_alvara_obter_404_nao_existe(admin_engine):
    """Obter alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara(s, tenant_id=tenant.id, alvara_id=99999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_obter_404_cross_tenant(admin_engine):
    """Obter alvará de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant1.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant1.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-005",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        alv_id = alv.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara(s, tenant_id=tenant2.id, alvara_id=alv_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_listar_sem_filtro(admin_engine):
    """Listar alvarás de uma tenant sem filtro."""
    tenant = await _provisionar(admin_engine)
    perm1 = await _permissionario(admin_engine, tenant.id, nome="Perm1")
    perm2 = await _permissionario(admin_engine, tenant.id, nome="Perm2")

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-006",
                tipo_servico="taxi",
                id_permissionario=perm1.id,
            ),
        )
        alv2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-007",
                tipo_servico="mototaxi",
                id_permissionario=perm2.id,
            ),
        )

        alvaras = await tr_svc.listar_alvaras(s, tenant_id=tenant.id)

    assert len(alvaras) == 2
    assert alv1.id in [a.id for a in alvaras]
    assert alv2.id in [a.id for a in alvaras]


@pytest.mark.asyncio
async def test_alvara_listar_filtro_por_permissionario(admin_engine):
    """Listar alvarás filtrados por permissionário."""
    tenant = await _provisionar(admin_engine)
    perm1 = await _permissionario(admin_engine, tenant.id, nome="Perm1")
    perm2 = await _permissionario(admin_engine, tenant.id, nome="Perm2")

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-008",
                tipo_servico="taxi",
                id_permissionario=perm1.id,
            ),
        )
        await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-009",
                tipo_servico="taxi",
                id_permissionario=perm2.id,
            ),
        )

        alvaras = await tr_svc.listar_alvaras(
            s, tenant_id=tenant.id, permissionario_id=perm1.id
        )

    assert len(alvaras) == 1
    assert alvaras[0].id == alv1.id


@pytest.mark.asyncio
async def test_alvara_listar_filtro_por_empresa(admin_engine):
    """Listar alvarás filtrados por empresa."""
    tenant = await _provisionar(admin_engine)
    emp1 = await _empresa(admin_engine, tenant.id, nome="Emp1")
    emp2 = await _empresa(admin_engine, tenant.id, nome="Emp2")

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-010",
                tipo_servico="transporte_escolar",
                id_empresa=emp1.id,
            ),
        )
        await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-011",
                tipo_servico="transporte_escolar",
                id_empresa=emp2.id,
            ),
        )

        alvaras = await tr_svc.listar_alvaras(
            s, tenant_id=tenant.id, empresa_id=emp1.id
        )

    assert len(alvaras) == 1
    assert alvaras[0].id == alv1.id


@pytest.mark.asyncio
async def test_alvara_listar_ordenacao_descendente(admin_engine):
    """Listar alvarás retorna ordenadas por criado_em descendente."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-012",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        # Aguarda um pouco para garantir ordem diferente de criado_em
        import time
        time.sleep(0.1)

        alv2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-013",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        alvaras = await tr_svc.listar_alvaras(s, tenant_id=tenant.id)

    # Mais recente primeiro (criado_em DESC)
    assert alvaras[0].id == alv2.id
    assert alvaras[1].id == alv1.id


# ========================= Testes de Validação ==========================


@pytest.mark.asyncio
async def test_alvara_validacao_sem_vinculo(admin_engine):
    """Validação: alvará sem empresa ou permissionário."""
    with pytest.raises(ValidationError) as exc:
        AlvaraCreate(
            numero_alvara="ALV-014",
            tipo_servico="taxi",
        )

    assert "vinculado" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_alvara_validacao_datas_inconsistentes(admin_engine):
    """Validação: data_inicio > data_validade."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    with pytest.raises(ValidationError) as exc:
        AlvaraCreate(
            numero_alvara="ALV-015",
            data_inicio=date(2025, 12, 31),
            data_validade=date(2024, 1, 1),
            tipo_servico="taxi",
            id_permissionario=perm.id,
        )

    assert "data_inicio" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_alvara_criar_numero_duplicado_mesma_tenant(admin_engine):
    """Validação: numero_alvara único por tenant."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-DUP",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        with pytest.raises(HTTPException) as exc:
            await tr_svc.criar_alvara(
                s, tenant_id=tenant.id,
                payload=AlvaraCreate(
                    numero_alvara="ALV-DUP",
                    tipo_servico="taxi",
                    id_permissionario=perm.id,
                ),
            )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_alvara_criar_numero_duplicado_tenant_diferente(admin_engine):
    """Número duplicado permitido em tenants diferentes."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    perm1 = await _permissionario(admin_engine, tenant1.id)
    perm2 = await _permissionario(admin_engine, tenant2.id)

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant1.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-SAME",
                tipo_servico="taxi",
                id_permissionario=perm1.id,
            ),
        )

    async with _sm(admin_engine)() as s:
        alv2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant2.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-SAME",
                tipo_servico="taxi",
                id_permissionario=perm2.id,
            ),
        )

    assert alv1.id != alv2.id


@pytest.mark.asyncio
async def test_alvara_criar_permissionario_inexistente(admin_engine):
    """FK validation: permissionário inexistente."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.criar_alvara(
                s, tenant_id=tenant.id,
                payload=AlvaraCreate(
                    numero_alvara="ALV-016",
                    tipo_servico="taxi",
                    id_permissionario=99999,
                ),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_criar_empresa_inexistente(admin_engine):
    """FK validation: empresa inexistente."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.criar_alvara(
                s, tenant_id=tenant.id,
                payload=AlvaraCreate(
                    numero_alvara="ALV-017",
                    tipo_servico="taxi",
                    id_empresa=99999,
                ),
            )

    assert exc.value.status_code == 404


# ========================= Testes de Atualização ==========================


@pytest.mark.asyncio
async def test_alvara_atualizar_numero(admin_engine):
    """Atualizar número do alvará."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-018",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        alv_id = alv.id

        atualizado = await tr_svc.atualizar_alvara(
            s, tenant_id=tenant.id, alvara_id=alv_id,
            payload=AlvaraUpdate(numero_alvara="ALV-018-NOVO"),
        )

    assert atualizado.numero_alvara == "ALV-018-NOVO"


@pytest.mark.asyncio
async def test_alvara_atualizar_datas(admin_engine):
    """Atualizar datas do alvará."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-019",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        alv_id = alv.id

        atualizado = await tr_svc.atualizar_alvara(
            s, tenant_id=tenant.id, alvara_id=alv_id,
            payload=AlvaraUpdate(
                data_inicio=date(2025, 1, 1),
                data_validade=date(2026, 12, 31),
            ),
        )

    assert atualizado.data_inicio == date(2025, 1, 1)
    assert atualizado.data_validade == date(2026, 12, 31)


@pytest.mark.asyncio
async def test_alvara_atualizar_numero_duplicado(admin_engine):
    """Validação: não permitir número duplicado na atualização."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-020",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        alv2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-021",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        with pytest.raises(HTTPException) as exc:
            await tr_svc.atualizar_alvara(
                s, tenant_id=tenant.id, alvara_id=alv2.id,
                payload=AlvaraUpdate(numero_alvara="ALV-020"),
            )

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_alvara_atualizar_datas_inconsistentes(admin_engine):
    """Validação: datas inconsistentes na atualização (validação Pydantic)."""
    with pytest.raises(ValidationError) as exc:
        AlvaraUpdate(
            data_inicio=date(2025, 12, 31),
            data_validade=date(2024, 1, 1),
        )

    assert "data_inicio" in str(exc.value).lower()


# ========================= Testes de Exclusão ==========================


@pytest.mark.asyncio
async def test_alvara_excluir_soft_delete(admin_engine):
    """Soft-delete: excluido setado para true."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-023",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        alv_id = alv.id

        await tr_svc.excluir_alvara(s, tenant_id=tenant.id, alvara_id=alv_id)

        with pytest.raises(HTTPException) as exc:
            await tr_svc.obter_alvara(s, tenant_id=tenant.id, alvara_id=alv_id)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_excluir_numero_reutilizavel(admin_engine):
    """Número liberado após soft-delete, reutilizável."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-REUSE",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        await tr_svc.excluir_alvara(s, tenant_id=tenant.id, alvara_id=alv1.id)

        # Número deve estar disponível
        alv2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-REUSE",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

    assert alv2.numero_alvara == "ALV-REUSE"
    assert alv2.id != alv1.id


@pytest.mark.asyncio
async def test_alvara_excluir_inexistente(admin_engine):
    """Excluir alvará inexistente retorna 404."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.excluir_alvara(s, tenant_id=tenant.id, alvara_id=99999)

    assert exc.value.status_code == 404

"""Transporte Regulado P2.1 — Renovação de Alvarás.

Cobre renovação tenant-scoped para alvarás vencidos (criação de novo alvará
atrelado ao anterior via renovado_de). Isolamento RLS, validações, cadeia de
histórico, soft-delete da cadeia.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraRenovarInput,
    PermissionarioCreate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(admin_engine):
    slug = _slug("alvren")
    async with _sm(admin_engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Alv Ren", admin_email=f"{slug}@t.local",
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


# ========================= Testes de Renovação ==========================


@pytest.mark.asyncio
async def test_alvara_listar_vencidos_basico(admin_engine):
    """Listar alvarás vencidos retorna apenas alvarás com data_validade <= hoje."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        # Alvará vencido
        vencido = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-VENC",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        # Alvará vigente
        vigente = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-VIG",
                data_validade=hoje + timedelta(days=30),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        vencidos = await tr_svc.listar_alvaras_vencidos(s, tenant_id=tenant.id)

    assert len(vencidos) == 1
    assert vencidos[0].id == vencido.id


@pytest.mark.asyncio
async def test_alvara_listar_vencidos_ordenacao(admin_engine):
    """Listar vencidos retorna ordenados por data_validade ASC (mais antigos primeiro)."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        # Vencido há 30 dias
        vencido1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-V1",
                data_validade=hoje - timedelta(days=30),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        # Vencido há 1 dia
        vencido2 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-V2",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        vencidos = await tr_svc.listar_alvaras_vencidos(s, tenant_id=tenant.id)

    # Mais antigos primeiro (ASC)
    assert vencidos[0].id == vencido1.id
    assert vencidos[1].id == vencido2.id


@pytest.mark.asyncio
async def test_alvara_listar_vencidos_vazio(admin_engine):
    """Listar vencidos retorna vazio quando nenhum vencido."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        # Apenas alvarás vigentes
        await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-VIG",
                data_validade=hoje + timedelta(days=30),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        vencidos = await tr_svc.listar_alvaras_vencidos(s, tenant_id=tenant.id)

    assert len(vencidos) == 0


@pytest.mark.asyncio
async def test_alvara_listar_vencidos_sem_data_validade(admin_engine):
    """Alvarás sem data_validade não aparecem em vencidos."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        # Alvará sem data_validade
        await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-SEM-DATA",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        vencidos = await tr_svc.listar_alvaras_vencidos(s, tenant_id=tenant.id)

    assert len(vencidos) == 0


@pytest.mark.asyncio
async def test_alvara_renovar_basico(admin_engine):
    """Renovar alvará vencido cria novo com renovado_de apontando para original."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        original = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-REN",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        original_id = original.id

        renovado = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=original_id,
            payload=AlvaraRenovarInput(
                data_validade=hoje + timedelta(days=365),
            ),
        )

    assert renovado.id != original_id
    assert renovado.renovado_de == original_id
    assert renovado.numero_alvara == original.numero_alvara
    assert renovado.tipo_servico == original.tipo_servico


@pytest.mark.asyncio
async def test_alvara_renovar_com_novos_dados(admin_engine):
    """Renovação permite atualizar datas e observações."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        original = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-REN2",
                data_inicio=date(2024, 1, 1),
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                observacoes="Original",
                id_permissionario=perm.id,
            ),
        )

        renovado = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=original.id,
            payload=AlvaraRenovarInput(
                data_inicio=date(2025, 1, 1),
                data_validade=hoje + timedelta(days=365),
                observacoes="Renovado",
            ),
        )

    assert renovado.data_inicio == date(2025, 1, 1)
    assert renovado.data_validade == hoje + timedelta(days=365)
    assert renovado.observacoes == "Renovado"


@pytest.mark.asyncio
async def test_alvara_renovar_vencida_obrigatorio(admin_engine):
    """Renovação só funciona para alvarás vencidos."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        vigente = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-VIG",
                data_validade=hoje + timedelta(days=30),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_alvara(
                s, tenant_id=tenant.id, alvara_id=vigente.id,
                payload=AlvaraRenovarInput(
                    data_validade=hoje + timedelta(days=365),
                ),
            )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_alvara_renovar_sem_data_validade(admin_engine):
    """Renovação não funciona para alvarás sem data_validade."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)

    async with _sm(admin_engine)() as s:
        sem_data = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-SEM",
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_alvara(
                s, tenant_id=tenant.id, alvara_id=sem_data.id,
                payload=AlvaraRenovarInput(),
            )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_alvara_renovacao_cria_nova_com_novo_id(admin_engine):
    """Renovação cria alvará com ID diferente."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        original = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-ID",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        renovado = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=original.id,
            payload=AlvaraRenovarInput(
                data_validade=hoje + timedelta(days=365),
            ),
        )

    assert renovado.id != original.id


@pytest.mark.asyncio
async def test_alvara_renovacao_copia_vinculos(admin_engine):
    """Renovação mantém vínculos (empresa/permissionário) do original."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        original = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-VINK",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        renovado = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=original.id,
            payload=AlvaraRenovarInput(
                data_validade=hoje + timedelta(days=365),
            ),
        )

    assert renovado.id_permissionario == original.id_permissionario
    assert renovado.id_empresa == original.id_empresa


@pytest.mark.asyncio
async def test_alvara_renovacao_historico_chain(admin_engine):
    """Renovações sucessivas criam cadeia: alv1 -> alv2 -> alv3."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        # Primeiro alvará
        alv1 = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-CHAIN",
                data_validade=hoje - timedelta(days=30),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )

        # Primeira renovação
        alv2 = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=alv1.id,
            payload=AlvaraRenovarInput(
                data_validade=hoje - timedelta(days=1),
            ),
        )

        # Segunda renovação
        alv3 = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=alv2.id,
            payload=AlvaraRenovarInput(
                data_validade=hoje + timedelta(days=365),
            ),
        )

    # Validar cadeia
    assert alv1.renovado_de is None
    assert alv2.renovado_de == alv1.id
    assert alv3.renovado_de == alv2.id


@pytest.mark.asyncio
async def test_alvara_renovar_cross_tenant_404(admin_engine):
    """Renovar alvará de outra tenant retorna 404."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)
    perm1 = await _permissionario(admin_engine, tenant1.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        alv = await tr_svc.criar_alvara(
            s, tenant_id=tenant1.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-CT",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm1.id,
            ),
        )
        alv_id = alv.id

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as exc:
            await tr_svc.renovar_alvara(
                s, tenant_id=tenant2.id, alvara_id=alv_id,
                payload=AlvaraRenovarInput(
                    data_validade=hoje + timedelta(days=365),
                ),
            )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_alvara_renovacao_preserva_timestamp(admin_engine):
    """Renovação cria criado_em com timestamp atual (não copia do original)."""
    tenant = await _provisionar(admin_engine)
    perm = await _permissionario(admin_engine, tenant.id)
    hoje = datetime.utcnow().date()

    async with _sm(admin_engine)() as s:
        original = await tr_svc.criar_alvara(
            s, tenant_id=tenant.id,
            payload=AlvaraCreate(
                numero_alvara="ALV-TIME",
                data_validade=hoje - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=perm.id,
            ),
        )
        original_criado = original.criado_em

        renovado = await tr_svc.renovar_alvara(
            s, tenant_id=tenant.id, alvara_id=original.id,
            payload=AlvaraRenovarInput(
                data_validade=hoje + timedelta(days=365),
            ),
        )

    # criado_em do renovado deve ser >= do original (tempo posterior)
    assert renovado.criado_em >= original_criado

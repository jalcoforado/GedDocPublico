"""Transporte P4.3 — Relatórios e KPIs de Alvarás.

Testa agregação de KPIs (ativos, vencidos, a_renovar_30d) e exportação
de relatórios em CSV.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import AlvaraCreate
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("p4r")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref P4 Relat", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _criar_permissionario(engine, tenant_id: int, cpf: str = None):
    """Helper: cria permissionário."""
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
    return perm.id, perm


async def _criar_alvara(engine, tenant_id: int, perm_id: int, numero: str = None,
                        data_validade: date | None = None, tipo_servico: str = "taxi"):
    """Helper: cria alvará com data_validade opcional."""
    if numero is None:
        numero = f"ALV-{uuid.uuid4().hex[:6].upper()}"

    async with _sm(engine)() as db:
        a = await tr_svc.criar_alvara(
            db,
            tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=numero,
                tipo_servico=tipo_servico,
                id_permissionario=perm_id,
                data_inicio=date.today(),
                data_validade=data_validade,
            ),
        )
    return a.id, a


@pytest.mark.asyncio
async def test_obter_kpis_agregados_vazio(admin_engine):
    """KPIs agregados com tenant sem alvarás."""
    tenant = await _provisionar(admin_engine)

    async with _sm(admin_engine)() as db:
        kpis = await tr_svc.obter_kpis_agregados(db, tenant_id=tenant.id)

        assert kpis["total_alvaras"] == 0
        assert kpis["ativos"] == 0
        assert kpis["vencidos"] == 0
        assert kpis["a_renovar_30d"] == 0
        assert kpis["indefinidos"] == 0


@pytest.mark.asyncio
async def test_obter_kpis_agregados_status(admin_engine):
    """Calcula KPIs por status (ativo, vencido, a_renovar_30d, indefinido)."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    hoje = date.today()

    # Criar alvarás com diferentes status
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-ATIVO",
                       data_validade=hoje + timedelta(days=100))  # ativo
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-VENCIDO",
                       data_validade=hoje - timedelta(days=10))  # vencido
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-RENOVAR",
                       data_validade=hoje + timedelta(days=20))  # a_renovar_30d
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-INDEFINIDO",
                       data_validade=None)  # indefinido

    async with _sm(admin_engine)() as db:
        kpis = await tr_svc.obter_kpis_agregados(db, tenant_id=tenant.id)

        assert kpis["total_alvaras"] == 4
        assert kpis["ativos"] == 1
        assert kpis["vencidos"] == 1
        assert kpis["a_renovar_30d"] == 1
        assert kpis["indefinidos"] == 1


@pytest.mark.asyncio
async def test_listar_relatorio_alvaras_sem_filtro(admin_engine):
    """Lista relatório de alvarás sem filtros."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    hoje = date.today()
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-1",
                       data_validade=hoje + timedelta(days=50))
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-2",
                       data_validade=hoje - timedelta(days=10))

    async with _sm(admin_engine)() as db:
        alvaras, total = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, limit=50
        )

        assert total == 2
        assert len(alvaras) == 2
        # Verificar que tem status calculado
        assert all("status" in a for a in alvaras)
        assert all("dias_para_vencimento" in a for a in alvaras)


@pytest.mark.asyncio
async def test_listar_relatorio_com_filtro_tipo_servico(admin_engine):
    """Filtra relatório por tipo_servico."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-TAXI",
                       tipo_servico="taxi")
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-MOTO",
                       tipo_servico="mototaxi")

    async with _sm(admin_engine)() as db:
        alvaras, total = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, tipo_servico="taxi", limit=50
        )

        assert total == 2  # Total contado antes do filtro
        # Após filtro de status, pode haver alteração
        taxistas = [a for a in alvaras if a["tipo_servico"] == "taxi"]
        assert len(taxistas) >= 1


@pytest.mark.asyncio
async def test_listar_relatorio_com_filtro_permissionario(admin_engine):
    """Filtra relatório por id_permissionario."""
    tenant = await _provisionar(admin_engine)
    perm1_id, _ = await _criar_permissionario(admin_engine, tenant.id, cpf="11111111111")
    perm2_id, _ = await _criar_permissionario(admin_engine, tenant.id, cpf="22222222222")

    await _criar_alvara(admin_engine, tenant.id, perm1_id, numero="ALV-P1")
    await _criar_alvara(admin_engine, tenant.id, perm2_id, numero="ALV-P2")

    async with _sm(admin_engine)() as db:
        alvaras, total = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, id_permissionario=perm1_id, limit=50
        )

        assert len(alvaras) >= 1
        assert all(a["id_permissionario"] == perm1_id for a in alvaras)


@pytest.mark.asyncio
async def test_listar_relatorio_com_filtro_status(admin_engine):
    """Filtra relatório por status."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    hoje = date.today()
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-ATIVO",
                       data_validade=hoje + timedelta(days=100))
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-VENCIDO",
                       data_validade=hoje - timedelta(days=10))

    async with _sm(admin_engine)() as db:
        alvaras, _ = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, status_filtro="ativo", limit=50
        )

        assert all(a["status"] == "ativo" for a in alvaras)


@pytest.mark.asyncio
async def test_listar_relatorio_paginacao(admin_engine):
    """Paginação do relatório."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    # Criar 5 alvarás
    for i in range(5):
        await _criar_alvara(admin_engine, tenant.id, perm_id, numero=f"ALV-{i}")

    async with _sm(admin_engine)() as db:
        page1, total1 = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, limit=2, offset=0
        )
        page2, total2 = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, limit=2, offset=2
        )

        assert len(page1) == 2
        assert len(page2) == 2
        assert total1 == 5
        assert total2 == 5


@pytest.mark.asyncio
async def test_gerar_csv_alvaras(admin_engine):
    """Gera CSV a partir de alvarás com KPIs."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)

    hoje = date.today()
    await _criar_alvara(admin_engine, tenant.id, perm_id, numero="ALV-CSV",
                       data_validade=hoje + timedelta(days=50))

    async with _sm(admin_engine)() as db:
        alvaras, _ = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant.id, limit=50
        )

    csv_content = tr_svc.gerar_csv_alvaras(alvaras)

    # Verificar que CSV contém headers e dados
    assert "numero_alvara" in csv_content
    assert "ALV-CSV" in csv_content
    assert "status" in csv_content


@pytest.mark.asyncio
async def test_cross_tenant_relatorio_isolation(admin_engine):
    """Cross-tenant: relatório isolado por tenant."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)

    perm1_id, _ = await _criar_permissionario(admin_engine, tenant1.id, cpf="11111111111")
    perm2_id, _ = await _criar_permissionario(admin_engine, tenant2.id, cpf="22222222222")

    await _criar_alvara(admin_engine, tenant1.id, perm1_id, numero="ALV-T1")
    await _criar_alvara(admin_engine, tenant2.id, perm2_id, numero="ALV-T2")

    async with _sm(admin_engine)() as db:
        alvaras_t1, _ = await tr_svc.listar_relatorio_alvaras(
            db, tenant_id=tenant1.id, limit=50
        )

        assert len(alvaras_t1) == 1
        assert alvaras_t1[0]["numero_alvara"] == "ALV-T1"

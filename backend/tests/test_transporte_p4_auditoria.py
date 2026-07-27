"""Transporte P4.2 — Auditoria e Histórico de Alvarás.

Testa registros append-only de eventos de alvará (criação, renovação,
atualização de responsáveis/veículos) com snapshots JSONB de estado.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import AlvaraCreate
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("p4a")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref P4 Audit", admin_email=f"{slug}@t.local",
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


async def _criar_alvara(engine, tenant_id: int, perm_id: int, numero: str = None):
    """Helper: cria alvará."""
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
    return a.id, a


@pytest.mark.asyncio
async def test_registrar_auditoria_alvara_criacao(admin_engine):
    """Registrar evento de criação de alvará."""
    tenant = await _provisionar(admin_engine)
    perm_id, perm = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id, alvara = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Registrar auditoria de criação
        audit = await tr_svc.registrar_auditoria_alvara(
            db,
            tenant_id=tenant.id,
            alvara_id=alvara_id,
            acao="alvara.criada",
            dados_novos={
                "numero_alvara": alvara.numero_alvara,
                "tipo_servico": alvara.tipo_servico,
            },
        )

        assert audit.acao == "alvara.criada"
        assert audit.dados_novos is not None
        assert audit.dados_novos["numero_alvara"] == alvara.numero_alvara
        assert audit.dados_antigos is None  # Criação não tem "antes"


@pytest.mark.asyncio
async def test_registrar_auditoria_com_snapshot_antes_depois(admin_engine):
    """Registrar auditoria com snapshots antes/depois."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id, _ = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Simular atualização com snapshots
        audit = await tr_svc.registrar_auditoria_alvara(
            db,
            tenant_id=tenant.id,
            alvara_id=alvara_id,
            acao="alvara.renovada",
            dados_antigos={"data_validade": "2025-01-01"},
            dados_novos={"data_validade": "2026-01-01"},
        )

        assert audit.dados_antigos["data_validade"] == "2025-01-01"
        assert audit.dados_novos["data_validade"] == "2026-01-01"


@pytest.mark.asyncio
async def test_registrar_auditoria_com_usuario(admin_engine):
    """Registrar auditoria com ID do usuário que fez a ação."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id, _ = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # id_usuario tem FK para utils.usuario — usar o admin real do tenant
        # provisionado. Fixar `1` violava a FK (esse id não existe aqui).
        usuario_id = int(
            (
                await db.execute(
                    text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant.id},
                )
            ).scalar_one()
        )

        audit = await tr_svc.registrar_auditoria_alvara(
            db,
            tenant_id=tenant.id,
            alvara_id=alvara_id,
            acao="alvara.atualizada",
            usuario_id=usuario_id,
        )

        assert audit.id_usuario == usuario_id


@pytest.mark.asyncio
async def test_listar_auditoria_alvara(admin_engine):
    """Listar histórico de auditoria de um alvará."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id, _ = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Criar 3 eventos de auditoria
        await tr_svc.registrar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, acao="alvara.criada"
        )
        await tr_svc.registrar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, acao="alvara.renovada"
        )
        await tr_svc.registrar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, acao="alvara.responsavel_adicionado"
        )

        # Listar
        eventos = await tr_svc.listar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, limit=50
        )

        assert len(eventos) == 3
        # Ordem DESC (mais recentes primeiro)
        assert eventos[0].acao == "alvara.responsavel_adicionado"
        assert eventos[1].acao == "alvara.renovada"
        assert eventos[2].acao == "alvara.criada"


@pytest.mark.asyncio
async def test_listar_auditoria_paginacao(admin_engine):
    """Listar auditoria com paginação (limit + offset)."""
    tenant = await _provisionar(admin_engine)
    perm_id, _ = await _criar_permissionario(admin_engine, tenant.id)
    alvara_id, _ = await _criar_alvara(admin_engine, tenant.id, perm_id)

    async with _sm(admin_engine)() as db:
        # Criar 5 eventos
        for i in range(5):
            await tr_svc.registrar_auditoria_alvara(
                db,
                tenant_id=tenant.id,
                alvara_id=alvara_id,
                acao=f"alvara.evento_{i}",
            )

        # Listar com limit=2
        page1 = await tr_svc.listar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, limit=2, offset=0
        )
        page2 = await tr_svc.listar_auditoria_alvara(
            db, tenant_id=tenant.id, alvara_id=alvara_id, limit=2, offset=2
        )

        assert len(page1) == 2
        assert len(page2) == 2
        # Verificar que não há duplicatas
        ids1 = {e.id for e in page1}
        ids2 = {e.id for e in page2}
        assert len(ids1 & ids2) == 0


@pytest.mark.asyncio
async def test_cross_tenant_auditoria_isolation(admin_engine):
    """Cross-tenant: auditoria isolada por tenant."""
    tenant1 = await _provisionar(admin_engine)
    tenant2 = await _provisionar(admin_engine)

    perm1_id, _ = await _criar_permissionario(admin_engine, tenant1.id)
    perm2_id, _ = await _criar_permissionario(admin_engine, tenant2.id)

    alvara1_id, _ = await _criar_alvara(admin_engine, tenant1.id, perm1_id)
    alvara2_id, _ = await _criar_alvara(admin_engine, tenant2.id, perm2_id)

    async with _sm(admin_engine)() as db:
        # Registrar eventos em ambos os tenants
        await tr_svc.registrar_auditoria_alvara(
            db,
            tenant_id=tenant1.id,
            alvara_id=alvara1_id,
            acao="alvara.criada",
        )
        await tr_svc.registrar_auditoria_alvara(
            db,
            tenant_id=tenant2.id,
            alvara_id=alvara2_id,
            acao="alvara.criada",
        )

        # Listar auditoria de tenant1 — só deve retornar evento de tenant1
        eventos_t1 = await tr_svc.listar_auditoria_alvara(
            db, tenant_id=tenant1.id, alvara_id=alvara1_id
        )

        assert len(eventos_t1) == 1
        assert eventos_t1[0].id_alvara == alvara1_id

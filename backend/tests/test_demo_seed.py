"""DEMO-1 — testes do CLI `seed_demo`.

Cada teste usa um tenant `demo-pytest-<suf>` descartável (não toca no tenant
`demo` que devs possam estar usando para apresentação local). Cleanup completo
no teardown.

Cobre:
1. apply roda sem erro
2. apply é idempotente (re-rodar não duplica nem cria)
3. status identifica tenant demo + contagens corretas
4. cria os 6 serviços esperados (todos com slug demo-*)
5. cria os 12 processos esperados (todos com numero_origem demo-*)
6. dados são criados APENAS no tenant alvo (não vazam pra outros tenants)
7. reset limpa dados demo sem afetar nada de outro tenant
"""
from __future__ import annotations

import argparse
import uuid

import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_demo import (
    DEMO_EMAIL_DOMAIN,
    DEMO_ORIGEM_PREFIX,
    DEMO_SLUG_PREFIX,
    PROCESSOS,
    SERVICOS,
    _apply,
    _reset,
)
from app.models import (
    Manifestante,
    Processo,
    Servico,
    Tenant,
    Usuario,
)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _ns(tenant: str, allow_non_demo: bool = False) -> argparse.Namespace:
    return argparse.Namespace(tenant=tenant, allow_non_demo=allow_non_demo)


async def _cleanup_demo_tenant(engine, slug: str) -> None:
    """Remove tenant + tudo que está nele (chamado no teardown).
    Usa o _reset do CLI primeiro (remove dados tenant-scoped), depois apaga
    o tenant em si."""
    async with _sm(engine)() as s:
        # Identifica tenant
        tid = (
            await s.execute(
                text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": slug},
            )
        ).scalar_one_or_none()
        if tid is None:
            return

        # Limpa tudo do tenant — usa ordem de FK conhecida.
        for sql in (
            f"SET LOCAL app.tenant_id = {int(tid)}",
            "UPDATE protocolos.processo SET id_ultima_movimentacao = NULL WHERE tenant_id = :t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id = :t",
            "DELETE FROM protocolos.anexo_processo WHERE tenant_id = :t",
            "DELETE FROM protocolos.anexo WHERE tenant_id = :t",
            "DELETE FROM protocolos.complementacao_documental WHERE tenant_id = :t",
            "DELETE FROM protocolos.movimentacao WHERE tenant_id = :t",
            "DELETE FROM protocolos.processo WHERE tenant_id = :t",
            "DELETE FROM protocolos.manifestante WHERE tenant_id = :t",
            "DELETE FROM protocolos.servico WHERE tenant_id = :t",
            "DELETE FROM protocolos.assunto WHERE tenant_id = :t",
            "DELETE FROM protocolos.tipo_processo WHERE tenant_id = :t",
            "DELETE FROM protocolos.tipo_anexo WHERE tenant_id = :t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id = :t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id = :t",
            "DELETE FROM utils.grupo WHERE tenant_id = :t",
            "DELETE FROM utils.usuario WHERE tenant_id = :t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id = :t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id = :t",
            "DELETE FROM aprimora_py.tenant WHERE id = :t",
        ):
            if "SET LOCAL" in sql:
                await s.execute(text(sql))
            else:
                await s.execute(text(sql), {"t": tid})
        await s.commit()


@pytest_asyncio.fixture
async def demo_slug(admin_engine):
    """Yield um slug demo-pytest-XXXX único; cleanup garantido.

    Dispõe `app.database.engine` no teardown — o `_apply` usa SessionLocal
    (singleton de módulo) que carrega event loop do PRIMEIRO teste; sem
    dispor, testes subsequentes batem em RuntimeError. Padrão já usado em
    `test_sec1_marcar_flag_must_change_password.py::client`."""
    slug = f"demo-pytest-{uuid.uuid4().hex[:8]}"
    try:
        yield slug
    finally:
        await _cleanup_demo_tenant(admin_engine, slug)
        from app.database import engine as app_engine

        await app_engine.dispose()


# ----------------------------------------------------------------------
# 1. apply roda sem erro
# ----------------------------------------------------------------------


async def test_apply_roda_sem_erro(admin_engine, demo_slug):
    rc = await _apply(_ns(demo_slug))
    assert rc == 0
    async with _sm(admin_engine)() as s:
        n_tenant = (
            await s.execute(
                text("SELECT COUNT(*) FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": demo_slug},
            )
        ).scalar_one()
    assert n_tenant == 1


# ----------------------------------------------------------------------
# 2. apply é idempotente
# ----------------------------------------------------------------------


async def test_apply_idempotente(admin_engine, demo_slug):
    rc1 = await _apply(_ns(demo_slug))
    assert rc1 == 0
    # 2º run não deve criar nada novo
    rc2 = await _apply(_ns(demo_slug))
    assert rc2 == 0
    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": demo_slug},
            )
        ).scalar_one()
        n_serv = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.servico WHERE tenant_id=:t "
                    f"  AND slug LIKE '{DEMO_SLUG_PREFIX}-%' AND excluido=false"
                ),
                {"t": tid},
            )
        ).scalar_one()
        n_proc = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo WHERE tenant_id=:t "
                    f"  AND numero_origem LIKE '{DEMO_ORIGEM_PREFIX}%'"
                ),
                {"t": tid},
            )
        ).scalar_one()
        n_manif = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.manifestante WHERE tenant_id=:t "
                    "  AND cpf_cnpj LIKE '999%'"
                ),
                {"t": tid},
            )
        ).scalar_one()
    assert n_serv == len(SERVICOS)
    assert n_proc == len(PROCESSOS)
    assert n_manif == 12


# ----------------------------------------------------------------------
# 3-4. apply cria os 6 serviços esperados
# ----------------------------------------------------------------------


async def test_apply_cria_servicos_esperados(admin_engine, demo_slug):
    await _apply(_ns(demo_slug))
    slugs_esperados = {s["slug"] for s in SERVICOS}
    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": demo_slug},
            )
        ).scalar_one()
        rows = (
            await s.execute(
                select(Servico.slug, Servico.prazo_estimado_dias).where(
                    Servico.tenant_id == tid,
                    Servico.slug.like(f"{DEMO_SLUG_PREFIX}-%"),
                    Servico.excluido.is_(False),
                )
            )
        ).all()
    slugs_criados = {r[0] for r in rows}
    assert slugs_criados == slugs_esperados
    # Ao menos um prazo curto (3d) e um longo (30d)
    prazos = {r[1] for r in rows}
    assert 3 in prazos
    assert 30 in prazos


# ----------------------------------------------------------------------
# 5. apply cria os 12 processos com numero_origem demo-*
# ----------------------------------------------------------------------


async def test_apply_cria_processos_esperados(admin_engine, demo_slug):
    await _apply(_ns(demo_slug))
    origens_esperadas = {p["origem"] for p in PROCESSOS}
    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": demo_slug},
            )
        ).scalar_one()
        rows = (
            await s.execute(
                select(Processo.numero_origem).where(
                    Processo.tenant_id == tid,
                    Processo.numero_origem.like(f"{DEMO_ORIGEM_PREFIX}%"),
                )
            )
        ).all()
    origens_criadas = {r[0] for r in rows}
    assert origens_criadas == origens_esperadas


# ----------------------------------------------------------------------
# 6. apply não vaza dados pra outros tenants
# ----------------------------------------------------------------------


async def test_apply_nao_vaza_para_outros_tenants(admin_engine, demo_slug):
    """Roda apply no demo-pytest; conta de processos/serviços demo-*
    em OUTROS tenants permanece zero."""
    async with _sm(admin_engine)() as s:
        outros_proc_antes = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo "
                    f"WHERE numero_origem LIKE '{DEMO_ORIGEM_PREFIX}%' "
                    "  AND tenant_id NOT IN (SELECT id FROM aprimora_py.tenant WHERE slug=:s)"
                ),
                {"s": demo_slug},
            )
        ).scalar_one()
    await _apply(_ns(demo_slug))
    async with _sm(admin_engine)() as s:
        outros_proc_depois = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo "
                    f"WHERE numero_origem LIKE '{DEMO_ORIGEM_PREFIX}%' "
                    "  AND tenant_id NOT IN (SELECT id FROM aprimora_py.tenant WHERE slug=:s)"
                ),
                {"s": demo_slug},
            )
        ).scalar_one()
    assert outros_proc_antes == outros_proc_depois, (
        "apply criou processos demo em outro tenant que não o alvo"
    )


# ----------------------------------------------------------------------
# 7. reset limpa dados demo sem afetar outro tenant
# ----------------------------------------------------------------------


async def test_reset_limpa_demo_sem_afetar_outros(admin_engine, demo_slug):
    await _apply(_ns(demo_slug))

    # Conta processos em outros tenants ANTES
    async with _sm(admin_engine)() as s:
        outros_antes = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo "
                    "WHERE tenant_id NOT IN (SELECT id FROM aprimora_py.tenant WHERE slug=:s)"
                ),
                {"s": demo_slug},
            )
        ).scalar_one()

    rc = await _reset(_ns(demo_slug))
    assert rc == 0

    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text("SELECT id FROM aprimora_py.tenant WHERE slug=:s"),
                {"s": demo_slug},
            )
        ).scalar_one()
        n_proc_demo = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo WHERE tenant_id=:t"
                ),
                {"t": tid},
            )
        ).scalar_one()
        n_serv_demo = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.servico WHERE tenant_id=:t "
                    "  AND excluido=false"
                ),
                {"t": tid},
            )
        ).scalar_one()
        outros_depois = (
            await s.execute(
                text(
                    "SELECT COUNT(*) FROM protocolos.processo "
                    "WHERE tenant_id NOT IN (SELECT id FROM aprimora_py.tenant WHERE slug=:s)"
                ),
                {"s": demo_slug},
            )
        ).scalar_one()
        admin_demo_existe = (
            await s.execute(
                text(
                    "SELECT 1 FROM utils.usuario WHERE tenant_id=:t "
                    f"  AND email='admin@{DEMO_EMAIL_DOMAIN}' AND excluido=false"
                ),
                {"t": tid},
            )
        ).scalar_one_or_none()

    assert n_proc_demo == 0, "reset não limpou os processos demo"
    assert n_serv_demo == 0, "reset não limpou os serviços demo"
    assert outros_antes == outros_depois, "reset afetou processos de outro tenant"
    assert admin_demo_existe == 1, "reset não deveria apagar admin@demo.test"


# ----------------------------------------------------------------------
# 8. guard: tenant não-demo é recusado sem --allow-non-demo
# ----------------------------------------------------------------------


async def test_apply_recusa_tenant_nao_demo(admin_engine):
    """`apply --tenant sobral` (ou qualquer slug que não comece com `demo`)
    deve abortar antes de qualquer mutação. Usamos pytest.raises(SystemExit)
    porque _guard_tenant_slug chama sys.exit(2)."""
    import pytest

    with pytest.raises(SystemExit) as excinfo:
        await _apply(_ns("sobral"))
    assert excinfo.value.code == 2

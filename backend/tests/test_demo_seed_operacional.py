"""Testes do CLI `seed_demo_operacional` (pagamentos, frota, transporte).

Cada teste usa um tenant descartável, criado no molde do `seed_bootstrap`
(tenant + admin + unidade) — de propósito, porque é o formato do tenant real de
homologação e foi justamente onde o `seed_demo` original quebrou.

Cobre:
1. apply cria dados nos três módulos
2. os débitos chegam nos status esperados (o rito roda de verdade)
3. a conciliação da Onda B tem extrato e sugestões
4. apply é idempotente
5. reset limpa tudo sem violar FK
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_demo_operacional import (
    ALVARAS,
    DEBITOS,
    OPS_EMAIL_DOMAIN,
    VEICULOS_FROTA,
    _apply,
    _reset,
)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _ns(tenant: str, modulo: str = "todos") -> argparse.Namespace:
    return argparse.Namespace(tenant=tenant, allow_non_demo=True, modulo=modulo)


async def _contar(engine, tenant_id: int, sql: str) -> int:
    async with _sm(engine)() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))
        return (await s.execute(text(sql), {"t": tenant_id})).scalar_one()


@pytest_asyncio.fixture
async def tenant_ops(admin_engine):
    """Tenant mínimo: o que o `seed_bootstrap` produz, mais uma unidade.

    O seeder operacional precisa de uma unidade (contratos e solicitações
    apontam para ela) e de nada além disso.
    """
    slug = f"ops-pytest-{uuid.uuid4().hex[:8]}"
    async with _sm(admin_engine)() as s:
        tid = (
            await s.execute(
                text(
                    "INSERT INTO aprimora_py.tenant (slug, nome, plano, ativo, criado_em) "
                    "VALUES (:s, 'Tenant Ops', 'basico', true, :c) RETURNING id"
                ),
                {"s": slug, "c": datetime.now(timezone.utc).replace(tzinfo=None)},
            )
        ).scalar_one()
        await s.execute(text(f"SET LOCAL app.tenant_id = {int(tid)}"))
        await s.execute(
            text(
                "INSERT INTO utils.unidade_trabalho "
                "(tenant_id, unidade_trabalho, sigla, excluido) "
                "VALUES (:t, 'Protocolo Geral', 'PG', false)"
            ),
            {"t": tid},
        )
        await s.execute(
            text(
                "INSERT INTO utils.usuario "
                "(tenant_id, nome, email, senha, senha_bcrypt, cpf, ativo, excluido, "
                " app, nivel_acesso_sigilo, must_change_password) "
                "VALUES (:t, 'Admin Ops', :e, '', '', :c, true, false, "
                "        'sistemas', 'interno', false)"
            ),
            {"t": tid, "e": f"admin@{slug}.test", "c": str(uuid.uuid4().int)[:11]},
        )
        await s.commit()
    try:
        yield slug, tid
    finally:
        await _reset(_ns(slug))
        async with _sm(admin_engine)() as s:
            for sql in (
                "DELETE FROM utils.usuario WHERE tenant_id = :t",
                "DELETE FROM utils.unidade_trabalho WHERE tenant_id = :t",
                "DELETE FROM aprimora_py.tenant WHERE id = :t",
            ):
                await s.execute(text(sql), {"t": tid})
            await s.commit()
        from app.database import engine as app_engine

        await app_engine.dispose()


@pytest.mark.asyncio
async def test_apply_cria_os_tres_modulos(admin_engine, tenant_ops):
    slug, tid = tenant_ops
    assert await _apply(_ns(slug)) == 0

    n_debitos = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM pagamentos.debito WHERE tenant_id=:t AND excluido=false",
    )
    n_veiculos = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM frota.veiculo WHERE tenant_id=:t AND excluido=false",
    )
    n_alvaras = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM transporte_regulado.alvara WHERE tenant_id=:t AND excluido=false",
    )
    assert n_debitos == len(DEBITOS)
    assert n_veiculos == len(VEICULOS_FROTA)
    assert n_alvaras == len(ALVARAS)


@pytest.mark.asyncio
async def test_debitos_percorrem_o_rito(admin_engine, tenant_ops):
    """O valor do seed está em passar pelos serviços: se ele usasse INSERT cru,
    os status existiriam sem histórico nem saldo comprometido coerente."""
    slug, tid = tenant_ops
    await _apply(_ns(slug, modulo="pagamentos"))

    async with _sm(admin_engine)() as s:
        await s.execute(text(f"SET LOCAL app.tenant_id = {int(tid)}"))
        status = dict(
            (
                await s.execute(
                    text(
                        "SELECT status, count(*) FROM pagamentos.debito "
                        "WHERE tenant_id=:t AND excluido=false GROUP BY status"
                    ),
                    {"t": tid},
                )
            ).all()
        )
        historico = (
            await s.execute(
                text(
                    "SELECT count(*) FROM pagamentos.debito_historico WHERE tenant_id=:t"
                ),
                {"t": tid},
            )
        ).scalar_one()

    # Os estados que só se alcança percorrendo o rito inteiro — PAGO exige
    # autorização com alçada, liberação e baixa na tesouraria.
    for esperado in ("RASCUNHO", "EM_VALIDACAO", "DEVOLVIDO", "VALIDADO",
                     "ENVIADO_SECRETARIO", "AUTORIZADO", "PAGO", "SUSPENSO"):
        assert status.get(esperado, 0) >= 1, f"nenhum débito em {esperado}: {status}"
    # Rito de verdade deixa trilha: no mínimo uma transição por débito.
    assert historico >= len(DEBITOS)


@pytest.mark.asyncio
async def test_conciliacao_tem_extrato_e_sugestoes(admin_engine, tenant_ops):
    slug, tid = tenant_ops
    await _apply(_ns(slug, modulo="pagamentos"))

    from app.database import SessionLocal
    from app.services import pagamentos_conciliacao as conc_svc

    db = SessionLocal()
    db.info["tenant_id"] = tid
    async with db:
        extratos = await conc_svc.listar_extratos(db, tenant_id=tid)
        assert extratos, "nenhum extrato importado — a Onda B ficaria sem dado"
        sugestoes = await conc_svc.sugerir_baixas(db, tenant_id=tid, id_extrato=extratos[0].id)

    # As parcelas pagas geram movimentação; o extrato repete os mesmos valores,
    # então tem de haver correspondência exata para pelo menos uma delas.
    assert any(s.tipo_correspondencia == "EXATA" for s in sugestoes)


@pytest.mark.asyncio
async def test_apply_idempotente(admin_engine, tenant_ops):
    slug, tid = tenant_ops
    await _apply(_ns(slug))
    antes = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM pagamentos.debito WHERE tenant_id=:t AND excluido=false",
    )
    await _apply(_ns(slug))
    depois = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM pagamentos.debito WHERE tenant_id=:t AND excluido=false",
    )
    assert depois == antes


@pytest.mark.asyncio
async def test_reset_limpa_tudo(admin_engine, tenant_ops):
    """Regressão da ordem de FK: o reset já reportou sucesso sem ter apagado,
    porque um erro isolado derrubava a transação inteira."""
    slug, tid = tenant_ops
    await _apply(_ns(slug))
    await _reset(_ns(slug))

    for tabela in (
        "pagamentos.debito",
        "pagamentos.parcela",
        "pagamentos.fornecedor",
        "pagamentos.conta_bancaria",
        "frota.veiculo",
        "frota.solicitacao_veiculo",
        "transporte_regulado.alvara",
        "transporte_regulado.permissionario",
    ):
        n = await _contar(
            admin_engine, tid, f"SELECT count(*) FROM {tabela} WHERE tenant_id=:t"
        )
        assert n == 0, f"{tabela} ainda tem {n} linha(s) após o reset"

    n_users = await _contar(
        admin_engine, tid,
        "SELECT count(*) FROM utils.usuario WHERE tenant_id=:t "
        f"AND email LIKE '%@{OPS_EMAIL_DOMAIN}'",
    )
    assert n_users == 0

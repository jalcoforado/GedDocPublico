"""SI-54 — seed do catálogo de tipos de processo e assuntos.

Roda `aplicar_catalogo` direto numa sessão administrativa sobre os tenants
descartáveis da fixture `two_tenants` (que limpa `assunto` e `tipo_processo`
no teardown). O CLI em si só acrescenta o guard de slug e o commit.
"""
from __future__ import annotations

import argparse

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli.seed_catalogo_protocolo import (
    TETO_ASSUNTOS_NA_ABERTURA,
    _apply,
    aplicar_catalogo,
    carregar_dados,
)
from app.models import Assunto, TipoProcesso

DADOS = carregar_dados()
N_TIPOS = len(DADOS["tipos"])
N_ASSUNTOS = sum(len(t["assuntos"]) for t in DADOS["tipos"])


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _aplicar(engine, tenant_id: int) -> dict:
    async with _sm(engine)() as s:
        s.info["tenant_id"] = tenant_id
        contagens = await aplicar_catalogo(s, tenant_id, DADOS)
        await s.commit()
    return contagens


async def _contar(engine, modelo, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return (
            await s.execute(
                select(func.count(modelo.id)).where(
                    modelo.tenant_id == tenant_id, modelo.excluido.is_(False)
                )
            )
        ).scalar_one()


# --- o arquivo de dados ------------------------------------------------------


def test_dados_sem_nome_repetido():
    """O seed procura assunto pelo NOME no tenant: dois iguais no arquivo
    virariam um só, sob o tipo que aparecer primeiro."""
    tipos = [t["nome"] for t in DADOS["tipos"]]
    assuntos = [a["nome"] for t in DADOS["tipos"] for a in t["assuntos"]]
    assert len(tipos) == len(set(tipos))
    assert len(assuntos) == len(set(assuntos))


def test_dados_cabem_no_combo_da_abertura():
    """Folga para os assuntos que a prefeitura já tem: a abertura só carrega
    200 e corta o resto sem aviso."""
    assert N_ASSUNTOS <= TETO_ASSUNTOS_NA_ABERTURA - 20


# --- aplicar -----------------------------------------------------------------


async def test_cria_tudo_e_so_no_tenant_alvo(admin_engine, two_tenants):
    tid_a, tid_b = two_tenants
    c = await _aplicar(admin_engine, tid_a)

    assert c["tipos_criados"] == N_TIPOS
    assert c["assuntos_criados"] == N_ASSUNTOS
    assert c["conflitos"] == []
    assert await _contar(admin_engine, TipoProcesso, tid_a) == N_TIPOS
    assert await _contar(admin_engine, Assunto, tid_a) == N_ASSUNTOS
    # Nada vaza para a outra prefeitura.
    assert await _contar(admin_engine, TipoProcesso, tid_b) == 0
    assert await _contar(admin_engine, Assunto, tid_b) == 0


async def test_rodar_de_novo_nao_duplica(admin_engine, two_tenants):
    tid_a, _ = two_tenants
    await _aplicar(admin_engine, tid_a)
    c = await _aplicar(admin_engine, tid_a)

    assert (c["tipos_criados"], c["assuntos_criados"]) == (0, 0)
    assert (c["tipos_existentes"], c["assuntos_existentes"]) == (N_TIPOS, N_ASSUNTOS)
    assert await _contar(admin_engine, Assunto, tid_a) == N_ASSUNTOS


async def test_nao_reativa_o_que_o_admin_desativou(admin_engine, two_tenants):
    tid_a, _ = two_tenants
    async with _sm(admin_engine)() as s:
        tp = TipoProcesso(tenant_id=tid_a, tipo_processo="Tributação", ativo=False,
                          exige_processo_pai=False, excluido=False)
        s.add(tp)
        await s.flush()
        s.add(Assunto(tenant_id=tid_a, assunto="Parcelamento de débitos",
                      id_tipo_processo=tp.id, ativo=False, exige_processo_pai=False,
                      excluido=False, nivel=1))
        await s.commit()

    await _aplicar(admin_engine, tid_a)

    async with _sm(admin_engine)() as s:
        tipos = (await s.execute(select(TipoProcesso.ativo).where(
            TipoProcesso.tenant_id == tid_a, TipoProcesso.tipo_processo == "Tributação",
        ))).scalars().all()
        assuntos = (await s.execute(select(Assunto.ativo).where(
            Assunto.tenant_id == tid_a, Assunto.assunto == "Parcelamento de débitos",
        ))).scalars().all()
    assert tipos == [False]
    assert assuntos == [False]


async def test_assunto_sob_outro_tipo_e_conflito_e_nao_se_move(admin_engine, two_tenants):
    tid_a, _ = two_tenants
    async with _sm(admin_engine)() as s:
        outro = TipoProcesso(tenant_id=tid_a, tipo_processo="Solicitação", ativo=True,
                             exige_processo_pai=False, excluido=False)
        s.add(outro)
        await s.flush()
        s.add(Assunto(tenant_id=tid_a, assunto="Férias", id_tipo_processo=outro.id,
                      ativo=True, exige_processo_pai=False, excluido=False, nivel=1))
        await s.commit()
        id_outro = outro.id

    c = await _aplicar(admin_engine, tid_a)

    assert len(c["conflitos"]) == 1 and "Férias" in c["conflitos"][0]
    async with _sm(admin_engine)() as s:
        tipos_de_ferias = (await s.execute(select(Assunto.id_tipo_processo).where(
            Assunto.tenant_id == tid_a, Assunto.assunto == "Férias",
        ))).scalars().all()
    assert tipos_de_ferias == [id_outro]


async def test_cli_recusa_tenant_que_nao_e_demo_sem_o_flag():
    with pytest.raises(SystemExit) as exc:
        await _apply(argparse.Namespace(tenant="sobral", allow_non_demo=False))
    assert exc.value.code == 2

"""Transporte Fase C1 — gate de renovação de alvará para titular suspenso.

Spec: `docs/superpowers/specs/2026-08-23-transporte-p5-pendencias-design.md`
(seção "Fatia C1 — o gate de renovação").

`renovar_alvara` passa a recusar com 409 quando o titular (permissionário OU
empresa) do alvará tem convocação de recadastramento `suspenso` não excluída,
de qualquer ciclo. A mensagem manda para a reativação — não para a reabertura
(lição da P5.3: mensagem que aponta a porta errada custa um chamado por
ocorrência).

**Emitir alvará novo NÃO passa pelo gate** — só `renovar_alvara`. Há teste
afirmando as duas coisas, porque "melhorar" o gate para cobrir emissão é a
deriva mais provável.

As fixtures reaproveitam os helpers da P5.2/P5.3 — duplicá-las faria as
baterias divergirem em silêncio sobre o que é um cenário válido.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.schemas.transporte_regulado import (
    AlvaraCreate,
    AlvaraRenovarInput,
    EmpresaCreate,
)
from app.main import app
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _convocacao,
    _cria_usuario_comum_transporte,
    _encerrar_arreio,
    _permissionario,
    _provisionar,
    _sm,
    _um_usuario,
)
from tests.test_transporte_p5_3_atraso import _ciclo_vencido, _parecer

HOJE = date.today()


async def _alvara_vencido(engine, tenant_id: int, *, id_permissionario=None, id_empresa=None):
    async with _sm(engine)() as db:
        return await tr.criar_alvara(
            db,
            tenant_id=tenant_id,
            payload=AlvaraCreate(
                numero_alvara=f"ALV-FC-{uuid.uuid4().hex[:8]}",
                data_validade=HOJE - timedelta(days=1),
                tipo_servico="taxi",
                id_permissionario=id_permissionario,
                id_empresa=id_empresa,
            ),
        )


async def _empresa_ativa(engine, tenant_id: int, *, razao="Empresa Fase C"):
    async with _sm(engine)() as db:
        return await tr.criar_empresa(
            db,
            tenant_id=tenant_id,
            payload=EmpresaCreate(
                razao_social=razao,
                cnpj=str(uuid.uuid4().int)[:14],
                tipo_servico="taxi",
                situacao="ativa",
            ),
        )


@pytest.mark.asyncio
async def test_suspenso_nao_renova_alvara_e_a_mensagem_aponta_reativacao(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )

    alvara = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.renovar_alvara(
                db, tenant_id=tid, alvara_id=alvara.id,
                payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
            )
    assert e.value.status_code == 409
    assert "reativação" in e.value.detail


@pytest.mark.asyncio
async def test_reativado_volta_a_renovar(admin_engine):
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        await tr.reativar_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer("Recurso deferido."), usuario_id=uid,
        )

    alvara = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)

    async with _sm(admin_engine)() as db:
        renovado = await tr.renovar_alvara(
            db, tenant_id=tid, alvara_id=alvara.id,
            payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
        )
    assert renovado.id != alvara.id
    assert renovado.renovado_de == alvara.id


@pytest.mark.asyncio
async def test_suspenso_ainda_emite_alvara_novo(admin_engine):
    """ANTI-DERIVA: `criar_alvara` (emissão) não passa pelo gate — só a renovação."""
    t = await _provisionar(admin_engine)
    tid = t.id
    perm = await _permissionario(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, perm, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )

    novo = await _alvara_vencido(admin_engine, tid, id_permissionario=perm.id)
    assert novo.id is not None


@pytest.mark.asyncio
async def test_empresa_suspensa_bloqueia_renovacao_do_alvara_da_empresa(admin_engine):
    """Convocação de EMPRESA suspensa bloqueia renovação de alvará de empresa.

    Confere o vocabulário feminino `suspensa` (adjetivo em português para
    empresa) contra o valor REAL gravado na convocação — que é `SITUACAO_SUSPENSO`
    ("suspenso", sem flexão de gênero: é constante única do módulo). A armadilha
    nº 1 do módulo é assumir que o texto muda com o gênero do titular.
    """
    t = await _provisionar(admin_engine)
    tid = t.id
    emp = await _empresa_ativa(admin_engine, tid)
    ciclo = await _ciclo_vencido(admin_engine, tid)
    _c, conv = await _convocacao(admin_engine, tid, emp, ciclo=ciclo)
    uid = await _um_usuario(admin_engine, tid)

    async with _sm(admin_engine)() as db:
        await tr.suspender_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id,
            payload=_parecer(), usuario_id=uid,
        )
    async with _sm(admin_engine)() as db:
        recarregada = await tr.obter_convocacao(
            db, tenant_id=tid, convocacao_id=conv.id
        )
    assert recarregada.situacao == "suspenso"
    assert recarregada.situacao == tr.SITUACAO_SUSPENSO

    alvara = await _alvara_vencido(admin_engine, tid, id_empresa=emp.id)

    async with _sm(admin_engine)() as db:
        with pytest.raises(HTTPException) as e:
            await tr.renovar_alvara(
                db, tenant_id=tid, alvara_id=alvara.id,
                payload=AlvaraRenovarInput(data_validade=HOJE + timedelta(days=365)),
            )
    assert e.value.status_code == 409
    assert "reativação" in e.value.detail


@pytest.mark.asyncio
async def test_http_usuario_comum_toma_409_na_renovacao(admin_engine):
    tenant = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            await contratar(s, tenant.id, ["transporte"])
            await s.commit()

        perm = await _permissionario(admin_engine, tenant.id, nome="Suspenso HTTP")
        ciclo = await _ciclo_vencido(admin_engine, tenant.id)
        _c, conv = await _convocacao(admin_engine, tenant.id, perm, ciclo=ciclo)
        uid_dec = await _um_usuario(admin_engine, tenant.id)

        async with _sm(admin_engine)() as db:
            await tr.suspender_convocacao(
                db, tenant_id=tenant.id, convocacao_id=conv.id,
                payload=_parecer(), usuario_id=uid_dec,
            )

        alvara = await _alvara_vencido(admin_engine, tenant.id, id_permissionario=perm.id)

        uid = await _cria_usuario_comum_transporte(admin_engine, tenant.id)
        _as_user(admin_engine, uid, tenant.id, tenant.slug)()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                f"/api/v2/transporte-regulado/alvaras/{alvara.id}/renovar",
                json={"data_validade": (HOJE + timedelta(days=365)).isoformat()},
            )
        assert r.status_code == 409, r.text
        assert "reativação" in r.json()["detail"]
    finally:
        # `_encerrar_arreio` não conhece `alvara` (nasceu antes desta fatia
        # criar alvará em cima de um cenário HTTP); sem isto o DELETE de
        # permissionario dela esbarra na FK e mascara o resultado do teste.
        async with _sm(admin_engine)() as s:
            await s.execute(
                text("DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t"),
                {"t": tenant.id},
            )
            await s.commit()
        await _encerrar_arreio(admin_engine, tenant.id)

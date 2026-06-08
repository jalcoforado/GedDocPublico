"""Frota (operacional) — ocorrências internas de veículos.

Cobre o serviço de domínio (`services/frota.py`): CRUD tenant-scoped, validação
same-tenant de veículo/motorista, ciclo aberta → em_tratamento → resolvida/
cancelada (sem alterar a situação do veículo), data_resolucao server-side,
whitelist, filtros e soft-delete.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    MotoristaCreate,
    VeiculoCreate,
    VeiculoOcorrenciaCreate,
    VeiculoOcorrenciaResolver,
    VeiculoOcorrenciaUpdate,
)
from app.services import frota as frota_svc
from app.services.provisioning_tenant import provisionar_tenant

HOJE = date.today()
_placa_seq = itertools.count(1)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("ocor")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Ocor", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    return f"AAA{next(_placa_seq) % 10000:04d}"


async def _veiculo(engine, tenant_id: int, *, situacao="disponivel") -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), situacao=situacao),
        )
        return v.id


async def _motorista(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        m = await frota_svc.criar_motorista(
            s, tenant_id=tenant_id,
            payload=MotoristaCreate(
                nome="Cond", cpf=str(uuid.uuid4().int)[:11], cnh_numero=str(uuid.uuid4().int)[:11],
                cnh_categoria="B", cnh_validade=date(2031, 1, 1),
            ),
        )
        return m.id


async def _criar_oc(engine, tenant_id, id_veiculo, *, tipo="avaria", gravidade="media",
                    id_motorista=None):
    async with _sm(engine)() as s:
        return await frota_svc.criar_ocorrencia(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoOcorrenciaCreate(
                id_veiculo=id_veiculo, tipo=tipo, descricao="ocorrência teste",
                gravidade=gravidade, id_motorista=id_motorista,
            ),
        )


async def _veiculo_situacao(engine, veiculo_id: int) -> str:
    async with _sm(engine)() as s:
        return (
            await s.execute(
                text("SELECT situacao FROM frota.veiculo WHERE id=:i"), {"i": veiculo_id}
            )
        ).scalar_one()


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM frota.veiculo_ocorrencia WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_vistoria WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_abastecimento WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_manutencao WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo_documento WHERE tenant_id=:t",
            "DELETE FROM frota.solicitacao_veiculo WHERE tenant_id=:t",
            "DELETE FROM frota.motorista WHERE tenant_id=:t",
            "DELETE FROM frota.veiculo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_grupo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.audit_log WHERE tenant_id=:t",
            "DELETE FROM utils.usuario WHERE tenant_id=:t",
            "DELETE FROM protocolos.tipo_manifestante WHERE tenant_id=:t",
            "DELETE FROM utils.unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM utils.tipo_unidade_trabalho WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant WHERE id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


# ============================ Criação =======================================
async def test_criar_ocorrencia_aberta_sem_efeito_no_veiculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, situacao="disponivel")
        o = await _criar_oc(admin_engine, t.id, v, tipo="sinistro", gravidade="critica")
        assert o.status == "aberta"
        assert o.gravidade == "critica"
        assert o.data_ocorrencia == HOJE          # default server-side
        assert o.data_resolucao is None
        assert await _veiculo_situacao(admin_engine, v) == "disponivel"  # intocado
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_ocorrencia_veiculo_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:
            await _criar_oc(admin_engine, b.id, va)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_bloqueia_motorista_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        vb = await _veiculo(admin_engine, b.id)
        ma = await _motorista(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:
            await _criar_oc(admin_engine, b.id, vb, id_motorista=ma)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


def test_tipo_e_descricao_validados():
    with pytest.raises(ValidationError):
        VeiculoOcorrenciaCreate(id_veiculo=1, tipo="invalido", descricao="x")
    with pytest.raises(ValidationError):
        VeiculoOcorrenciaCreate(id_veiculo=1, tipo="avaria", descricao="")


# ============================ Ciclo de status ===============================
async def test_iniciar_resolver_grava_data_resolucao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        o = await _criar_oc(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            em_trat = await frota_svc.iniciar_tratamento_ocorrencia(
                s, tenant_id=t.id, ocorrencia_id=o.id
            )
        assert em_trat.status == "em_tratamento"
        async with _sm(admin_engine)() as s:
            resolvida = await frota_svc.resolver_ocorrencia(
                s, tenant_id=t.id, ocorrencia_id=o.id,
                payload=VeiculoOcorrenciaResolver(providencias="trocado o para-choque"),
            )
        assert resolvida.status == "resolvida"
        assert resolvida.data_resolucao == HOJE       # server-side
        assert resolvida.providencias == "trocado o para-choque"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_resolver_cancelada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        o = await _criar_oc(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            await frota_svc.cancelar_ocorrencia(s, tenant_id=t.id, ocorrencia_id=o.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.resolver_ocorrencia(
                    s, tenant_id=t.id, ocorrencia_id=o.id,
                    payload=VeiculoOcorrenciaResolver(),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem / filtros ============================
async def test_listar_filtra_status(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        o1 = await _criar_oc(admin_engine, t.id, v)
        await _criar_oc(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            await frota_svc.resolver_ocorrencia(
                s, tenant_id=t.id, ocorrencia_id=o1.id, payload=VeiculoOcorrenciaResolver()
            )
        async with _sm(admin_engine)() as s:
            abertas = await frota_svc.listar_ocorrencias(s, tenant_id=t.id, status_filtro="aberta")
            resolvidas = await frota_svc.listar_ocorrencias(s, tenant_id=t.id, status_filtro="resolvida")
        assert len(abertas) == 1
        assert len(resolvidas) == 1
        assert resolvidas[0].id == o1.id
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Update / whitelist ============================
async def test_update_whitelist_e_bloqueio_em_resolvida(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        o = await _criar_oc(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            atualizada = await frota_svc.atualizar_ocorrencia(
                s, tenant_id=t.id, ocorrencia_id=o.id,
                payload=VeiculoOcorrenciaUpdate(gravidade="alta", descricao="atualizada"),
            )
        assert atualizada.gravidade == "alta"
        assert atualizada.descricao == "atualizada"
        async with _sm(admin_engine)() as s:
            await frota_svc.resolver_ocorrencia(
                s, tenant_id=t.id, ocorrencia_id=o.id, payload=VeiculoOcorrenciaResolver()
            )
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.atualizar_ocorrencia(
                    s, tenant_id=t.id, ocorrencia_id=o.id,
                    payload=VeiculoOcorrenciaUpdate(gravidade="baixa"),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = VeiculoOcorrenciaUpdate.model_validate(
        {"gravidade": "alta", "status": "resolvida", "data_resolucao": "2030-01-01",
         "id_veiculo": 7, "tenant_id": 1, "id": 9, "excluido": True}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"gravidade": "alta"}
    for proibido in ("status", "data_resolucao", "id_veiculo", "tenant_id", "id", "excluido"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Soft-delete / cross-tenant ====================
async def test_delete_soft_e_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        o = await _criar_oc(admin_engine, a.id, va)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_ocorrencia(s, tenant_id=b.id, ocorrencia_id=o.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_ocorrencia(s, tenant_id=a.id, ocorrencia_id=o.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_ocorrencia(s, tenant_id=a.id, ocorrencia_id=o.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM frota.veiculo_ocorrencia WHERE id=:i"),
                    {"i": o.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)

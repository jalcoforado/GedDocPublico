"""Frota (operacional) — manutenção preventiva/corretiva de veículos.

Cobre o serviço de domínio (`services/frota.py`): CRUD tenant-scoped, ciclo
aberta → em_andamento → concluida/cancelada, efeitos na `situacao` do veículo
(abrir põe em 'manutencao' se 'disponivel'; concluir/cancelar libera só se em
'manutencao', sem sobrescrever 'em_uso'), whitelist e soft-delete. Mesmo padrão
dos demais testes de frota.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    VeiculoCreate,
    VeiculoManutencaoConcluir,
    VeiculoManutencaoCreate,
    VeiculoManutencaoUpdate,
)
from app.services import frota as frota_svc
from app.services.provisioning_tenant import provisionar_tenant

# `HOJE` é fixo no import de propósito: serve de BASE ESTÁVEL para deslocamentos
# (`HOJE + timedelta(...)`) dentro de um teste. Não use em asserção contra data
# gerada pelo SERVIDOR: a suíte roda por horas e, quando cruza a meia-noite, o
# servidor devolve o dia seguinte e a comparação estoura. Aconteceu em
# 2026-08-15→16, em cinco testes de frota, numa rodada de 7 h 22. Nesses casos
# compare com `date.today()` avaliado NA HORA da asserção.
HOJE = date.today()
_placa_seq = itertools.count(1)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("manut")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Manut", admin_email=f"{slug}@t.local",
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


async def _criar_manut(engine, tenant_id, id_veiculo, *, tipo="preventiva", descricao="rev"):
    async with _sm(engine)() as s:
        return await frota_svc.criar_manutencao(
            s, tenant_id=tenant_id, id_veiculo=id_veiculo,
            payload=VeiculoManutencaoCreate(
                id_veiculo=id_veiculo, tipo=tipo, descricao=descricao
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


# ============================ Criação + efeito no veículo ===================
async def test_criar_manutencao_poe_veiculo_em_manutencao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, situacao="disponivel")
        m = await _criar_manut(admin_engine, t.id, v, tipo="corretiva")
        assert m.status == "aberta"
        assert m.tipo == "corretiva"
        assert m.data_abertura == date.today()  # default server-side; ver a nota de HOJE
        assert await _veiculo_situacao(admin_engine, v) == "manutencao"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_abrir_manutencao_nao_sobrescreve_em_uso(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id, situacao="em_uso")
        await _criar_manut(admin_engine, t.id, v)
        assert await _veiculo_situacao(admin_engine, v) == "em_uso"  # intocado
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_criar_manutencao_cross_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        with pytest.raises(HTTPException) as exc:
            await _criar_manut(admin_engine, b.id, va)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Ciclo de status ===============================
async def test_iniciar_e_concluir_libera_veiculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        m = await _criar_manut(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            iniciada = await frota_svc.iniciar_manutencao(s, tenant_id=t.id, manutencao_id=m.id)
        assert iniciada.status == "em_andamento"
        async with _sm(admin_engine)() as s:
            concluida = await frota_svc.concluir_manutencao(
                s, tenant_id=t.id, manutencao_id=m.id,
                payload=VeiculoManutencaoConcluir(custo_final=250.50),
            )
        assert concluida.status == "concluida"
        assert concluida.data_conclusao == date.today()  # server-side; ver a nota de HOJE
        assert float(concluida.custo_final) == 250.50
        assert await _veiculo_situacao(admin_engine, v) == "disponivel"  # liberado
    finally:
        await _cleanup(admin_engine, t.id)


async def test_concluir_nao_sobrescreve_veiculo_em_uso(admin_engine):
    """Se o veículo foi para 'em_uso' durante a manutenção (cenário de borda),
    concluir NÃO o devolve a 'disponivel'."""
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)  # disponivel -> manutencao
        m = await _criar_manut(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            await s.execute(
                text("UPDATE frota.veiculo SET situacao='em_uso' WHERE id=:i"), {"i": v}
            )
            await s.commit()
        async with _sm(admin_engine)() as s:
            await frota_svc.concluir_manutencao(
                s, tenant_id=t.id, manutencao_id=m.id,
                payload=VeiculoManutencaoConcluir(),
            )
        assert await _veiculo_situacao(admin_engine, v) == "em_uso"  # não sobrescreve
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_concluir_cancelada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        m = await _criar_manut(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            await frota_svc.cancelar_manutencao(s, tenant_id=t.id, manutencao_id=m.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.concluir_manutencao(
                    s, tenant_id=t.id, manutencao_id=m.id,
                    payload=VeiculoManutencaoConcluir(),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_cancelar_libera_veiculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        m = await _criar_manut(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            cancelada = await frota_svc.cancelar_manutencao(s, tenant_id=t.id, manutencao_id=m.id)
        assert cancelada.status == "cancelada"
        assert await _veiculo_situacao(admin_engine, v) == "disponivel"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem / filtros ============================
async def test_listar_filtra_por_status_e_veiculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v1 = await _veiculo(admin_engine, t.id)
        v2 = await _veiculo(admin_engine, t.id)
        m1 = await _criar_manut(admin_engine, t.id, v1)
        await _criar_manut(admin_engine, t.id, v2)
        async with _sm(admin_engine)() as s:
            await frota_svc.cancelar_manutencao(s, tenant_id=t.id, manutencao_id=m1.id)
        async with _sm(admin_engine)() as s:
            por_veiculo = await frota_svc.listar_manutencoes(s, tenant_id=t.id, id_veiculo=v1)
            abertas = await frota_svc.listar_manutencoes(s, tenant_id=t.id, status_filtro="aberta")
        assert {x.id for x in por_veiculo} == {m1.id}
        assert m1.id not in {x.id for x in abertas}   # m1 foi cancelada
        assert len(abertas) == 1                       # só a de v2 segue aberta
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Update / whitelist ============================
async def test_update_whitelist_e_bloqueio_em_concluida(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        v = await _veiculo(admin_engine, t.id)
        m = await _criar_manut(admin_engine, t.id, v)
        async with _sm(admin_engine)() as s:
            atualizada = await frota_svc.atualizar_manutencao(
                s, tenant_id=t.id, manutencao_id=m.id,
                payload=VeiculoManutencaoUpdate(fornecedor="Oficina X", custo_estimado=100),
            )
        assert atualizada.fornecedor == "Oficina X"
        assert float(atualizada.custo_estimado) == 100
        # concluir e tentar editar -> 409
        async with _sm(admin_engine)() as s:
            await frota_svc.concluir_manutencao(
                s, tenant_id=t.id, manutencao_id=m.id, payload=VeiculoManutencaoConcluir()
            )
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.atualizar_manutencao(
                    s, tenant_id=t.id, manutencao_id=m.id,
                    payload=VeiculoManutencaoUpdate(fornecedor="Y"),
                )
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = VeiculoManutencaoUpdate.model_validate(
        {"fornecedor": "X", "status": "concluida", "tenant_id": 1, "id": 9,
         "id_veiculo": 7, "excluido": True, "data_conclusao": "2030-01-01",
         "custo_final": 999}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"fornecedor": "X"}
    for proibido in ("status", "tenant_id", "id", "id_veiculo", "excluido",
                     "data_conclusao", "custo_final"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Soft-delete / cross-tenant ====================
async def test_delete_soft_e_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        va = await _veiculo(admin_engine, a.id)
        m = await _criar_manut(admin_engine, a.id, va)
        # cross-tenant detalhe -> 404
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_manutencao(s, tenant_id=b.id, manutencao_id=m.id)
            assert exc.value.status_code == 404
        # soft delete
        async with _sm(admin_engine)() as s:
            await frota_svc.excluir_manutencao(s, tenant_id=a.id, manutencao_id=m.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.obter_manutencao(s, tenant_id=a.id, manutencao_id=m.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM frota.veiculo_manutencao WHERE id=:i"),
                    {"i": m.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)

"""Frota PR-4 — designação de veículo/motorista em solicitação aprovada.

Cobre o serviço de domínio (`services/frota.py`): regras de status da solicitação,
disponibilidade do veículo (só 'disponivel'), situação do motorista (só 'ativo'),
obrigatoriedade de motorista, designador/data server-side, redesignação e limpeza.
Mesmo padrão dos demais testes de frota (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.frota import (
    MotoristaCreate,
    SolicitacaoVeiculoCreate,
    SolicitacaoVeiculoDesignar,
    VeiculoCreate,
)
from app.services import frota as frota_svc
from app.services.provisioning_tenant import provisionar_tenant

SAIDA = datetime(2030, 1, 10, 8, 0, 0)
RETORNO = datetime(2030, 1, 10, 18, 0, 0)


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("desig")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Desig", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


async def _usuario_id(engine, tenant_id: int) -> int:
    async with _sm(engine)() as s:
        return int(
            (
                await s.execute(
                    text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                    {"t": tenant_id},
                )
            ).scalar_one()
        )


def _placa() -> str:
    return "AAA" + str(uuid.uuid4().int)[:1] + "A" + str(uuid.uuid4().int)[:2]


async def _veiculo(engine, tenant_id: int, situacao: str = "disponivel") -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), situacao=situacao),
        )
        return v.id


async def _motorista(engine, tenant_id: int, situacao: str = "ativo") -> int:
    async with _sm(engine)() as s:
        m = await frota_svc.criar_motorista(
            s, tenant_id=tenant_id,
            payload=MotoristaCreate(
                nome="Cond", cpf=str(uuid.uuid4().int)[:11], cnh_numero=str(uuid.uuid4().int)[:11],
                cnh_categoria="B", cnh_validade=datetime(2031, 1, 1).date(), situacao=situacao,
            ),
        )
        return m.id


async def _sol(engine, tenant_id: int, uid: int, *, necessita=False, status_final="aprovada") -> int:
    async with _sm(engine)() as s:
        sol = await frota_svc.criar_solicitacao(
            s, tenant_id=tenant_id, id_usuario_solicitante=uid,
            payload=SolicitacaoVeiculoCreate(
                finalidade="F", destino="D", data_saida_prevista=SAIDA,
                data_retorno_prevista=RETORNO, quantidade_passageiros=2,
                necessita_motorista=necessita,
            ),
        )
    sid = sol.id
    if status_final == "aprovada":
        async with _sm(engine)() as s:
            await frota_svc.aprovar_solicitacao(s, tenant_id=tenant_id, solicitacao_id=sid)
    elif status_final == "rejeitada":
        async with _sm(engine)() as s:
            await frota_svc.rejeitar_solicitacao(s, tenant_id=tenant_id, solicitacao_id=sid, justificativa="x")
    elif status_final == "cancelada":
        async with _sm(engine)() as s:
            await frota_svc.cancelar_solicitacao(s, tenant_id=tenant_id, solicitacao_id=sid)
    # "solicitada" => deixa como está
    return sid


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
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


async def _designar(engine, tenant_id, sid, uid, *, id_veiculo, id_motorista=None, obs=None):
    async with _sm(engine)() as s:
        return await frota_svc.designar_solicitacao(
            s, tenant_id=tenant_id, solicitacao_id=sid, id_usuario_designador=uid,
            payload=SolicitacaoVeiculoDesignar(
                id_veiculo=id_veiculo, id_motorista=id_motorista, observacoes_designacao=obs
            ),
        )


# ---------- designação feliz ----------
async def test_designar_veiculo_em_aprovada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)
        v = await _veiculo(admin_engine, t.id)
        d = await _designar(admin_engine, t.id, sid, uid, id_veiculo=v, obs="ok")
        assert d.id_veiculo_designado == v
        assert d.id_motorista_designado is None
        assert d.id_usuario_designador == uid          # server-side
        assert d.data_designacao is not None           # server-side
        assert d.observacoes_designacao == "ok"
        assert d.status == "aprovada"                  # status não muda
    finally:
        await _cleanup(admin_engine, t.id)


async def test_designar_veiculo_e_motorista_quando_necessita(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, necessita=True)
        v = await _veiculo(admin_engine, t.id)
        m = await _motorista(admin_engine, t.id, situacao="ativo")
        d = await _designar(admin_engine, t.id, sid, uid, id_veiculo=v, id_motorista=m)
        assert d.id_veiculo_designado == v and d.id_motorista_designado == m
    finally:
        await _cleanup(admin_engine, t.id)


async def test_rejeita_designacao_sem_motorista_quando_necessita(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, necessita=True)
        v = await _veiculo(admin_engine, t.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=v)
        assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- status da solicitação ----------
@pytest.mark.parametrize("st", ["solicitada", "rejeitada", "cancelada"])
async def test_bloqueia_designacao_fora_de_aprovada(admin_engine, st):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, status_final=st)
        v = await _veiculo(admin_engine, t.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=v)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- veículo: só 'disponivel' ----------
@pytest.mark.parametrize("sit", ["em_uso", "manutencao", "inativo", "baixado"])
async def test_bloqueia_veiculo_nao_disponivel(admin_engine, sit):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)
        v = await _veiculo(admin_engine, t.id, situacao=sit)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=v)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_veiculo_inexistente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=9999999)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_veiculo_de_outro_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        sid = await _sol(admin_engine, a.id, ua)
        vb = await _veiculo(admin_engine, b.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, a.id, sid, ua, id_veiculo=vb)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- motorista: só 'ativo' ----------
@pytest.mark.parametrize("sit", ["inativo", "afastado"])
async def test_bloqueia_motorista_nao_ativo(admin_engine, sit):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, necessita=True)
        v = await _veiculo(admin_engine, t.id)
        m = await _motorista(admin_engine, t.id, situacao=sit)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=v, id_motorista=m)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_motorista_inexistente(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, necessita=True)
        v = await _veiculo(admin_engine, t.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, t.id, sid, uid, id_veiculo=v, id_motorista=9999999)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_motorista_de_outro_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        sid = await _sol(admin_engine, a.id, ua, necessita=True)
        va = await _veiculo(admin_engine, a.id)
        mb = await _motorista(admin_engine, b.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, a.id, sid, ua, id_veiculo=va, id_motorista=mb)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- redesignação ----------
async def test_redesignacao_enquanto_aprovada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)
        v1 = await _veiculo(admin_engine, t.id)
        v2 = await _veiculo(admin_engine, t.id)
        await _designar(admin_engine, t.id, sid, uid, id_veiculo=v1)
        d2 = await _designar(admin_engine, t.id, sid, uid, id_veiculo=v2)
        assert d2.id_veiculo_designado == v2
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- limpar designação ----------
async def test_limpar_designacao_em_aprovada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)
        v = await _veiculo(admin_engine, t.id)
        await _designar(admin_engine, t.id, sid, uid, id_veiculo=v, obs="x")
        async with _sm(admin_engine)() as s:
            d = await frota_svc.limpar_designacao(s, tenant_id=t.id, solicitacao_id=sid)
        assert d.id_veiculo_designado is None
        assert d.id_motorista_designado is None
        assert d.id_usuario_designador is None
        assert d.data_designacao is None
        assert d.observacoes_designacao is None
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.parametrize("st", ["solicitada", "rejeitada", "cancelada"])
async def test_bloqueia_limpar_fora_de_aprovada(admin_engine, st):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, status_final=st)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.limpar_designacao(s, tenant_id=t.id, solicitacao_id=sid)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ---------- cross-tenant na própria solicitação ----------
async def test_designar_solicitacao_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        ub = await _usuario_id(admin_engine, b.id)
        sid = await _sol(admin_engine, a.id, ua)
        vb = await _veiculo(admin_engine, b.id)
        with pytest.raises(HTTPException) as exc:
            await _designar(admin_engine, b.id, sid, ub, id_veiculo=vb)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ---------- schema Designar não aceita campos proibidos ----------
def test_designar_schema_descarta_proibidos():
    m = SolicitacaoVeiculoDesignar.model_validate(
        {"id_veiculo": 5, "id_motorista": None, "tenant_id": 9, "status": "aprovada",
         "id_usuario_solicitante": 7, "id_usuario_designador": 3}
    )
    dump = m.model_dump()
    assert dump == {"id_veiculo": 5, "id_motorista": None, "observacoes_designacao": None}
    for proibido in ("tenant_id", "status", "id_usuario_solicitante", "id_usuario_designador"):
        assert proibido not in dump
        assert not hasattr(m, proibido)

"""Frota PR-5 — saída e retorno real do veículo.

Cobre o serviço de domínio (`services/frota.py`): ciclo operacional
aprovada → em_uso → concluida, efeitos na situação/quilometragem do veículo,
datas/usuários server-side, regras de km e bloqueios de cancelamento em estados
operacionais. Mesmo padrão dos demais testes de frota (provisionar_tenant +
admin_engine).
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
    SolicitacaoVeiculoRegistrarRetorno,
    SolicitacaoVeiculoRegistrarSaida,
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
    slug = _slug("sair")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Saida", admin_email=f"{slug}@t.local",
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


async def _veiculo(engine, tenant_id: int, *, situacao="disponivel", km=0) -> int:
    async with _sm(engine)() as s:
        v = await frota_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoCreate(placa=_placa(), situacao=situacao, quilometragem_atual=km),
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


async def _designar(engine, tenant_id, sid, uid, *, id_veiculo, id_motorista=None):
    async with _sm(engine)() as s:
        await frota_svc.designar_solicitacao(
            s, tenant_id=tenant_id, solicitacao_id=sid, id_usuario_designador=uid,
            payload=SolicitacaoVeiculoDesignar(id_veiculo=id_veiculo, id_motorista=id_motorista),
        )


async def _saida(engine, tenant_id, sid, uid, *, km_saida, obs=None):
    async with _sm(engine)() as s:
        return await frota_svc.registrar_saida(
            s, tenant_id=tenant_id, solicitacao_id=sid, id_usuario_registro=uid,
            payload=SolicitacaoVeiculoRegistrarSaida(km_saida=km_saida, observacoes_saida=obs),
        )


async def _retorno(engine, tenant_id, sid, uid, *, km_retorno, obs=None):
    async with _sm(engine)() as s:
        return await frota_svc.registrar_retorno(
            s, tenant_id=tenant_id, solicitacao_id=sid, id_usuario_registro=uid,
            payload=SolicitacaoVeiculoRegistrarRetorno(km_retorno=km_retorno, observacoes_retorno=obs),
        )


async def _veiculo_estado(engine, veiculo_id: int):
    async with _sm(engine)() as s:
        return (
            await s.execute(
                text("SELECT situacao, quilometragem_atual FROM frota.veiculo WHERE id=:i"),
                {"i": veiculo_id},
            )
        ).one()


async def _set_veiculo_situacao(engine, veiculo_id: int, situacao: str) -> None:
    async with _sm(engine)() as s:
        await s.execute(
            text("UPDATE frota.veiculo SET situacao=:s WHERE id=:i"),
            {"s": situacao, "i": veiculo_id},
        )
        await s.commit()


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


async def _preparar(engine, *, necessita=False, km_veiculo=0):
    """Tenant + usuário + solicitação aprovada e designada com veículo."""
    t = await _provisionar(engine)
    uid = await _usuario_id(engine, t.id)
    sid = await _sol(engine, t.id, uid, necessita=necessita)
    v = await _veiculo(engine, t.id, km=km_veiculo)
    m = await _motorista(engine, t.id) if necessita else None
    await _designar(engine, t.id, sid, uid, id_veiculo=v, id_motorista=m)
    return t, uid, sid, v


# ============================ Saída (caminho feliz) ==========================
async def test_registrar_saida_em_aprovada_designada(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=1000)
    try:
        d = await _saida(admin_engine, t.id, sid, uid, km_saida=1000, obs="saiu ok")
        assert d.status == "em_uso"
        assert d.km_saida == 1000
        assert d.observacoes_saida == "saiu ok"
        assert d.data_saida_real is not None             # server-side
        assert d.id_usuario_registro_saida == uid        # server-side
        sit, km = await _veiculo_estado(admin_engine, v)
        assert sit == "em_uso"                            # veículo passa a em_uso
        assert km == 1000                                 # km NÃO muda na saída
    finally:
        await _cleanup(admin_engine, t.id)


async def test_saida_com_motorista_quando_necessita(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, necessita=True)
    try:
        d = await _saida(admin_engine, t.id, sid, uid, km_saida=0)
        assert d.status == "em_uso"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Saída (bloqueios) ==============================
async def test_bloqueia_saida_sem_veiculo_designado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid)  # aprovada, sem designar
        with pytest.raises(HTTPException) as exc:
            await _saida(admin_engine, t.id, sid, uid, km_saida=10)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_saida_sem_motorista_quando_necessita(admin_engine):
    """Designação exige motorista quando necessita; o bloqueio operacional é
    garantido removendo o motorista designado direto no banco antes da saída."""
    t, uid, sid, v = await _preparar(admin_engine, necessita=True)
    try:
        async with _sm(admin_engine)() as s:
            await s.execute(
                text(
                    "UPDATE frota.solicitacao_veiculo SET id_motorista_designado=NULL WHERE id=:i"
                ),
                {"i": sid},
            )
            await s.commit()
        with pytest.raises(HTTPException) as exc:
            await _saida(admin_engine, t.id, sid, uid, km_saida=0)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.parametrize("sit", ["em_uso", "manutencao", "inativo", "baixado"])
async def test_bloqueia_saida_veiculo_nao_disponivel(admin_engine, sit):
    t, uid, sid, v = await _preparar(admin_engine)
    try:
        await _set_veiculo_situacao(admin_engine, v, sit)
        with pytest.raises(HTTPException) as exc:
            await _saida(admin_engine, t.id, sid, uid, km_saida=10)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.parametrize("st", ["solicitada", "rejeitada", "cancelada"])
async def test_bloqueia_saida_fora_de_aprovada(admin_engine, st):
    t = await _provisionar(admin_engine)
    try:
        uid = await _usuario_id(admin_engine, t.id)
        sid = await _sol(admin_engine, t.id, uid, status_final=st)
        with pytest.raises(HTTPException) as exc:
            await _saida(admin_engine, t.id, sid, uid, km_saida=10)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_saida_duplicada(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=100)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=100)
        with pytest.raises(HTTPException) as exc:  # já está em_uso
            await _saida(admin_engine, t.id, sid, uid, km_saida=100)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_km_saida_menor_que_quilometragem_atual(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=5000)
    try:
        with pytest.raises(HTTPException) as exc:
            await _saida(admin_engine, t.id, sid, uid, km_saida=4999)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Retorno (caminho feliz) =======================
async def test_registrar_retorno_apos_saida(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=1000)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=1000)
        d = await _retorno(admin_engine, t.id, sid, uid, km_retorno=1250, obs="voltou")
        assert d.status == "concluida"
        assert d.km_retorno == 1250
        assert d.observacoes_retorno == "voltou"
        assert d.data_retorno_real is not None            # server-side
        assert d.id_usuario_registro_retorno == uid       # server-side
        sit, km = await _veiculo_estado(admin_engine, v)
        assert sit == "disponivel"                        # veículo liberado
        assert km == 1250                                 # quilometragem atualizada
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Retorno (bloqueios) ===========================
async def test_bloqueia_retorno_sem_saida(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine)  # aprovada/designada, sem saída
    try:
        with pytest.raises(HTTPException) as exc:
            await _retorno(admin_engine, t.id, sid, uid, km_retorno=10)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_retorno_duplicado(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=100)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=100)
        await _retorno(admin_engine, t.id, sid, uid, km_retorno=200)
        with pytest.raises(HTTPException) as exc:  # já está concluida
            await _retorno(admin_engine, t.id, sid, uid, km_retorno=300)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_km_retorno_menor_que_km_saida(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=1000)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=1000)
        with pytest.raises(HTTPException) as exc:
            await _retorno(admin_engine, t.id, sid, uid, km_retorno=999)
        assert exc.value.status_code == 400
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cancelamento bloqueado ========================
async def test_bloqueia_cancelar_em_uso(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=100)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=100)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.cancelar_solicitacao(s, tenant_id=t.id, solicitacao_id=sid)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_bloqueia_cancelar_concluida(admin_engine):
    t, uid, sid, v = await _preparar(admin_engine, km_veiculo=100)
    try:
        await _saida(admin_engine, t.id, sid, uid, km_saida=100)
        await _retorno(admin_engine, t.id, sid, uid, km_retorno=200)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await frota_svc.cancelar_solicitacao(s, tenant_id=t.id, solicitacao_id=sid)
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Cross-tenant ==================================
async def test_saida_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        ua = await _usuario_id(admin_engine, a.id)
        ub = await _usuario_id(admin_engine, b.id)
        sid = await _sol(admin_engine, a.id, ua)
        va = await _veiculo(admin_engine, a.id)
        await _designar(admin_engine, a.id, sid, ua, id_veiculo=va)
        with pytest.raises(HTTPException) as exc:  # tenant B não enxerga a sol de A
            await _saida(admin_engine, b.id, sid, ub, km_saida=10)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Schemas: whitelist ============================
def test_registrar_saida_schema_descarta_proibidos():
    m = SolicitacaoVeiculoRegistrarSaida.model_validate(
        {"km_saida": 10, "observacoes_saida": "x", "status": "em_uso",
         "data_saida_real": "2030-01-01T00:00:00", "id_usuario_registro_saida": 9,
         "tenant_id": 1}
    )
    dump = m.model_dump()
    assert dump == {"km_saida": 10, "observacoes_saida": "x"}
    for proibido in ("status", "data_saida_real", "id_usuario_registro_saida", "tenant_id"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


def test_registrar_retorno_schema_descarta_proibidos():
    m = SolicitacaoVeiculoRegistrarRetorno.model_validate(
        {"km_retorno": 20, "observacoes_retorno": "y", "status": "concluida",
         "data_retorno_real": "2030-01-01T00:00:00", "id_usuario_registro_retorno": 9,
         "tenant_id": 1}
    )
    dump = m.model_dump()
    assert dump == {"km_retorno": 20, "observacoes_retorno": "y"}
    for proibido in ("status", "data_retorno_real", "id_usuario_registro_retorno", "tenant_id"):
        assert proibido not in dump
        assert not hasattr(m, proibido)

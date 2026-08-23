"""Transporte Regulado PR-3 — cadastro de Veículos regulados/permissionários.

Cobre o serviço de domínio (`services/transporte_regulado.py`): CRUD tenant-scoped,
normalização/unicidade de placa/renavam/chassi, vínculo obrigatório a permissionário
e/ou empresa (mesmo tenant), isolamento cross-tenant (404), whitelist de edição,
ações de situação (inativar/reativar/suspender) e soft-delete. Mesmo padrão dos
testes de Permissionário e Empresa.

NÃO se relaciona com `frota.veiculo`: a classe é `VeiculoRegulado`
(tabela `transporte_regulado.veiculo`).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.transporte_regulado import (
    EmpresaCreate,
    PermissionarioCreate,
    VeiculoReguladoCreate,
    VeiculoReguladoUpdate,
)
from app.services import transporte_regulado as tr_svc
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("vei")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Vei", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _placa() -> str:
    # 7 alfanuméricos (padrão antigo simplificado): 3 letras + 4 dígitos.
    h = uuid.uuid4().hex.upper()
    letras = "".join(c for c in h if c.isalpha())[:3].ljust(3, "X")
    digitos = "".join(c for c in h if c.isdigit())[:4].ljust(4, "0")
    return f"{letras}{digitos}"


def _renavam() -> str:
    return str(uuid.uuid4().int)[:11]


def _cpf() -> str:
    return str(uuid.uuid4().int)[:11]


def _cnpj() -> str:
    return str(uuid.uuid4().int)[:14]


async def _permissionario(engine, tenant_id):
    async with _sm(engine)() as s:
        return await tr_svc.criar_permissionario(
            s, tenant_id=tenant_id,
            payload=PermissionarioCreate(nome="Dono", cpf=_cpf(), tipo_servico="taxi"),
        )


async def _empresa(engine, tenant_id):
    async with _sm(engine)() as s:
        return await tr_svc.criar_empresa(
            s, tenant_id=tenant_id,
            payload=EmpresaCreate(razao_social="Op LTDA", cnpj=_cnpj(), tipo_servico="taxi"),
        )


async def _criar(engine, tenant_id, *, permissionario=None, empresa=None, placa=None,
                 renavam=None, chassi=None, tipo="taxi", situacao="pendente"):
    async with _sm(engine)() as s:
        return await tr_svc.criar_veiculo(
            s, tenant_id=tenant_id,
            payload=VeiculoReguladoCreate(
                id_permissionario=permissionario, id_empresa=empresa,
                placa=placa or _placa(), renavam=renavam, chassi=chassi,
                marca="Fiat", modelo="Uno", tipo_servico=tipo, situacao=situacao,
            ),
        )


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.veiculo WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
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


# ============================ Criação / vínculo =============================
async def test_criar_veiculo_vinculado_permissionario(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        v = await _criar(admin_engine, t.id, permissionario=p.id, tipo="mototaxi")
        assert v.id is not None
        assert v.tenant_id == t.id
        assert v.id_permissionario == p.id
        assert v.id_empresa is None
        assert v.situacao == "pendente"
        assert v.excluido is False
        assert v.criado_em is not None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_criar_veiculo_vinculado_empresa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        e = await _empresa(admin_engine, t.id)
        v = await _criar(admin_engine, t.id, empresa=e.id)
        assert v.id_empresa == e.id
        assert v.id_permissionario is None
    finally:
        await _cleanup(admin_engine, t.id)


def test_rejeita_veiculo_sem_vinculo():
    with pytest.raises(ValidationError):
        VeiculoReguladoCreate(placa="ABC1234", marca="Fiat", modelo="Uno", tipo_servico="taxi")


def test_placa_normaliza():
    v = VeiculoReguladoCreate(
        id_permissionario=1, placa="abc-1d23", marca="Fiat", modelo="Uno", tipo_servico="taxi"
    )
    assert v.placa == "ABC1D23"


def test_placa_invalida_rejeitada():
    with pytest.raises(ValidationError):
        VeiculoReguladoCreate(
            id_permissionario=1, placa="ABC12", marca="Fiat", modelo="Uno", tipo_servico="taxi"
        )


async def test_placa_duplicada_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        placa = _placa()
        await _criar(admin_engine, t.id, permissionario=p.id, placa=placa)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, permissionario=p.id, placa=placa)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_placa_igual_em_outro_tenant_permitido(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        pa = await _permissionario(admin_engine, a.id)
        pb = await _permissionario(admin_engine, b.id)
        placa = _placa()
        va = await _criar(admin_engine, a.id, permissionario=pa.id, placa=placa)
        vb = await _criar(admin_engine, b.id, permissionario=pb.id, placa=placa)
        assert va.id != vb.id
        assert va.placa == vb.placa == placa
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_placa_reutilizavel_apos_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        placa = _placa()
        v1 = await _criar(admin_engine, t.id, permissionario=p.id, placa=placa)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_veiculo(s, tenant_id=t.id, veiculo_id=v1.id)
        v2 = await _criar(admin_engine, t.id, permissionario=p.id, placa=placa)
        assert v2.id != v1.id
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Renavam / chassi ==============================
def test_renavam_normaliza_e_valida():
    v = VeiculoReguladoCreate(
        id_permissionario=1, placa="ABC1234", marca="Fiat", modelo="Uno",
        tipo_servico="taxi", renavam="123.456.789",
    )
    assert v.renavam == "123456789"
    with pytest.raises(ValidationError):
        VeiculoReguladoCreate(
            id_permissionario=1, placa="ABC1234", marca="Fiat", modelo="Uno",
            tipo_servico="taxi", renavam="123",
        )


async def test_renavam_duplicado_mesmo_tenant_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        renavam = _renavam()
        await _criar(admin_engine, t.id, permissionario=p.id, renavam=renavam)
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, permissionario=p.id, renavam=renavam)
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_chassi_normaliza_e_unicidade(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        v1 = await _criar(admin_engine, t.id, permissionario=p.id, chassi="9bw za 60 0011")
        assert v1.chassi == "9BWZA600011"  # uppercase, sem espaços
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, t.id, permissionario=p.id, chassi="9BWZA600011")
        assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Vínculo cross-tenant ==========================
async def test_vinculo_deve_ser_mesmo_tenant(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        pa = await _permissionario(admin_engine, a.id)
        # permissionário do tenant A não pode vincular veículo do tenant B
        with pytest.raises(HTTPException) as exc:
            await _criar(admin_engine, b.id, permissionario=pa.id)
        assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


async def test_detalhe_cross_tenant_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        pa = await _permissionario(admin_engine, a.id)
        va = await _criar(admin_engine, a.id, permissionario=pa.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_veiculo(s, tenant_id=b.id, veiculo_id=va.id)
            assert exc.value.status_code == 404
    finally:
        await _cleanup(admin_engine, a.id)
        await _cleanup(admin_engine, b.id)


# ============================ Update / whitelist ============================
async def test_update_atualiza_campos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        v = await _criar(admin_engine, t.id, permissionario=p.id)
        async with _sm(admin_engine)() as s:
            up = await tr_svc.atualizar_veiculo(
                s, tenant_id=t.id, veiculo_id=v.id,
                payload=VeiculoReguladoUpdate(cor="Prata", capacidade_passageiros=4),
            )
        assert up.cor == "Prata"
        assert up.capacidade_passageiros == 4
    finally:
        await _cleanup(admin_engine, t.id)


def test_update_schema_descarta_proibidos():
    m = VeiculoReguladoUpdate.model_validate(
        {"cor": "Preto", "tenant_id": 1, "id": 9, "excluido": True,
         "criado_em": "2030-01-01T00:00:00", "atualizado_em": "2030-01-01T00:00:00"}
    )
    dump = m.model_dump(exclude_unset=True)
    assert dump == {"cor": "Preto"}
    for proibido in ("tenant_id", "id", "excluido", "criado_em", "atualizado_em"):
        assert proibido not in dump
        assert not hasattr(m, proibido)


# ============================ Ações de situação =============================
async def test_inativar_reativar_suspender(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        v = await _criar(admin_engine, t.id, permissionario=p.id, situacao="ativo")
        async with _sm(admin_engine)() as s:
            inativo = await tr_svc.set_situacao_veiculo(
                s, tenant_id=t.id, veiculo_id=v.id, situacao="inativo")
        assert inativo.situacao == "inativo"
        async with _sm(admin_engine)() as s:
            ativo = await tr_svc.set_situacao_veiculo(
                s, tenant_id=t.id, veiculo_id=v.id, situacao="ativo")
        assert ativo.situacao == "ativo"
        async with _sm(admin_engine)() as s:
            suspenso = await tr_svc.set_situacao_veiculo(
                s, tenant_id=t.id, veiculo_id=v.id, situacao="suspenso")
        assert suspenso.situacao == "suspenso"
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Listagem / filtros ============================
async def test_listar_filtra_situacao_tipo_e_vinculo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        e = await _empresa(admin_engine, t.id)
        await _criar(admin_engine, t.id, permissionario=p.id, tipo="taxi", situacao="ativo")
        await _criar(admin_engine, t.id, empresa=e.id, tipo="mototaxi", situacao="pendente")
        async with _sm(admin_engine)() as s:
            ativos, _ = await tr_svc.listar_veiculos(s, tenant_id=t.id, situacao="ativo")
            mototaxi, _ = await tr_svc.listar_veiculos(s, tenant_id=t.id, tipo_servico="mototaxi")
            por_emp, _ = await tr_svc.listar_veiculos(s, tenant_id=t.id, id_empresa=e.id)
            por_perm, _ = await tr_svc.listar_veiculos(s, tenant_id=t.id, id_permissionario=p.id)
        assert len(ativos) == 1 and ativos[0].situacao == "ativo"
        assert len(mototaxi) == 1 and mototaxi[0].tipo_servico == "mototaxi"
        assert len(por_emp) == 1 and por_emp[0].id_empresa == e.id
        assert len(por_perm) == 1 and por_perm[0].id_permissionario == p.id
    finally:
        await _cleanup(admin_engine, t.id)


async def test_listar_filtra_por_q_placa_ou_marca_modelo(admin_engine):
    """Seletor de alvo-veículo (Fase B, frontend) precisa buscar por PLACA ou
    MARCA/MODELO. `total` tem de acompanhar `q` — a divergência entre a
    condição da consulta e a da contagem já mordeu este módulo duas vezes."""
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        placa_alvo = _placa()
        async with _sm(admin_engine)() as s:
            v_placa = await tr_svc.criar_veiculo(
                s, tenant_id=t.id,
                payload=VeiculoReguladoCreate(
                    id_permissionario=p.id, placa=placa_alvo,
                    marca="Fiat", modelo="Uno", tipo_servico="taxi",
                ),
            )
        async with _sm(admin_engine)() as s:
            v_modelo = await tr_svc.criar_veiculo(
                s, tenant_id=t.id,
                payload=VeiculoReguladoCreate(
                    id_permissionario=p.id, placa=_placa(),
                    marca="Renault", modelo="Sandero Zebrado", tipo_servico="taxi",
                ),
            )
        async with _sm(admin_engine)() as s:
            # Busca por PLACA.
            rows, total = await tr_svc.listar_veiculos(s, tenant_id=t.id, q=placa_alvo)
            assert total == len(rows) == 1
            assert rows[0].id == v_placa.id

            # Busca por MODELO (substring, case-insensitive).
            rows, total = await tr_svc.listar_veiculos(s, tenant_id=t.id, q="zebrado")
            assert total == len(rows) == 1
            assert rows[0].id == v_modelo.id

            # Sem q, os dois voltam e total bate com a lista.
            rows, total = await tr_svc.listar_veiculos(s, tenant_id=t.id)
            assert total == len(rows) == 2

            # q sem correspondência: lista vazia e total 0 (não diverge).
            rows, total = await tr_svc.listar_veiculos(s, tenant_id=t.id, q="inexistente-xyz")
            assert total == len(rows) == 0
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ Soft-delete ===================================
async def test_delete_faz_soft_delete(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        p = await _permissionario(admin_engine, t.id)
        v = await _criar(admin_engine, t.id, permissionario=p.id)
        async with _sm(admin_engine)() as s:
            await tr_svc.excluir_veiculo(s, tenant_id=t.id, veiculo_id=v.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await tr_svc.obter_veiculo(s, tenant_id=t.id, veiculo_id=v.id)
            assert exc.value.status_code == 404
        async with _sm(admin_engine)() as s:
            excluido = (
                await s.execute(
                    text("SELECT excluido FROM transporte_regulado.veiculo WHERE id=:i"),
                    {"i": v.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _cleanup(admin_engine, t.id)

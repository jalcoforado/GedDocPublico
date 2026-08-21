"""Transporte P6b — linhas (cadastro CRUD).

Spec: `docs/superpowers/specs/2026-08-21-transporte-p6b-linhas`.

Fixtures/estilo seguem `test_transporte_p6_pontos.py`: `admin_engine`,
`_provisionar` (de `test_transporte_p5_2_atendimento`), limpeza no teardown.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text

from app.main import app
from app.schemas.transporte_regulado import LinhaCreate
from app.services import transporte_regulado as tr
from tests.test_transporte_p5_2_atendimento import _provisionar, _sm


async def _operadores(engine, tenant_id: int):
    """Cria uma empresa e um permissionário mínimos e devolve (id_emp, id_perm)."""
    sufixo = uuid.uuid4().hex[:8]
    async with engine.begin() as conn:
        r1 = await conn.execute(text(
            "INSERT INTO transporte_regulado.empresa "
            "(tenant_id, razao_social, cnpj, tipo_servico, situacao, criado_em) "
            "VALUES (:t, :rs, :c, 'transporte_distrital', 'ativa', NOW()) RETURNING id"
        ), {"t": tenant_id, "rs": f"Empresa {sufixo}", "c": sufixo[:8].ljust(14, "0")})
        r2 = await conn.execute(text(
            "INSERT INTO transporte_regulado.permissionario "
            "(tenant_id, nome, cpf, tipo_servico, situacao, criado_em) "
            "VALUES (:t, :n, :c, 'transporte_escolar', 'ativo', NOW()) RETURNING id"
        ), {"t": tenant_id, "n": f"Perm {sufixo}", "c": sufixo[:8].ljust(11, "0")})
        return r1.scalar_one(), r2.scalar_one()


async def _linha(engine, tenant_id: int, *, nome=None, id_empresa=None, id_permissionario=None):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.criar_linha(
                db,
                tenant_id=tenant_id,
                payload=LinhaCreate(
                    nome=nome or f"Linha {uuid.uuid4().hex[:6]}",
                    origem="Centro",
                    destino="Bairro Novo",
                    tipo_servico="transporte_distrital",
                    id_empresa=id_empresa,
                    id_permissionario=id_permissionario,
                ),
            )


async def _limpar(engine, tenant_id: int) -> None:
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.linha_horario WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.linha_parada WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.linha WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest.mark.asyncio
async def test_criar_linha_com_empresa(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, nome="Linha 100", id_empresa=id_emp)
        assert linha.situacao == "ativa"
        assert linha.id_empresa == id_emp
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_nome_de_linha_e_unico_por_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        await _linha(admin_engine, t.id, nome="Linha Circular", id_empresa=id_emp)
        with pytest.raises(HTTPException) as e:
            # Caixa diferente: o índice/checagem é sobre `lower(nome)`.
            await _linha(admin_engine, t.id, nome="linha circular", id_empresa=id_emp)
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_linha_sem_operador_e_recusada_no_schema():
    with pytest.raises(ValidationError):
        LinhaCreate(
            nome="Linha X",
            origem="A",
            destino="B",
            tipo_servico="transporte_distrital",
            id_empresa=None,
            id_permissionario=None,
        )


@pytest.mark.asyncio
async def test_operador_de_outro_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        id_emp_b, _ = await _operadores(admin_engine, b.id)
        with pytest.raises(HTTPException) as e:
            await _linha(admin_engine, a.id, id_empresa=id_emp_b)
        # 404, não 403: 403 confirmaria que a empresa existe noutro tenant.
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_operador_excluido_e_recusado(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text("UPDATE transporte_regulado.empresa SET excluido = true WHERE id = :id"),
                {"id": id_emp},
            )
        with pytest.raises(HTTPException) as e:
            await _linha(admin_engine, t.id, id_empresa=id_emp)
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_linha_de_outro_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, a.id)
        linha = await _linha(admin_engine, a.id, id_empresa=id_emp)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.obter_linha(db, tenant_id=b.id, linha_id=linha.id)
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_excluir_linha_nao_cascateia_filhas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_parada "
                    "(tenant_id, id_linha, ordem, descricao, criado_em) "
                    "VALUES (:t, :l, 1, 'Parada 1', NOW())"
                ),
                {"t": t.id, "l": linha.id},
            )
            await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_horario "
                    "(tenant_id, id_linha, dia_semana, partida, criado_em) "
                    "VALUES (:t, :l, 1, '08:00', NOW())"
                ),
                {"t": t.id, "l": linha.id},
            )

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.excluir_linha(db, tenant_id=t.id, linha_id=linha.id)

        async with admin_engine.begin() as conn:
            parada = (
                await conn.execute(
                    text(
                        "SELECT excluido FROM transporte_regulado.linha_parada "
                        "WHERE id_linha = :l"
                    ),
                    {"l": linha.id},
                )
            ).scalar_one()
            horario_existe = (
                await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM transporte_regulado.linha_horario "
                        "WHERE id_linha = :l"
                    ),
                    {"l": linha.id},
                )
            ).scalar_one()
        assert parada is False, "excluir a linha não deve marcar as paradas como excluídas"
        assert horario_existe == 1, "excluir a linha não deve remover os horários"
    finally:
        await _limpar(admin_engine, t.id)

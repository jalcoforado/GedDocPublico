"""Transporte P7 — ocorrências (catálogo de tipos + registro).

Spec: `docs/superpowers/specs/2026-08-21-transporte-p7-ocorrencias-design.md`.

Fixtures/estilo seguem `test_transporte_p6b_linhas.py`: `admin_engine`,
`_provisionar`/`_operadores` (adaptado), limpeza no teardown.
"""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.main import app
from app.schemas.transporte_regulado import (
    OcorrenciaCreate,
    OcorrenciaTipoCreate,
    OcorrenciaTipoUpdate,
)
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


async def _tipo(engine, tenant_id: int, *, nome=None, ativo=True):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.criar_tipo_ocorrencia(
                db,
                tenant_id=tenant_id,
                payload=OcorrenciaTipoCreate(
                    nome=nome or f"Tipo {uuid.uuid4().hex[:6]}", ativo=ativo,
                ),
            )


async def _limpar(engine, tenant_id: int) -> None:
    app.dependency_overrides.clear()
    from app.database import engine as app_engine

    await app_engine.dispose()
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM transporte_regulado.ocorrencia_andamento WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia_tipo WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.empresa WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.permissionario WHERE tenant_id=:t",
        ):
            await s.execute(text(stmt), {"t": tenant_id})
        await s.commit()


@pytest.mark.asyncio
async def test_nome_de_tipo_e_unico_por_tenant(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        await _tipo(admin_engine, t.id, nome="Recusa de corrida")
        with pytest.raises(HTTPException) as e:
            # Caixa diferente: a checagem é sobre `lower(nome)`.
            await _tipo(admin_engine, t.id, nome="recusa de corrida")
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excluir_tipo_em_uso_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Fato X",
                        id_empresa=id_emp,
                    ),
                    id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.excluir_tipo_ocorrencia(db, tenant_id=t.id, tipo_id=tipo.id)
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_tipo_inativo_permanece_em_ocorrencia_antiga(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id, nome="Veículo sem vistoria")
        id_emp, _ = await _operadores(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                ocorrencia = await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Fato Y",
                        id_empresa=id_emp,
                    ),
                    id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.atualizar_tipo_ocorrencia(
                    db, tenant_id=t.id, tipo_id=tipo.id,
                    payload=OcorrenciaTipoUpdate(ativo=False),
                )

        async with _sm(admin_engine)() as db:
            tipos = await tr.listar_tipos_ocorrencia(db, tenant_id=t.id)
            achado = next(x for x in tipos if x.id == tipo.id)
            assert achado.ativo is False

            recarregada = await tr.obter_ocorrencia(
                db, tenant_id=t.id, ocorrencia_id=ocorrencia.id
            )
            assert recarregada.id_tipo == tipo.id
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_registrar_no_balcao_sem_alvo_da_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Sem alvo nenhum",
                    ),
                    id_usuario=None,
                    exigir_alvo=True,
                )
        assert e.value.status_code == 422
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_registrar_com_alvo_cross_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        tipo_a = await _tipo(admin_engine, a.id)
        id_emp_b, _ = await _operadores(admin_engine, b.id)
        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.registrar_ocorrencia(
                    db, tenant_id=a.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo_a.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Alvo alheio",
                        id_empresa=id_emp_b,
                    ),
                    id_usuario=None,
                )
        # 404, não 403: 403 confirmaria que a empresa existe noutro tenant.
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_registrar_cria_ato_registro_na_trilha(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                ocorrencia = await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Fato Z",
                        id_empresa=id_emp,
                    ),
                    id_usuario=None,
                )
        assert ocorrencia.situacao == "registrada"

        async with admin_engine.begin() as conn:
            andamentos = (
                await conn.execute(
                    text(
                        "SELECT ato FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id"
                    ),
                    {"id": ocorrencia.id},
                )
            ).scalars().all()
        assert andamentos == ["registro"]
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------------------ listar_ocorrencias


@pytest.mark.asyncio
async def test_listar_ocorrencias_filtros_e_contagem(admin_engine):
    """`total` tem de acompanhar `q` e `situacao` — condição acrescentada só na
    consulta ou só na contagem faz a paginação mentir. `total == len(rows)` é o
    invariante que a mutação óbvia (esquecer a condição na contagem) quebraria."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                oc_descricao = await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Recusa de embarque na praça",
                        id_empresa=id_emp,
                    ),
                    id_usuario=None,
                )
            async with db.begin():
                oc_referencia = await tr.registrar_ocorrencia(
                    db, tenant_id=t.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo.id, origem="denuncia",
                        data_fato=date.today(), descricao="Outro fato qualquer",
                        referencia_alvo="placa ABC1D23", id_empresa=id_emp,
                    ),
                    id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            # Casa por DESCRIÇÃO.
            rows, total = await tr.listar_ocorrencias(db, tenant_id=t.id, q="embarque")
            assert total == len(rows) == 1
            assert [r.id for r in rows] == [oc_descricao.id]

            # Casa por REFERÊNCIA DE ALVO.
            rows, total = await tr.listar_ocorrencias(db, tenant_id=t.id, q="ABC1D23")
            assert total == len(rows) == 1
            assert [r.id for r in rows] == [oc_referencia.id]

            # Filtro de situação: as duas nascem `registrada`.
            rows, total = await tr.listar_ocorrencias(db, tenant_id=t.id, situacao="registrada")
            assert total == len(rows) == 2

            rows, total = await tr.listar_ocorrencias(db, tenant_id=t.id, situacao="em_apuracao")
            assert total == len(rows) == 0

            # Sem filtro nenhum, as duas voltam e total bate com a lista.
            rows, total = await tr.listar_ocorrencias(db, tenant_id=t.id)
            assert total == len(rows) == 2
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_ocorrencia_de_outro_tenant_da_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        tipo_a = await _tipo(admin_engine, a.id)
        id_emp_a, _ = await _operadores(admin_engine, a.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                ocorrencia = await tr.registrar_ocorrencia(
                    db, tenant_id=a.id,
                    payload=OcorrenciaCreate(
                        id_tipo=tipo_a.id, origem="fiscalizacao",
                        data_fato=date.today(), descricao="Fato do tenant A",
                        id_empresa=id_emp_a,
                    ),
                    id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.obter_ocorrencia(db, tenant_id=b.id, ocorrencia_id=ocorrencia.id)
        assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)

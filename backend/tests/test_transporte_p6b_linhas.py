"""Transporte P6b — linhas (cadastro CRUD).

Spec: `docs/superpowers/specs/2026-08-21-transporte-p6b-linhas`.

Fixtures/estilo seguem `test_transporte_p6_pontos.py`: `admin_engine`,
`_provisionar` (de `test_transporte_p5_2_atendimento`), limpeza no teardown.
"""
from __future__ import annotations

import uuid
from datetime import datetime, time

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.main import app
from app.models import LinhaHorario, LinhaParada
from app.schemas.transporte_regulado import (
    AlvaraCreate,
    LinhaCreate,
    LinhaHorarioCreate,
    LinhaParadaCreate,
    LinhaParadaUpdate,
    LinhaUpdate,
)
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _cria_usuario_comum_transporte,
    _provisionar,
    _sm,
)


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


async def _linha(
    engine, tenant_id: int, *, nome=None, codigo=None, situacao="ativa",
    id_empresa=None, id_permissionario=None,
):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.criar_linha(
                db,
                tenant_id=tenant_id,
                payload=LinhaCreate(
                    nome=nome or f"Linha {uuid.uuid4().hex[:6]}",
                    codigo=codigo,
                    origem="Centro",
                    destino="Bairro Novo",
                    tipo_servico="transporte_distrital",
                    situacao=situacao,
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
            # `test_alvara_continua_emitindo_para_operador_de_linha` emite um
            # alvará ligado ao permissionário: sem apagá-lo antes, o DELETE do
            # permissionário abaixo esbarra na FK `alvara_id_permissionario_fkey`.
            "DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t",
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


# ------------------------------------------------------------ listar_linhas


@pytest.mark.asyncio
async def test_listar_linhas_filtra_por_q_e_situacao(admin_engine):
    """`total` tem de acompanhar `q` e `situacao` — a classe de bug já ocorreu
    duas vezes neste módulo (permissionário, alvará): condição acrescentada só
    na consulta ou só na contagem faz a paginação mentir. Aqui as duas ficam
    lado a lado: `total == len(rows)` é o invariante que a mutação óbvia
    (esquecer a condição na contagem) quebraria — a contagem voltaria 3 com
    a lista mostrando 1.
    """
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        l_nome = await _linha(
            admin_engine, t.id, nome="Expresso Sul", codigo="A100", id_empresa=id_emp
        )
        l_codigo = await _linha(
            admin_engine, t.id, nome="Perimetral", codigo="B200", id_empresa=id_emp
        )
        l_inativa = await _linha(
            admin_engine, t.id, nome="Circular Centro", codigo="C300",
            situacao="inativa", id_empresa=id_emp,
        )

        async with _sm(admin_engine)() as db:
            # Casa por NOME.
            rows, total = await tr.listar_linhas(db, tenant_id=t.id, q="Expresso")
            assert total == len(rows) == 1, "total deve acompanhar o filtro por nome"
            assert [r.id for r in rows] == [l_nome.id]

            # Casa por CÓDIGO.
            rows, total = await tr.listar_linhas(db, tenant_id=t.id, q="B200")
            assert total == len(rows) == 1, "total deve acompanhar o filtro por código"
            assert [r.id for r in rows] == [l_codigo.id]

            # Filtro de situação: só a inativa volta.
            rows, total = await tr.listar_linhas(db, tenant_id=t.id, situacao="inativa")
            assert total == len(rows) == 1
            assert [r.id for r in rows] == [l_inativa.id]

            # Sem filtro nenhum, as três voltam e total bate com a lista.
            rows, total = await tr.listar_linhas(db, tenant_id=t.id)
            assert total == len(rows) == 3
    finally:
        await _limpar(admin_engine, t.id)


# ---------------------------------------------------------- atualizar_linha


@pytest.mark.asyncio
async def test_atualizar_linha_troca_nome_e_situacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, nome="Linha Antiga", id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                atualizada = await tr.atualizar_linha(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaUpdate(nome="Linha Nova", situacao="inativa"),
                )
        assert atualizada.nome == "Linha Nova"
        assert atualizada.situacao == "inativa"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_atualizar_linha_sem_operador_no_estado_final_da_422(admin_engine):
    """Linha só com empresa: remover a empresa sem indicar permissionário
    deixaria o estado final sem operador nenhum — o CHECK do banco é a rede,
    mas a borda tem de recusar antes com mensagem útil."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.atualizar_linha(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaUpdate(id_empresa=None),
                )
        assert e.value.status_code == 422
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_renomear_linha_para_nome_existente_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        await _linha(admin_engine, t.id, nome="Linha Um", id_empresa=id_emp)
        outra = await _linha(admin_engine, t.id, nome="Linha Dois", id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.atualizar_linha(
                    db, tenant_id=t.id, linha_id=outra.id,
                    payload=LinhaUpdate(nome="Linha Um"),
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------------ P6b: paradas e horários


@pytest.mark.asyncio
async def test_parada_nova_entra_no_fim(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                p1 = await tr.criar_parada(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaParadaCreate(descricao="Parada A"),
                )
            async with db.begin():
                p2 = await tr.criar_parada(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaParadaCreate(descricao="Parada B"),
                )
        assert p1.ordem == 1
        assert p2.ordem == 2
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_atualizar_parada_troca_descricao_sem_mexer_na_ordem(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                parada = await tr.criar_parada(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaParadaCreate(descricao="Parada Original"),
                )
            ordem_antes = parada.ordem
            async with db.begin():
                atualizada = await tr.atualizar_parada(
                    db, tenant_id=t.id, linha_id=linha.id, parada_id=parada.id,
                    payload=LinhaParadaUpdate(descricao="Parada Renomeada"),
                )
        assert atualizada.descricao == "Parada Renomeada"
        assert atualizada.ordem == ordem_antes
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excluir_parada_do_meio_mantem_ordem_das_restantes(admin_engine):
    """Exclusão é soft e NÃO renumera — a ordem só muda no `reordenar_paradas`
    explícito. A listagem simplesmente pula a excluída."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            paradas = []
            for nome in ("A", "B", "C"):
                async with db.begin():
                    paradas.append(
                        await tr.criar_parada(
                            db, tenant_id=t.id, linha_id=linha.id,
                            payload=LinhaParadaCreate(descricao=f"Parada {nome}"),
                        )
                    )
            do_meio = paradas[1]
            async with db.begin():
                await tr.excluir_parada(
                    db, tenant_id=t.id, linha_id=linha.id, parada_id=do_meio.id,
                )
            restantes = await tr.listar_paradas(db, tenant_id=t.id, linha_id=linha.id)

        assert [p.id for p in restantes] == [paradas[0].id, paradas[2].id]
        assert [p.ordem for p in restantes] == [1, 3]

        async with admin_engine.begin() as conn:
            excluido = (
                await conn.execute(
                    text(
                        "SELECT excluido FROM transporte_regulado.linha_parada "
                        "WHERE id = :id"
                    ),
                    {"id": do_meio.id},
                )
            ).scalar_one()
        assert excluido is True
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_parada_e_horario_cross_tenant_e_inexistente_dao_404(admin_engine):
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        id_emp_a, _ = await _operadores(admin_engine, a.id)
        linha = await _linha(admin_engine, a.id, id_empresa=id_emp_a)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                parada = await tr.criar_parada(
                    db, tenant_id=a.id, linha_id=linha.id,
                    payload=LinhaParadaCreate(descricao="Parada Única"),
                )
            async with db.begin():
                horario = await tr.criar_horario(
                    db, tenant_id=a.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=4, partida=time(6, 0)),
                )

            # Caller do tenant B (cross-tenant): 404, não 403.
            with pytest.raises(HTTPException) as e:
                await tr.atualizar_parada(
                    db, tenant_id=b.id, linha_id=linha.id, parada_id=parada.id,
                    payload=LinhaParadaUpdate(descricao="Invasão"),
                )
            assert e.value.status_code == 404

            with pytest.raises(HTTPException) as e:
                await tr.excluir_parada(
                    db, tenant_id=b.id, linha_id=linha.id, parada_id=parada.id,
                )
            assert e.value.status_code == 404

            with pytest.raises(HTTPException) as e:
                await tr.excluir_horario(
                    db, tenant_id=b.id, linha_id=linha.id, horario_id=horario.id,
                )
            assert e.value.status_code == 404

            # Tenant certo, id inventado (alto e improvável de existir): 404.
            with pytest.raises(HTTPException) as e:
                await tr.atualizar_parada(
                    db, tenant_id=a.id, linha_id=linha.id, parada_id=999999999,
                    payload=LinhaParadaUpdate(descricao="Fantasma"),
                )
            assert e.value.status_code == 404

            with pytest.raises(HTTPException) as e:
                await tr.excluir_parada(
                    db, tenant_id=a.id, linha_id=linha.id, parada_id=999999999,
                )
            assert e.value.status_code == 404

            with pytest.raises(HTTPException) as e:
                await tr.excluir_horario(
                    db, tenant_id=a.id, linha_id=linha.id, horario_id=999999999,
                )
            assert e.value.status_code == 404
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_reordenar_renumera_1_a_n(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            paradas = {}
            for nome in ("A", "B", "C"):
                async with db.begin():
                    paradas[nome] = await tr.criar_parada(
                        db, tenant_id=t.id, linha_id=linha.id,
                        payload=LinhaParadaCreate(descricao=f"Parada {nome}"),
                    )

            nova_ordem = [paradas["C"].id, paradas["A"].id, paradas["B"].id]
            async with db.begin():
                resultado = await tr.reordenar_paradas(
                    db, tenant_id=t.id, linha_id=linha.id, ids=nova_ordem
                )

        assert [p.id for p in resultado] == nova_ordem
        assert [p.ordem for p in resultado] == [1, 2, 3]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_reordenar_com_id_faltando_ou_sobrando_da_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            paradas = []
            for nome in ("A", "B", "C"):
                async with db.begin():
                    paradas.append(
                        await tr.criar_parada(
                            db, tenant_id=t.id, linha_id=linha.id,
                            payload=LinhaParadaCreate(descricao=f"Parada {nome}"),
                        )
                    )

            # (a) lista parcial: falta um id.
            with pytest.raises(HTTPException) as e:
                await tr.reordenar_paradas(
                    db, tenant_id=t.id, linha_id=linha.id,
                    ids=[paradas[0].id, paradas[1].id],
                )
            assert e.value.status_code == 422

            # (b) lista com id alheio (que não pertence à linha).
            with pytest.raises(HTTPException) as e:
                await tr.reordenar_paradas(
                    db, tenant_id=t.id, linha_id=linha.id,
                    ids=[paradas[0].id, paradas[1].id, paradas[2].id, 999999],
                )
            assert e.value.status_code == 422
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_leitura_ordena_por_ordem_e_id_com_duplicata_plantada(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            paradas = []
            for nome in ("A", "B", "C"):
                async with db.begin():
                    paradas.append(
                        await tr.criar_parada(
                            db, tenant_id=t.id, linha_id=linha.id,
                            payload=LinhaParadaCreate(descricao=f"Parada {nome}"),
                        )
                    )

        # Planta duplicata de `ordem` direto no banco — contornando o serviço,
        # que nunca produziria isso sozinho (é exatamente por isso que o
        # desempate por `id` existe).
        async with admin_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE transporte_regulado.linha_parada SET ordem = 1 "
                    "WHERE id = :id"
                ),
                {"id": paradas[2].id},
            )

        async with _sm(admin_engine)() as db:
            lidas = await tr.listar_paradas(db, tenant_id=t.id, linha_id=linha.id)

        # Duas com ordem=1 (A e C), desempatadas por id; B com ordem=2 por último.
        assert [p.id for p in lidas] == [
            paradas[0].id, paradas[2].id, paradas[1].id,
        ]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_horario_duplicado_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.criar_horario(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=1, partida=time(8, 0)),
                )
            with pytest.raises(HTTPException) as e:
                await tr.criar_horario(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=1, partida=time(8, 0)),
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_horario_apagado_libera_o_par(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                horario = await tr.criar_horario(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=2, partida=time(7, 30)),
                )
            async with db.begin():
                await tr.excluir_horario(
                    db, tenant_id=t.id, linha_id=linha.id, horario_id=horario.id,
                )
            # O mesmo par (dia_semana, partida) volta a passar.
            async with db.begin():
                novo = await tr.criar_horario(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=2, partida=time(7, 30)),
                )
        assert novo.id != horario.id
    finally:
        await _limpar(admin_engine, t.id)


# ------------------------------------------------------------- a prova estrutural


@pytest.mark.asyncio
async def test_o_banco_barra_horario_duplicado_sem_passar_pelo_servico(admin_engine):
    """A exclusividade do par (linha, dia_semana, partida) é do índice único
    parcial, não do `SELECT` de checagem em `criar_horario`. Insere o segundo
    horário direto pelo banco, contornando o serviço inteiro, e espera
    `IntegrityError` — sem isso, remover o índice deixaria a bateria toda
    verde enquanto duas requisições concorrentes duplicariam o horário em
    produção."""
    t = await _provisionar(admin_engine)
    try:
        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.criar_horario(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaHorarioCreate(dia_semana=3, partida=time(9, 0)),
                )

        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as db:
                async with db.begin():
                    db.add(
                        LinhaHorario(
                            tenant_id=t.id, id_linha=linha.id,
                            dia_semana=3, partida=time(9, 0),
                            criado_em=datetime.utcnow(),
                        )
                    )
    finally:
        await _limpar(admin_engine, t.id)


# ----------------------------------------------------------------- HTTP


@pytest.mark.asyncio
async def test_http_usuario_comum_cria_linha_e_le_detalhe(admin_engine):
    """Usuário COMUM, não super-usuário.

    O bypass de SU em `auth/perms.py` retorna antes do `getattr(item, action)`,
    e foi assim que dez rotas do transporte ficaram devolvendo 500 para
    operador não-SU sem a suíte notar. Toda rota nova precisa de um teste que
    passe por este caminho.
    """
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                # `contratar` RECONCILIA: passar só `["transporte"]`
                # descontrata os demais.
                await contratar(s, t.id, ["transporte"])

        id_emp, _ = await _operadores(admin_engine, t.id)
        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/linhas"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                base,
                json={
                    "nome": "Linha HTTP",
                    "origem": "Centro",
                    "destino": "Bairro Novo",
                    "tipo_servico": "transporte_distrital",
                    "id_empresa": id_emp,
                },
            )
            assert r.status_code == 201, r.text
            linha_id = r.json()["id"]

            r = await c.get(f"{base}/{linha_id}")
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert corpo["paradas"] == []
            assert corpo["horarios"] == []
            assert corpo["operador_nome"]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_reordenar_paradas(admin_engine):
    """Prova de passagem que a rota literal `/ordem` não foi engolida pela
    paramétrica `/{parada_id}` — senão o PUT abaixo devolveria 422 sem chegar
    ao handler."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                await contratar(s, t.id, ["transporte"])

        id_emp, _ = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_empresa=id_emp)
        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = f"/api/v2/transporte-regulado/linhas/{linha.id}"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r1 = await c.post(f"{base}/paradas", json={"descricao": "Parada A"})
            assert r1.status_code == 201, r1.text
            r2 = await c.post(f"{base}/paradas", json={"descricao": "Parada B"})
            assert r2.status_code == 201, r2.text
            id_a, id_b = r1.json()["id"], r2.json()["id"]

            r = await c.put(f"{base}/paradas/ordem", json={"ids": [id_b, id_a]})
            assert r.status_code == 200, r.text

            r = await c.get(base)
            assert r.status_code == 200, r.text
            paradas = r.json()["paradas"]
            assert [p["id"] for p in paradas] == [id_b, id_a]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_rls_filtra_as_tres_tabelas_sob_aprimora_app(admin_engine, app_session):
    """Isolamento cross-tenant nas três tabelas SOB `app_session` (papel
    `aprimora_app`, NOBYPASSRLS) — os demais testes cross-tenant deste arquivo
    rodam com `admin_engine` (`ged_user`, BYPASSRLS) e provam a camada de
    serviço, não a policy do Postgres. Este é o único que prova a policy.

    Por inversão: se a policy de `linha`/`linha_parada`/`linha_horario` fosse
    tautológica (`USING (true)`, equivalente a esquecer o `WHERE` de RLS), o
    SELECT sob tenant A devolveria as linhas de A **e** de B, e a asserção
    `id_linha_b not in ids` falharia. É essa asserção — ausência do id do
    outro tenant, não uma contagem — que fecha o buraco.
    """
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        id_emp_a, _ = await _operadores(admin_engine, a.id)
        id_emp_b, _ = await _operadores(admin_engine, b.id)
        linha_a = await _linha(admin_engine, a.id, nome="Linha RLS A", id_empresa=id_emp_a)
        linha_b = await _linha(admin_engine, b.id, nome="Linha RLS B", id_empresa=id_emp_b)

        async with admin_engine.begin() as conn:
            r = await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_parada "
                    "(tenant_id, id_linha, ordem, descricao, criado_em) "
                    "VALUES (:t, :l, 1, 'Parada RLS', NOW()) RETURNING id"
                ),
                {"t": a.id, "l": linha_a.id},
            )
            parada_a_id = r.scalar_one()
            r = await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_parada "
                    "(tenant_id, id_linha, ordem, descricao, criado_em) "
                    "VALUES (:t, :l, 1, 'Parada RLS', NOW()) RETURNING id"
                ),
                {"t": b.id, "l": linha_b.id},
            )
            parada_b_id = r.scalar_one()
            r = await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_horario "
                    "(tenant_id, id_linha, dia_semana, partida, criado_em) "
                    "VALUES (:t, :l, 1, '08:00', NOW()) RETURNING id"
                ),
                {"t": a.id, "l": linha_a.id},
            )
            horario_a_id = r.scalar_one()
            r = await conn.execute(
                text(
                    "INSERT INTO transporte_regulado.linha_horario "
                    "(tenant_id, id_linha, dia_semana, partida, criado_em) "
                    "VALUES (:t, :l, 1, '08:00', NOW()) RETURNING id"
                ),
                {"t": b.id, "l": linha_b.id},
            )
            horario_b_id = r.scalar_one()

        async def _ids_vistos(tenant_id: int, tabela: str) -> set[int]:
            await app_session.execute(
                text(f"SET LOCAL app.tenant_id = '{tenant_id}'")
            )
            rows = (
                await app_session.execute(text(f"SELECT id FROM {tabela}"))
            ).scalars().all()
            return set(rows)

        # Sob o tenant A: só ids de A aparecem, nunca os de B.
        ids_linha = await _ids_vistos(a.id, "transporte_regulado.linha")
        assert linha_a.id in ids_linha
        assert linha_b.id not in ids_linha
        await app_session.rollback()

        ids_parada = await _ids_vistos(a.id, "transporte_regulado.linha_parada")
        assert parada_a_id in ids_parada
        assert parada_b_id not in ids_parada
        await app_session.rollback()

        ids_horario = await _ids_vistos(a.id, "transporte_regulado.linha_horario")
        assert horario_a_id in ids_horario
        assert horario_b_id not in ids_horario
        await app_session.rollback()

        # Sob o tenant B: o simétrico — só ids de B, nunca os de A.
        ids_linha = await _ids_vistos(b.id, "transporte_regulado.linha")
        assert linha_b.id in ids_linha
        assert linha_a.id not in ids_linha
        await app_session.rollback()

        ids_parada = await _ids_vistos(b.id, "transporte_regulado.linha_parada")
        assert parada_b_id in ids_parada
        assert parada_a_id not in ids_parada
        await app_session.rollback()

        ids_horario = await _ids_vistos(b.id, "transporte_regulado.linha_horario")
        assert horario_b_id in ids_horario
        assert horario_a_id not in ids_horario
        await app_session.rollback()
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_alvara_continua_emitindo_para_operador_de_linha(admin_engine):
    """O teste do NÃO-gate: linha existir/inativar não trava o alvará do
    permissionário que a opera — mesma decisão da P6 com o ponto/vaga."""
    t = await _provisionar(admin_engine)
    try:
        _, id_perm = await _operadores(admin_engine, t.id)
        linha = await _linha(admin_engine, t.id, id_permissionario=id_perm)

        async with _sm(admin_engine)() as db:
            alvara = await tr.criar_alvara(
                db,
                tenant_id=t.id,
                payload=AlvaraCreate(
                    numero_alvara=f"ALV-{uuid.uuid4().hex[:8]}",
                    tipo_servico="transporte_escolar",
                    id_permissionario=id_perm,
                ),
            )
        assert alvara.id is not None

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.atualizar_linha(
                    db, tenant_id=t.id, linha_id=linha.id,
                    payload=LinhaUpdate(situacao="inativa"),
                )

        async with _sm(admin_engine)() as db:
            perm_depois = await tr.obter_permissionario(
                db, tenant_id=t.id, permissionario_id=id_perm
            )
        assert perm_depois.situacao == "ativo", (
            "inativar a linha não pode mudar a situação do permissionário"
        )
    finally:
        await _limpar(admin_engine, t.id)

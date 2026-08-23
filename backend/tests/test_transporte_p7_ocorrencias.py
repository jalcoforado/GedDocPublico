"""Transporte P7 — ocorrências (catálogo de tipos + registro).

Spec: `docs/superpowers/specs/2026-08-21-transporte-p7-ocorrencias-design.md`.

Fixtures/estilo seguem `test_transporte_p6b_linhas.py`: `admin_engine`,
`_provisionar`/`_operadores` (adaptado), limpeza no teardown.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.auth.jwt import build_cidadao_payload, encode_token, get_jwt_secret
from app.main import app
from app.models import OcorrenciaTipo, UsuarioExterno
from app.schemas.transporte_regulado import (
    AlvaraCreate,
    DenunciaCidadaoCreate,
    OcorrenciaCreate,
    OcorrenciaOut,
    OcorrenciaTipoCreate,
    OcorrenciaTipoUpdate,
)
from app.services import transporte_regulado as tr
from app.services.modulos import contratar
from tests.conftest import arreio_tenant_http
from tests.test_transporte_p5_2_atendimento import (
    _as_user,
    _cria_usuario_comum_transporte,
    _provisionar,
    _sm,
)


async def _cidadao(engine, tenant_id: int, *, email: str | None = "cidadao@ex.com") -> int:
    """Cidadão mínimo para os testes de denúncia (P7.2)."""
    async with _sm(engine)() as s:
        c = UsuarioExterno(
            tenant_id=tenant_id, nome="Cidadão de Teste",
            cpf_cnpj=uuid.uuid4().hex[:11], email=email,
            ativo=True, excluido=False, uid=uuid.uuid4(),
            data_criacao=datetime.now(),
            login_govbr=False, telefone_whatsapp=False,
        )
        s.add(c)
        await s.commit()
        return c.id


async def _get_cidadao(engine, cid: int) -> UsuarioExterno:
    async with _sm(engine)() as s:
        return (
            await s.execute(select(UsuarioExterno).where(UsuarioExterno.id == cid))
        ).scalar_one()


async def _token_cidadao(engine, cid: int, tenant_id: int) -> str:
    async with _sm(engine)() as s:
        secret = await get_jwt_secret(s)
    cidadao = await _get_cidadao(engine, cid)
    payload = build_cidadao_payload(
        cidadao.id, cidadao.cpf_cnpj or "", tenant_id=tenant_id
    )
    return encode_token(payload, secret)


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
            "DELETE FROM aprimora_py.notificacao WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia_andamento WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia WHERE tenant_id=:t",
            "DELETE FROM transporte_regulado.ocorrencia_tipo WHERE tenant_id=:t",
            "DELETE FROM utils.usuario_externo WHERE tenant_id=:t",
            # `test_alvara_continua_emitindo_com_ocorrencia_procedente` emite um
            # alvará ligado ao permissionário: sem apagá-lo antes, o DELETE do
            # permissionário abaixo esbarra na FK `alvara_id_permissionario_fkey`.
            "DELETE FROM transporte_regulado.alvara WHERE tenant_id=:t",
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
async def test_o_banco_barra_tipo_duplicado_sem_passar_pelo_servico(admin_engine):
    """A exclusividade de `nome` (case-insensitive) por tenant é do índice
    único parcial `ux_ocorrencia_tipo_nome`, não do `SELECT` de checagem em
    `criar_tipo_ocorrencia`. Insere o segundo tipo direto pelo banco,
    contornando o serviço inteiro, e espera `IntegrityError` — sem isso,
    remover o índice deixaria a bateria toda verde enquanto duas requisições
    concorrentes duplicariam o tipo em produção."""
    t = await _provisionar(admin_engine)
    try:
        await _tipo(admin_engine, t.id, nome="Recusa de corrida")

        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as db:
                async with db.begin():
                    db.add(
                        OcorrenciaTipo(
                            tenant_id=t.id, nome="RECUSA DE CORRIDA",
                            ativo=True, criado_em=datetime.utcnow(),
                        )
                    )
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


# ------------------------------------------------------------ máquina de estados


async def _registrar(engine, tenant_id: int, tipo, *, id_empresa=None, exigir_alvo=True):
    async with _sm(engine)() as db:
        async with db.begin():
            return await tr.registrar_ocorrencia(
                db, tenant_id=tenant_id,
                payload=OcorrenciaCreate(
                    id_tipo=tipo.id, origem="fiscalizacao" if id_empresa else "denuncia",
                    data_fato=date.today(), descricao="Fato para máquina de estados",
                    id_empresa=id_empresa,
                ),
                id_usuario=None,
                exigir_alvo=exigir_alvo,
            )


@pytest.mark.asyncio
async def test_maquina_de_estados_caminho_feliz(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                em_apuracao = await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )
        assert em_apuracao.situacao == "em_apuracao"

        async with _sm(admin_engine)() as db:
            async with db.begin():
                decidida = await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="improcedente", parecer="Sem elementos", id_usuario=None,
                )
        assert decidida.situacao == "improcedente"

        async with admin_engine.begin() as conn:
            atos = (
                await conn.execute(
                    text(
                        "SELECT ato FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id ORDER BY criado_em, id"
                    ),
                    {"id": ocorrencia.id},
                )
            ).scalars().all()
        assert atos == ["registro", "inicio_apuracao", "decisao"]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_decidir_direto_de_registrada_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="improcedente", parecer="Direto", id_usuario=None,
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_decidir_duas_vezes_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="arquivada", parecer="Primeira decisão", id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="arquivada", parecer="Segunda decisão", id_usuario=None,
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_anotar_em_situacao_final_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="arquivada", parecer="Arquivo", id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.anotar_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    parecer="Anotação tardia", id_usuario=None,
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_decidir_sem_parecer_da_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="improcedente", parecer="   ", id_usuario=None,
                )
        assert e.value.status_code == 422
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_procedente_sem_alvo_da_409(admin_engine):
    """Denúncia (`exigir_alvo=False`) apurada; decidir procedente sem alvo dá
    409; vincular o alvo e decidir de novo passa — prova o ciclo
    denúncia → vincular → decidir."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, id_perm = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, exigir_alvo=False)
        assert ocorrencia.id_permissionario is None
        assert ocorrencia.id_empresa is None

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="procedente", parecer="Confirmado", id_usuario=None,
                )
        assert e.value.status_code == 409

        async with _sm(admin_engine)() as db:
            async with db.begin():
                vinculada = await tr.vincular_alvo_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    id_permissionario=id_perm, id_usuario=None,
                )
        assert vinculada.id_permissionario == id_perm

        async with _sm(admin_engine)() as db:
            async with db.begin():
                decidida = await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="procedente", parecer="Confirmado após vínculo",
                    id_usuario=None,
                )
        assert decidida.situacao == "procedente"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_vincular_alvo_grava_na_ocorrencia_e_na_trilha(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, id_perm = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                vinculada = await tr.vincular_alvo_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    id_permissionario=id_perm, id_usuario=None,
                )
        # Passar None para empresa não apaga o vínculo que já existia.
        assert vinculada.id_permissionario == id_perm
        assert vinculada.id_empresa == id_emp

        async with admin_engine.begin() as conn:
            atos = (
                await conn.execute(
                    text(
                        "SELECT ato FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id ORDER BY criado_em, id"
                    ),
                    {"id": ocorrencia.id},
                )
            ).scalars().all()
        assert atos == ["registro", "vinculo_alvo"]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_excluir_fora_de_registrada_da_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.excluir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                )
        assert e.value.status_code == 409
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_alvara_continua_emitindo_com_ocorrencia_procedente(admin_engine):
    """NÃO-GATE: ocorrência procedente contra um permissionário não trava a
    emissão de alvará dele — mesma decisão do molde em test_transporte_p6b_linhas.py."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, id_perm = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(
            admin_engine, t.id, tipo, exigir_alvo=False,
        )

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.vincular_alvo_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    id_permissionario=id_perm, id_usuario=None,
                )
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.decidir_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    resultado="procedente", parecer="Confirmado", id_usuario=None,
                )

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
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_rls_filtra_as_tres_tabelas_sob_aprimora_app(admin_engine, app_session):
    """Isolamento cross-tenant nas três tabelas de P7 SOB `app_session` (papel
    `aprimora_app`, NOBYPASSRLS) — molde exato de
    `test_rls_filtra_as_tres_tabelas_sob_aprimora_app` em
    `test_transporte_p6b_linhas.py`."""
    a = await _provisionar(admin_engine)
    b = await _provisionar(admin_engine)
    try:
        tipo_a = await _tipo(admin_engine, a.id, nome="Tipo RLS A")
        tipo_b = await _tipo(admin_engine, b.id, nome="Tipo RLS B")
        id_emp_a, _ = await _operadores(admin_engine, a.id)
        id_emp_b, _ = await _operadores(admin_engine, b.id)
        ocorrencia_a = await _registrar(admin_engine, a.id, tipo_a, id_empresa=id_emp_a)
        ocorrencia_b = await _registrar(admin_engine, b.id, tipo_b, id_empresa=id_emp_b)

        async def _ids_vistos(tenant_id: int, tabela: str) -> set[int]:
            await app_session.execute(
                text(f"SET LOCAL app.tenant_id = '{tenant_id}'")
            )
            rows = (
                await app_session.execute(text(f"SELECT id FROM {tabela}"))
            ).scalars().all()
            return set(rows)

        # Sob o tenant A: só ids de A aparecem, nunca os de B.
        ids_tipo = await _ids_vistos(a.id, "transporte_regulado.ocorrencia_tipo")
        assert tipo_a.id in ids_tipo
        assert tipo_b.id not in ids_tipo
        await app_session.rollback()

        ids_ocorrencia = await _ids_vistos(a.id, "transporte_regulado.ocorrencia")
        assert ocorrencia_a.id in ids_ocorrencia
        assert ocorrencia_b.id not in ids_ocorrencia
        await app_session.rollback()

        ids_andamento = await _ids_vistos(a.id, "transporte_regulado.ocorrencia_andamento")
        async with admin_engine.begin() as conn:
            andamento_a_id = (
                await conn.execute(
                    text(
                        "SELECT id FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id"
                    ),
                    {"id": ocorrencia_a.id},
                )
            ).scalar_one()
            andamento_b_id = (
                await conn.execute(
                    text(
                        "SELECT id FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id"
                    ),
                    {"id": ocorrencia_b.id},
                )
            ).scalar_one()
        assert andamento_a_id in ids_andamento
        assert andamento_b_id not in ids_andamento
        await app_session.rollback()

        # Sob o tenant B: o simétrico — só ids de B, nunca os de A.
        ids_tipo = await _ids_vistos(b.id, "transporte_regulado.ocorrencia_tipo")
        assert tipo_b.id in ids_tipo
        assert tipo_a.id not in ids_tipo
        await app_session.rollback()

        ids_ocorrencia = await _ids_vistos(b.id, "transporte_regulado.ocorrencia")
        assert ocorrencia_b.id in ids_ocorrencia
        assert ocorrencia_a.id not in ids_ocorrencia
        await app_session.rollback()

        ids_andamento = await _ids_vistos(b.id, "transporte_regulado.ocorrencia_andamento")
        assert andamento_b_id in ids_andamento
        assert andamento_a_id not in ids_andamento
        await app_session.rollback()
    finally:
        await _limpar(admin_engine, a.id)
        await _limpar(admin_engine, b.id)


@pytest.mark.asyncio
async def test_vincular_alvo_sem_nenhum_id_da_422(admin_engine):
    """Os três ids None → 422, e a falha não deixa rastro: nenhum ato
    `vinculo_alvo` entra na trilha."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            with pytest.raises(HTTPException) as e:
                await tr.vincular_alvo_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    id_usuario=None,
                )
        assert e.value.status_code == 422

        async with admin_engine.begin() as conn:
            atos = (
                await conn.execute(
                    text(
                        "SELECT ato FROM transporte_regulado.ocorrencia_andamento "
                        "WHERE id_ocorrencia = :id ORDER BY criado_em, id"
                    ),
                    {"id": ocorrencia.id},
                )
            ).scalars().all()
        assert atos == ["registro"]
        assert "vinculo_alvo" not in atos
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_listar_andamentos_ordena_por_criado_em_e_id(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        id_emp, _ = await _operadores(admin_engine, t.id)
        ocorrencia = await _registrar(admin_engine, t.id, tipo, id_empresa=id_emp)

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id, id_usuario=None,
                )
        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.anotar_ocorrencia(
                    db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
                    parecer="Fiscal esteve no local", id_usuario=None,
                )

        async with _sm(admin_engine)() as db:
            andamentos = await tr.listar_andamentos(
                db, tenant_id=t.id, ocorrencia_id=ocorrencia.id,
            )
        assert [a.ato for a in andamentos] == ["registro", "inicio_apuracao", "anotacao"]

        outro = await _provisionar(admin_engine)
        try:
            async with _sm(admin_engine)() as db:
                with pytest.raises(HTTPException) as e:
                    await tr.listar_andamentos(
                        db, tenant_id=outro.id, ocorrencia_id=ocorrencia.id,
                    )
            assert e.value.status_code == 404
        finally:
            await _limpar(admin_engine, outro.id)
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_usuario_comum_registra_apura_e_decide(admin_engine):
    """Usuário COMUM, não super-usuário.

    O bypass de SU em `auth/perms.py` retorna antes do `getattr(item,
    action)`, e foi assim que dez rotas do transporte ficaram devolvendo 500
    para operador não-SU sem a suíte notar. Toda rota nova precisa de um
    teste que passe por este caminho.
    """
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                # `contratar` RECONCILIA: passar só `["transporte"]`
                # descontrata os demais.
                await contratar(s, t.id, ["transporte"])

        tipo = await _tipo(admin_engine, t.id)
        _, id_perm = await _operadores(admin_engine, t.id)
        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/ocorrencias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                base,
                json={
                    "id_tipo": tipo.id,
                    "origem": "fiscalizacao",
                    "data_fato": "2026-08-01",
                    "descricao": "Recusa de corrida registrada no balcão",
                    "id_permissionario": id_perm,
                },
            )
            assert r.status_code == 201, r.text
            ocorrencia_id = r.json()["id"]

            r = await c.post(f"{base}/{ocorrencia_id}/apurar")
            assert r.status_code == 200, r.text
            assert r.json()["situacao"] == "em_apuracao"

            r = await c.post(
                f"{base}/{ocorrencia_id}/decidir",
                json={"resultado": "improcedente", "parecer": "Sem elementos"},
            )
            assert r.status_code == 200, r.text
            assert r.json()["situacao"] == "improcedente"

            r = await c.get(f"{base}/{ocorrencia_id}")
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert [a["ato"] for a in corpo["andamentos"]] == [
                "registro", "inicio_apuracao", "decisao",
            ]
            assert corpo["situacao"] == "improcedente"
            assert corpo["alvo_resumo"]
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_tipos_nao_engolida_pela_parametrica(admin_engine):
    """Prova de passagem que `/tipos` não foi engolida pela paramétrica
    `/{ocorrencia_id}` — senão devolveria 422 sem chegar ao handler."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                await contratar(s, t.id, ["transporte"])

        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/ocorrencias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get(f"{base}/tipos")
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
    finally:
        await _limpar(admin_engine, t.id)


# ---------------------------------------------------------- P7.2: realm cidadão

@pytest.mark.asyncio
async def test_cidadao_registra_denuncia_sem_alvo(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id, nome="Recusa de corrida")
        cid = await _cidadao(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                cidadao = await db.get(UsuarioExterno, cid)
                denuncia = await tr.registrar_denuncia_cidadao(
                    db, tenant_id=t.id, cidadao=cidadao,
                    payload=DenunciaCidadaoCreate(
                        id_tipo=tipo.id, descricao="Motorista recusou a corrida",
                        referencia_alvo="placa ABC1D23", data_fato=date.today(),
                    ),
                )
        assert denuncia.origem == "denuncia"
        assert denuncia.id_cidadao == cid
        assert denuncia.id_permissionario is None
        assert denuncia.id_empresa is None
        assert denuncia.id_veiculo is None
        assert denuncia.situacao == "registrada"
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_denuncia_com_tipo_inativo_da_422(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id, ativo=False)
        cid = await _cidadao(admin_engine, t.id)
        async with _sm(admin_engine)() as db:
            cidadao = await db.get(UsuarioExterno, cid)
            with pytest.raises(HTTPException) as e:
                await tr.registrar_denuncia_cidadao(
                    db, tenant_id=t.id, cidadao=cidadao,
                    payload=DenunciaCidadaoCreate(
                        id_tipo=tipo.id, descricao="Fato qualquer",
                        data_fato=date.today(),
                    ),
                )
        assert e.value.status_code == 422
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cidadao_so_ve_as_suas(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        cid_a = await _cidadao(admin_engine, t.id, email="a@ex.com")
        cid_b = await _cidadao(admin_engine, t.id, email="b@ex.com")

        async def _registrar_denuncia(cid, descricao):
            async with _sm(admin_engine)() as db:
                async with db.begin():
                    cidadao = await db.get(UsuarioExterno, cid)
                    return await tr.registrar_denuncia_cidadao(
                        db, tenant_id=t.id, cidadao=cidadao,
                        payload=DenunciaCidadaoCreate(
                            id_tipo=tipo.id, descricao=descricao,
                            data_fato=date.today(),
                        ),
                    )

        d_a = await _registrar_denuncia(cid_a, "Denúncia de A")
        d_b = await _registrar_denuncia(cid_b, "Denúncia de B")

        async with _sm(admin_engine)() as db:
            minhas_a = await tr.listar_denuncias_do_cidadao(
                db, tenant_id=t.id, id_cidadao=cid_a
            )
            minhas_b = await tr.listar_denuncias_do_cidadao(
                db, tenant_id=t.id, id_cidadao=cid_b
            )
        ids_a = {d.id for d in minhas_a}
        ids_b = {d.id for d in minhas_b}
        assert ids_a == {d_a.id}
        assert ids_b == {d_b.id}
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_saida_do_cidadao_nao_vaza_campos_internos(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        cid = await _cidadao(admin_engine, t.id)
        token = await _token_cidadao(admin_engine, cid, t.id)
        arreio_tenant_http(t.id, t.slug)
        base = "/api/v2/cidadao/denuncias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                base,
                json={
                    "id_tipo": tipo.id,
                    "descricao": "Excesso de lotação no ponto",
                    "data_fato": "2026-08-01",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 201, r.text

            r = await c.get(base, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.text
            corpo = r.json()
            assert len(corpo) >= 1
            assert set(corpo[0].keys()) == {
                "id", "tipo_nome", "descricao", "referencia_alvo",
                "situacao", "data_fato", "criado_em",
            }
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_decisao_gera_email_neutro_ao_cidadao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                await contratar(s, t.id, ["transporte"])

        tipo = await _tipo(admin_engine, t.id)
        cid = await _cidadao(admin_engine, t.id, email="denunciante@ex.com")
        async with _sm(admin_engine)() as db:
            async with db.begin():
                cidadao = await db.get(UsuarioExterno, cid)
                denuncia = await tr.registrar_denuncia_cidadao(
                    db, tenant_id=t.id, cidadao=cidadao,
                    payload=DenunciaCidadaoCreate(
                        id_tipo=tipo.id, descricao="Veículo sem vistoria",
                        data_fato=date.today(),
                    ),
                )

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=denuncia.id, id_usuario=None,
                )

        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/ocorrencias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                f"{base}/{denuncia.id}/decidir",
                json={"resultado": "improcedente", "parecer": "Sem elementos"},
            )
            assert r.status_code == 200, r.text

        async with admin_engine.begin() as conn:
            notif = (
                await conn.execute(
                    text(
                        "SELECT destinatario_email, canal, mensagem, tipo "
                        "FROM aprimora_py.notificacao WHERE tenant_id = :t"
                    ),
                    {"t": t.id},
                )
            ).mappings().all()
        assert len(notif) == 1
        row = notif[0]
        assert row["destinatario_email"] == "denunciante@ex.com"
        assert row["canal"] == "email"
        assert "improcedente" not in row["mensagem"].lower()
        assert "procedente" not in row["mensagem"].lower()
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_cidadao_sem_email_nao_explode(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            async with s.begin():
                await contratar(s, t.id, ["transporte"])

        tipo = await _tipo(admin_engine, t.id)
        cid = await _cidadao(admin_engine, t.id, email=None)
        async with _sm(admin_engine)() as db:
            async with db.begin():
                cidadao = await db.get(UsuarioExterno, cid)
                denuncia = await tr.registrar_denuncia_cidadao(
                    db, tenant_id=t.id, cidadao=cidadao,
                    payload=DenunciaCidadaoCreate(
                        id_tipo=tipo.id, descricao="Sem e-mail cadastrado",
                        data_fato=date.today(),
                    ),
                )

        async with _sm(admin_engine)() as db:
            async with db.begin():
                await tr.iniciar_apuracao(
                    db, tenant_id=t.id, ocorrencia_id=denuncia.id, id_usuario=None,
                )

        uid = await _cria_usuario_comum_transporte(admin_engine, t.id)
        _as_user(admin_engine, uid, t.id, t.slug)()
        base = "/api/v2/transporte-regulado/ocorrencias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                f"{base}/{denuncia.id}/decidir",
                json={"resultado": "arquivada", "parecer": "Arquivado"},
            )
            assert r.status_code == 200, r.text

        async with admin_engine.begin() as conn:
            total = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM aprimora_py.notificacao "
                        "WHERE tenant_id = :t"
                    ),
                    {"t": t.id},
                )
            ).scalar_one()
        assert total == 0
    finally:
        await _limpar(admin_engine, t.id)


@pytest.mark.asyncio
async def test_http_cidadao_token_real(admin_engine):
    """Token de verdade (build_cidadao_payload + encode_token), não override
    de dependência — prova que o realm cidadão funciona ponta a ponta com
    Authorization: Bearer."""
    t = await _provisionar(admin_engine)
    try:
        tipo = await _tipo(admin_engine, t.id)
        cid = await _cidadao(admin_engine, t.id)
        token = await _token_cidadao(admin_engine, cid, t.id)
        arreio_tenant_http(t.id, t.slug)
        base = "/api/v2/cidadao/denuncias"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post(
                base,
                json={
                    "id_tipo": tipo.id,
                    "descricao": "Motorista trafegando em alta velocidade",
                    "referencia_alvo": "ponto central",
                    "data_fato": "2026-08-05",
                },
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r.status_code == 201, r.text
            assert r.json()["situacao"] == "registrada"

            r = await c.get(base, headers={"Authorization": f"Bearer {token}"})
            assert r.status_code == 200, r.text
            assert len(r.json()) == 1
    finally:
        await _limpar(admin_engine, t.id)


# ---------------------------------- data_fato não pode ser futura (síncrono)


def test_ocorrencia_create_rejeita_data_fato_futura():
    from datetime import timedelta

    from pydantic import ValidationError

    amanha = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError, match="A data do fato não pode ser futura"):
        OcorrenciaCreate(
            id_tipo=1, origem="fiscalizacao", data_fato=amanha, descricao="Fato X",
        )


def test_denuncia_cidadao_create_rejeita_data_fato_futura():
    from datetime import timedelta

    from pydantic import ValidationError

    amanha = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError, match="A data do fato não pode ser futura"):
        DenunciaCidadaoCreate(id_tipo=1, descricao="Fato X", data_fato=amanha)


def test_ocorrencia_out_nao_rejeita_data_fato_futura_ja_gravada():
    """`OcorrenciaOut` herda de `OcorrenciaBase`, não de `OcorrenciaCreate`: o
    validador de "não futura" é regra de ENTRADA. Uma linha já no banco com
    `data_fato` futura (histórica, corrigida por trás, ou só um relógio de
    servidor adiantado) tem de continuar sendo servida em list/detalhe/decidir
    sem 500 — sem essa separação de herança, `model_validate` reprovaria a
    própria leitura."""
    from datetime import timedelta

    amanha = date.today() + timedelta(days=1)
    saida = OcorrenciaOut.model_validate(
        {
            "id": 1, "id_tipo": 1, "origem": "fiscalizacao",
            "data_fato": amanha, "descricao": "Fato X",
            "situacao": "registrada", "criado_em": datetime.utcnow(),
            "andamentos": [],
        }
    )
    assert saida.data_fato == amanha

"""Testes de retenções tributárias (F4, Task 2).

Padrão de dados: `_provisionar`/`_criar_usuario`/`_setup_debito` copiados de
`test_pagamentos_f4_lote.py`. Padrão HTTP: `_usuario_com`/`_get`/`_post`
copiados de `test_pagamentos_f2_ajustes.py`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.deps import get_current_user
from app.config import get_settings
from app.main import app
from app.models import LotePagamento, LotePagamentoParcela, Parcela, Usuario
from app.schemas.pagamentos import (
    ContaCreate, ContratoCreate, DebitoCreate, FonteCreate,
    FornecedorCreate, NaturezaCreate, ParcelaCreate, RetencaoCreate, RetencaoUpdate,
)
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_retencoes as ret
from app.services.provisioning_tenant import provisionar_tenant
from tests.conftest import arreio_tenant_http

APP = get_settings().app_name


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _criar_usuario(engine, tenant_id: int, nome: str) -> int:
    async with _sm(engine)() as s:
        uid = (await s.execute(text(
            "INSERT INTO utils.usuario (tenant_id, nome, email, senha, senha_bcrypt, "
            "cpf, ativo, excluido, app, nivel_acesso_sigilo, must_change_password) "
            "VALUES (:t, :n, :e, '', '', :c, true, false, 'sistemas', 'interno', false) "
            "RETURNING id"
        ), {"t": tenant_id, "n": nome, "e": f"{uuid.uuid4().hex[:10]}@t.local",
            "c": str(uuid.uuid4().int)[:11]})).scalar_one()
        await s.commit()
    return uid


async def _provisionar(engine):
    slug = _slug("pagf4ret")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F4 Retencao", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    solicitante_id = await _criar_usuario(engine, tenant.id, "Solicitante")
    return tenant, solicitante_id


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.retencao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.lote_pagamento_parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.lote_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.posicao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.excecao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.anexo_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_versao WHERE tenant_id=:t",
            "DELETE FROM pagamentos.pedido_ajuste WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
            "DELETE FROM aprimora_py.tenant_modulo WHERE tenant_id=:t",
            "DELETE FROM utils.grupo_transacao WHERE tenant_id=:t",
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


async def _setup_debito(engine, tenant_id: int, usuario_id: int, *, valor_total=Decimal("1000.00")):
    """Cria um débito completo em rascunho, com 1 parcela. Devolve (debito, id_conta_pagadora)."""
    async with _sm(engine)() as s:
        fornecedor = await cad.criar_fornecedor(
            s, tenant_id=tenant_id,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Empresa LTDA"),
        )
        fonte = await cad.criar_fonte(
            s, tenant_id=tenant_id,
            payload=FonteCreate(
                codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria",
                grupos_despesa_permitidos=[],
            ),
        )
        conta = await cad.criar_conta(
            s, tenant_id=tenant_id,
            payload=ContaCreate(
                nome="Conta Teste", banco="001", agencia="1",
                conta=uuid.uuid4().hex[:8], id_fonte_recursos=fonte.id,
                grupo_despesa="CUSTEIO", saldo_inicial="10000.00", ativa=True,
            ),
        )

        from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
        stmt = select(UnidadeTrabalho).where(UnidadeTrabalho.tenant_id == tenant_id).limit(1)
        unidade = (await s.execute(stmt)).scalar()
        if not unidade:
            tipo = (await s.execute(select(TipoUnidadeTrabalho).limit(1))).scalar()
            if not tipo:
                tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
                s.add(tipo)
                await s.flush()
            unidade = UnidadeTrabalho(
                tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id,
                unidade_trabalho="Unidade Teste",
            )
            s.add(unidade)
            await s.flush()

        natureza = await cad.criar_natureza(
            s, tenant_id=tenant_id,
            payload=NaturezaCreate(codigo=f"N{uuid.uuid4().hex[:5]}", descricao="Teste"),
        )
        contrato = await cad.criar_contrato(
            s, tenant_id=tenant_id,
            payload=ContratoCreate(
                numero=f"CT-{uuid.uuid4().hex[:8]}", id_fornecedor=fornecedor.id,
                id_unidade=unidade.id, objeto="Serviços de Teste",
                vigencia_inicio="2026-01-01", vigencia_fim="2026-12-31",
                valor_total=Decimal("5000.00"), categoria="SERVICOS",
            ),
        )

        debito = await svc.criar_debito(
            s, tenant_id=tenant_id, usuario_id=usuario_id,
            payload=DebitoCreate(
                numero_nf="NF123456", id_fornecedor=fornecedor.id,
                id_natureza=natureza.id, id_contrato=contrato.id,
                id_fonte_recursos=fonte.id, id_unidade=unidade.id,
                valor_total=valor_total, descricao="Débito de Teste",
                competencia="2026-01",
                parcelas=[ParcelaCreate(numero=1, valor=valor_total, vencimento="2026-02-01")],
            ),
        )
    return debito, conta.id


@pytest.mark.asyncio
async def test_criar_listar_atualizar_excluir_retencao(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            r = await ret.criar_retencao(
                s, tenant_id=tenant.id, debito_id=debito.id,
                payload=RetencaoCreate(tipo="IRRF", base_calculo=Decimal("1000.00"),
                                       aliquota=Decimal("1.5"), valor=Decimal("15.00")),
            )
        assert r.id is not None
        assert r.valor == Decimal("15.00")

        async with _sm(admin_engine)() as s:
            listadas = await ret.listar_retencoes_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        assert len(listadas) == 1

        async with _sm(admin_engine)() as s:
            atualizada = await ret.atualizar_retencao(
                s, tenant_id=tenant.id, retencao_id=r.id,
                payload=RetencaoUpdate(valor=Decimal("20.00")),
            )
        assert atualizada.valor == Decimal("20.00")

        async with _sm(admin_engine)() as s:
            await ret.excluir_retencao(s, tenant_id=tenant.id, retencao_id=r.id)
        async with _sm(admin_engine)() as s:
            listadas = await ret.listar_retencoes_debito(s, tenant_id=tenant.id, debito_id=debito.id)
        assert listadas == []
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_valor_liquido_soma_retencoes_nao_excluidas(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta_id = await _setup_debito(
            admin_engine, tenant.id, solicitante_id, valor_total=Decimal("1000.00"))

        async with _sm(admin_engine)() as s:
            bruto, liquido, retencoes = await ret.resumo_retencoes(
                s, tenant_id=tenant.id, debito_id=debito.id)
        assert bruto == Decimal("1000.00")
        assert liquido == Decimal("1000.00")
        assert retencoes == []

        async with _sm(admin_engine)() as s:
            r1 = await ret.criar_retencao(
                s, tenant_id=tenant.id, debito_id=debito.id,
                payload=RetencaoCreate(tipo="IRRF", base_calculo=Decimal("1000.00"),
                                       valor=Decimal("15.00")))
        async with _sm(admin_engine)() as s:
            r2 = await ret.criar_retencao(
                s, tenant_id=tenant.id, debito_id=debito.id,
                payload=RetencaoCreate(tipo="ISS", base_calculo=Decimal("1000.00"),
                                       valor=Decimal("50.00")))

        async with _sm(admin_engine)() as s:
            bruto, liquido, retencoes = await ret.resumo_retencoes(
                s, tenant_id=tenant.id, debito_id=debito.id)
        assert bruto == Decimal("1000.00")
        assert liquido == Decimal("935.00")
        assert len(retencoes) == 2

        # excluir uma retenção tira do líquido
        async with _sm(admin_engine)() as s:
            await ret.excluir_retencao(s, tenant_id=tenant.id, retencao_id=r1.id)
        async with _sm(admin_engine)() as s:
            _bruto, liquido, _retencoes = await ret.resumo_retencoes(
                s, tenant_id=tenant.id, debito_id=debito.id)
        assert liquido == Decimal("950.00")
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_retencao_travada_com_parcela_em_lote_ativo(admin_engine):
    """Débito com parcela engajada num lote (PENDENTE, não FALHOU) barra
    criar/atualizar/excluir retenção com 409."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            parcela = (await s.execute(
                select(Parcela).where(Parcela.id_debito == debito.id)
            )).scalar_one()
            lote = LotePagamento(
                tenant_id=tenant.id, numero="L0001", id_conta_pagadora=conta_id,
                situacao="RASCUNHO", valor_total=Decimal("1000.00"),
                id_usuario=solicitante_id, criado_em=datetime.utcnow(),
            )
            s.add(lote)
            await s.flush()
            s.add(LotePagamentoParcela(
                tenant_id=tenant.id, id_lote=lote.id, id_parcela=parcela.id,
                situacao="PENDENTE", criado_em=datetime.utcnow(),
            ))
            await s.commit()

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await ret.criar_retencao(
                    s, tenant_id=tenant.id, debito_id=debito.id,
                    payload=RetencaoCreate(tipo="IRRF", base_calculo=Decimal("1000.00"),
                                           valor=Decimal("15.00")))
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_recolher_retencao_grava_campos(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            r = await ret.criar_retencao(
                s, tenant_id=tenant.id, debito_id=debito.id,
                payload=RetencaoCreate(tipo="INSS", base_calculo=Decimal("1000.00"),
                                       valor=Decimal("110.00")))
        assert r.recolhido is False

        async with _sm(admin_engine)() as s:
            recolhida = await ret.recolher_retencao(
                s, tenant_id=tenant.id, retencao_id=r.id,
                data_recolhimento=date(2026, 9, 20), documento_recolhimento="GPS-123",
            )
        assert recolhida.recolhido is True
        assert recolhida.data_recolhimento == date(2026, 9, 20)
        assert recolhida.documento_recolhimento == "GPS-123"

        async with _sm(admin_engine)() as s:
            pendentes = await ret.listar_pendentes_recolhimento(s, tenant_id=tenant.id)
        assert recolhida.id not in [p.id for p in pendentes]
    finally:
        await _cleanup(admin_engine, tenant.id)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


async def _usuario_com(engine, tenant_id: int, codigos: list[str]) -> int:
    """Usuário NÃO super-usuário, com exatamente as transações pedidas."""
    async with _sm(engine)() as s:
        sistema_id = int((await s.execute(text(
            "SELECT id FROM utils.sistema WHERE app=:a AND excluido=false LIMIT 1"
        ), {"a": APP})).scalar_one())
        nivel_id = (await s.execute(text(
            "SELECT id FROM utils.nivel WHERE valor <> 0 AND excluido = false LIMIT 1"
        ))).scalar_one_or_none()
        if nivel_id is None:
            nivel_id = (await s.execute(text(
                "INSERT INTO utils.nivel (nivel, valor, excluido) "
                "VALUES ('Operacional', 1, false) RETURNING id"))).scalar_one()
        uid = int((await s.execute(text("""
            INSERT INTO utils.usuario (tenant_id, nome, email, senha, cpf, ativo,
                                       excluido, app, nivel_acesso_sigilo)
            VALUES (:t, 'Usuario Comum Retencao', :e, '', :cpf, true, false, :a, 'interno')
            RETURNING id"""), {"t": tenant_id, "e": f"retencao-{uuid.uuid4().hex[:8]}@f4.test",
                               "cpf": uuid.uuid4().hex[:11], "a": APP})).scalar_one())
        gid = int((await s.execute(text("""
            INSERT INTO utils.grupo (tenant_id, id_nivel, id_sistema, grupo, excluido)
            VALUES (:t, :n, :s, :g, false) RETURNING id"""),
            {"t": tenant_id, "n": nivel_id, "s": sistema_id,
             "g": f"Grupo Retencao {uuid.uuid4().hex[:6]}"})).scalar_one())
        await s.execute(text("""
            INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app)
            VALUES (:t, :u, :g, true, false, :a)"""),
            {"t": tenant_id, "u": uid, "g": gid, "a": APP})
        for codigo in codigos:
            tr = (await s.execute(text(
                "SELECT id FROM utils.transacao WHERE codigo=:c AND excluido=false LIMIT 1"
            ), {"c": codigo})).scalar_one()
            await s.execute(text("""
                INSERT INTO utils.grupo_transacao
                    (tenant_id, id_grupo, id_transacao, inserir, atualizar, excluir, excluido)
                VALUES (:t, :g, :tr, true, true, true, false)"""),
                {"t": tenant_id, "g": gid, "tr": int(tr)})
        await s.commit()
    return uid


async def _get(engine, tenant_id, slug, usuario_id, caminho):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get(caminho)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


async def _post(engine, tenant_id, slug, usuario_id, caminho, body):
    async def _get_user():
        async with _sm(engine)() as s:
            return (await s.execute(
                select(Usuario).where(Usuario.id == usuario_id))).scalar_one()

    app.dependency_overrides[get_current_user] = _get_user
    arreio_tenant_http(tenant_id, slug)
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.post(caminho, json=body)
    finally:
        app.dependency_overrides.clear()
        from app.database import engine as app_engine
        await app_engine.dispose()


@pytest.mark.asyncio
async def test_http_usuario_comum_cria_e_le_retencao(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, _conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        uid = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])

        resp = await _post(
            admin_engine, tenant.id, tenant.slug, uid,
            f"/api/v2/pagamentos/debitos/{debito.id}/retencoes",
            {"tipo": "IRRF", "base_calculo": "1000.00", "aliquota": "1.5", "valor": "15.00"},
        )
        assert resp.status_code == 201, resp.text

        resp = await _get(
            admin_engine, tenant.id, tenant.slug, uid,
            f"/api/v2/pagamentos/debitos/{debito.id}/retencoes",
        )
        assert resp.status_code == 200, resp.text
        corpo = resp.json()
        assert corpo["valor_bruto"] == "1000.00"
        assert corpo["valor_liquido"] == "985.00"
        assert len(corpo["retencoes"]) == 1
    finally:
        await _cleanup(admin_engine, tenant.id)

"""Pagamentos v2.0 Fase 2C — liquidação, duplicidade, fornecedor irregular e
suspensão/reativação (RF-VAL-02/03, RF-SOL-09, RF-TES-06, RN-01).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _provisionar(engine):
    slug = f"pagval{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Val", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico")
    return tenant


async def _cleanup(engine, tenant_id: int) -> None:
    async with _sm(engine)() as s:
        for stmt in (
            "DELETE FROM pagamentos.ordem_pagamento_debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.ordem_pagamento WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito_historico WHERE tenant_id=:t",
            "UPDATE pagamentos.parcela SET id_movimentacao=NULL WHERE tenant_id=:t",
            "DELETE FROM pagamentos.movimentacao_conta WHERE tenant_id=:t",
            "DELETE FROM pagamentos.parcela WHERE tenant_id=:t",
            "DELETE FROM pagamentos.debito WHERE tenant_id=:t",
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
            "DELETE FROM pagamentos.natureza_despesa WHERE tenant_id=:t",
            "DELETE FROM pagamentos.conta_bancaria WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fonte_recursos WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id=:t",
            "DELETE FROM pagamentos.fornecedor WHERE tenant_id=:t",
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


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"U {sufixo}", "e": f"{sufixo}@t.local", "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _base(engine, tenant_id, *, situacao="REGULAR"):
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Forn", situacao_cadastral=situacao,
            motivo_pendencia=None if situacao == "REGULAR" else "Certidão vencida"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Mat"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial="10000.00"))
    return forn, nat, fonte, conta


def _payload(forn, nat, fonte, *, valor="1000.00", nf=None, ne=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
        valor_total=valor, competencia="2026-07", descricao="x", numero_nf=nf, numero_ne=ne,
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")])


async def test_duplicidade_bloqueia_criacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, _conta = await _base(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"u{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await deb.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                                   payload=_payload(forn, nat, fonte, nf="NF-123", ne="NE-1"))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await deb.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                                       payload=_payload(forn, nat, fonte, nf="NF-123", ne="NE-1"))
            assert exc.value.status_code == 409
            assert "duplicidade" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)


async def test_duplicidade_ignora_sem_nf(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, _conta = await _base(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"u{uuid.uuid4().hex[:6]}")
        # sem numero_nf → não há checagem de duplicidade
        async with _sm(admin_engine)() as s:
            await deb.criar_debito(s, tenant_id=t.id, usuario_id=uid, payload=_payload(forn, nat, fonte))
        async with _sm(admin_engine)() as s:
            d2 = await deb.criar_debito(s, tenant_id=t.id, usuario_id=uid, payload=_payload(forn, nat, fonte))
        assert d2.status == "RASCUNHO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_fornecedor_irregular_bloqueia_autorizacao(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id, situacao="IRREGULAR")
        sol = await _novo_usuario(admin_engine, t.id, f"s{uuid.uuid4().hex[:6]}")
        apr = await _novo_usuario(admin_engine, t.id, f"a{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d = await deb.criar_debito(s, tenant_id=t.id, usuario_id=sol,
                                       payload=_payload(forn, nat, fonte, ne="NE-1"))
        async with _sm(admin_engine)() as s:
            await deb.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=sol)
        async with _sm(admin_engine)() as s:
            await deb.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        async with _sm(admin_engine)() as s:
            await deb.confirmar_liquidacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        autorizador = await _novo_usuario(admin_engine, t.id, f"au{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autorizador, id_natureza=None, valor_maximo="999999.00"))
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, grupos=[
                    GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id])])
            assert exc.value.status_code == 422
            assert "irregular" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)


async def _pronto_para_autorizar(engine, tenant_id, forn, nat, fonte, *, valor="1000.00", ne="NE-1"):
    """Débito APROVADO + liquidado, com autorizador dotado de alçada. Retorna (d, autorizador)."""
    sol = await _novo_usuario(engine, tenant_id, f"s{uuid.uuid4().hex[:6]}")
    apr = await _novo_usuario(engine, tenant_id, f"a{uuid.uuid4().hex[:6]}")
    autorizador = await _novo_usuario(engine, tenant_id, f"au{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=sol,
                                   payload=_payload(forn, nat, fonte, valor=valor, ne=ne))
    async with _sm(engine)() as s:
        await deb.enviar_aprovacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=sol)
    async with _sm(engine)() as s:
        await deb.aprovar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=apr)
    async with _sm(engine)() as s:
        await deb.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=apr)
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=autorizador, id_natureza=None, valor_maximo="9999999.00"))
    return d, autorizador


async def test_autorizar_sem_empenho_bloqueia(admin_engine):
    """RN-01: sem número de empenho, não pode autorizar (mesmo liquidado)."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)
        d, autorizador = await _pronto_para_autorizar(admin_engine, t.id, forn, nat, fonte, ne=None)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, grupos=[
                    GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id])])
            assert exc.value.status_code == 422
            assert "empenho" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)


async def test_excecao_saldo_permite_com_justificativa(admin_engine):
    """RN-15: saldo insuficiente pode ser autorizado com exceção justificada; a
    justificativa é gravada no histórico (auditável)."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)  # saldo 10.000
        d, autorizador = await _pronto_para_autorizar(admin_engine, t.id, forn, nat, fonte, valor="50000.00")
        async with _sm(admin_engine)() as s:
            ops = await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, grupos=[
                GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id],
                                   permitir_saldo_insuficiente=True,
                                   justificativa_excecao="Pagamento judicial urgente")])
        assert len(ops) == 1
        async with _sm(admin_engine)() as s:
            hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        aut_hist = [h for h in hist if h.acao == "AUTORIZADO"]
        assert aut_hist and "EXCEÇÃO DE SALDO" in (aut_hist[0].justificativa or "")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_excecao_saldo_sem_justificativa_bloqueia(admin_engine):
    """RN-15: exceção sem justificativa é rejeitada."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta = await _base(admin_engine, t.id)
        d, autorizador = await _pronto_para_autorizar(admin_engine, t.id, forn, nat, fonte, valor="50000.00")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador, grupos=[
                    GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id],
                                       permitir_saldo_insuficiente=True)])
            assert exc.value.status_code == 422
            assert "justificativa" in exc.value.detail.lower()
    finally:
        await _cleanup(admin_engine, t.id)


async def test_detectar_duplicidade_considera_contrato(admin_engine):
    """RF-SOL-09: o contrato compõe a chave de duplicidade — mesma NF/empenho mas
    contrato distinto não é duplicata."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, _conta = await _base(admin_engine, t.id)
        uid = await _novo_usuario(admin_engine, t.id, f"u{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d = await deb.criar_debito(s, tenant_id=t.id, usuario_id=uid,
                                       payload=_payload(forn, nat, fonte, nf="NF-7", ne="NE-7"))
        async with _sm(admin_engine)() as s:
            # mesma NF/empenho/valor/competência, mas exigindo contrato específico → sem match
            outro_contrato = await deb.detectar_duplicidade(
                s, tenant_id=t.id, id_fornecedor=forn.id, numero_nf="NF-7", numero_ne="NE-7",
                valor_total=d.valor_total, competencia=d.competencia, id_contrato=999999)
            # sem restrição de contrato → encontra a duplicata
            sem_contrato = await deb.detectar_duplicidade(
                s, tenant_id=t.id, id_fornecedor=forn.id, numero_nf="NF-7", numero_ne="NE-7",
                valor_total=d.valor_total, competencia=d.competencia)
        assert outro_contrato == []
        assert d.id in sem_contrato
    finally:
        await _cleanup(admin_engine, t.id)


async def test_suspender_e_reativar(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, _conta = await _base(admin_engine, t.id)
        sol = await _novo_usuario(admin_engine, t.id, f"s{uuid.uuid4().hex[:6]}")
        apr = await _novo_usuario(admin_engine, t.id, f"a{uuid.uuid4().hex[:6]}")
        tes = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d = await deb.criar_debito(s, tenant_id=t.id, usuario_id=sol, payload=_payload(forn, nat, fonte))
        async with _sm(admin_engine)() as s:
            await deb.enviar_aprovacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=sol)
        async with _sm(admin_engine)() as s:
            await deb.aprovar(s, tenant_id=t.id, debito_id=d.id, usuario_id=apr)
        async with _sm(admin_engine)() as s:
            ds = await deb.suspender(s, tenant_id=t.id, debito_id=d.id, usuario_id=tes,
                                     justificativa="Suspeita de duplicidade")
        assert ds.status == "SUSPENSO"
        async with _sm(admin_engine)() as s:
            dr = await deb.reativar(s, tenant_id=t.id, debito_id=d.id, usuario_id=tes)
        assert dr.status == "APROVADO"
    finally:
        await _cleanup(admin_engine, t.id)

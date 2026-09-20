"""Testes da execução em lote (F4).

Task 1: invariantes da migration 0121 (`_provisionar`/`_criar_usuario`/
`_setup_debito`, copiados de `test_pagamentos_f3_fila.py`).

Task 3 (seleção/criação/revisão/cancelamento do lote, ao final do arquivo):
`_debito_liberado` e helpers associados copiados/adaptados de
`test_pagamentos_f3_pretericao.py::_debito_autorizado` — é o caminho mais
curto até uma parcela `LIBERADA` com `id_conta_pagadora` gravado (só
`pagamentos_autorizacao.autorizar_lote` grava essa coluna; `criar_lote`
exige que todas as parcelas do lote pertençam à MESMA conta pagadora).

**Simplificação deliberada**: nenhum teste aqui dispara o 409 de
`assert_ordem_respeitada` especificamente PELO `criar_lote`. Na prática, uma
parcela só chega a `LIBERADA` depois de passar pela MESMA guarda em
`liberar_parcelas` (F3) — então, dentro do rito normal, se `criar_lote`
consegue selecionar a parcela é porque a ordem já foi respeitada na
liberação. A chamada em `criar_lote` é defesa em profundidade para o caso
estreito de `MARCO_REGRAVADO` reabrir a fila DEPOIS da liberação (mesmo
padrão de dupla checagem que `pagar_parcela` já faz) — cenário não coberto
aqui por não valer o custo de montagem frente ao que resta da F4. A lógica
da guarda em si já é exaustivamente testada em `test_pagamentos_f3_pretericao.py`.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import LotePagamento, LotePagamentoParcela, Parcela
from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, ContratoCreate, DebitoCreate, FonteCreate,
    FornecedorCreate, GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_lotes as lot
from app.services.provisioning_tenant import provisionar_tenant
from tests.fixtures.pagamentos import id_unidade_padrao


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
    slug = _slug("pagf4lote")
    async with _sm(engine)() as s:
        tenant, _senha = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos F4 Lote", admin_email=f"{slug}@t.local",
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
            "DELETE FROM pagamentos.alcada WHERE tenant_id=:t",
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


async def _setup_debito(engine, tenant_id: int, usuario_id: int):
    """Cria um débito completo em rascunho, com 1 parcela, fonte, conta,
    fornecedor etc. Devolve (debito, id_conta_pagadora)."""
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
                valor_total=Decimal("1000.00"), descricao="Débito de Teste",
                competencia="2026-01",
                parcelas=[ParcelaCreate(numero=1, valor=Decimal("1000.00"), vencimento="2026-02-01")],
            ),
        )
    return debito, conta.id


@pytest.mark.asyncio
async def test_parcela_unica_em_lote_ativo(admin_engine):
    """Prova o UNIQUE parcial `(tenant_id, id_parcela) WHERE situacao <>
    'FALHOU'`: uma 2ª linha ativa para a mesma parcela estoura IntegrityError,
    mas uma 2ª linha `FALHOU` (reprocesso após falha) é permitida."""
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            parcela = (await s.execute(
                select(Parcela).where(Parcela.id_debito == debito.id)
            )).scalar_one()

        async with _sm(admin_engine)() as s:
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
            lote_id = lote.id

        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as s:
                s.add(LotePagamentoParcela(
                    tenant_id=tenant.id, id_lote=lote_id, id_parcela=parcela.id,
                    situacao="PENDENTE", criado_em=datetime.utcnow(),
                ))
                await s.commit()

        # Uma 2ª linha FALHOU para a MESMA parcela é permitida — reprocesso.
        async with _sm(admin_engine)() as s:
            s.add(LotePagamentoParcela(
                tenant_id=tenant.id, id_lote=lote_id, id_parcela=parcela.id,
                situacao="FALHOU", motivo_falha="conta encerrada",
                criado_em=datetime.utcnow(),
            ))
            await s.commit()
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_numero_lote_unico_por_tenant(admin_engine):
    """Prova o UNIQUE `(tenant_id, numero)` de `lote_pagamento`: mesmo número
    no mesmo tenant estoura IntegrityError; tenants diferentes, sem
    conflito."""
    tenant_a, sol_a = await _provisionar(admin_engine)
    tenant_b, sol_b = await _provisionar(admin_engine)
    try:
        _debito_a, conta_a = await _setup_debito(admin_engine, tenant_a.id, sol_a)
        _debito_b, conta_b = await _setup_debito(admin_engine, tenant_b.id, sol_b)

        async with _sm(admin_engine)() as s:
            s.add(LotePagamento(
                tenant_id=tenant_a.id, numero="L0001", id_conta_pagadora=conta_a,
                situacao="RASCUNHO", valor_total=Decimal("0"),
                id_usuario=sol_a, criado_em=datetime.utcnow(),
            ))
            await s.commit()

        with pytest.raises(IntegrityError):
            async with _sm(admin_engine)() as s:
                s.add(LotePagamento(
                    tenant_id=tenant_a.id, numero="L0001", id_conta_pagadora=conta_a,
                    situacao="RASCUNHO", valor_total=Decimal("0"),
                    id_usuario=sol_a, criado_em=datetime.utcnow(),
                ))
                await s.commit()

        # Mesmo número, tenant diferente — sem conflito.
        async with _sm(admin_engine)() as s:
            s.add(LotePagamento(
                tenant_id=tenant_b.id, numero="L0001", id_conta_pagadora=conta_b,
                situacao="RASCUNHO", valor_total=Decimal("0"),
                id_usuario=sol_b, criado_em=datetime.utcnow(),
            ))
            await s.commit()
    finally:
        await _cleanup(admin_engine, tenant_a.id)
        await _cleanup(admin_engine, tenant_b.id)


# ---------------------------------------------------------------------------
# Task 3 — seleção, criação, revisão, cancelamento
# ---------------------------------------------------------------------------


async def _fonte_conta(engine, tenant_id, *, saldo_inicial="10000.00"):
    async with _sm(engine)() as s:
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Lote", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
    return fonte, conta


async def _fornecedor2(engine, tenant_id, *, nome="Fornecedor Lote LTDA"):
    async with _sm(engine)() as s:
        return await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome=nome))


def _payload_debito2(forn, nat, fonte, conta, *, unidade_id: int, valor="1000.00"):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
        id_conta=conta.id, id_unidade=unidade_id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        numero_ne=f"NE-{uuid.uuid4().hex[:8]}", categoria="SERVICOS",
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _debito_liberado(engine, tenant_id, *, forn, nat, fonte, conta, unidade_id,
                           valor="1000.00"):
    """RASCUNHO -> ... -> AUTORIZADO (com `id_conta_pagadora` gravado via
    `autorizar_lote`) -> parcela LIBERADA. Devolve (debito, id_parcela)."""
    solicitante = await _criar_usuario(engine, tenant_id, "Solicitante Lote")
    gestor = await _criar_usuario(engine, tenant_id, "Gestor Lote")
    validador = await _criar_usuario(engine, tenant_id, "Validador Lote")
    autorizador = await _criar_usuario(engine, tenant_id, "Autorizador Lote")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito2(forn, nat, fonte, conta,
                                                            unidade_id=unidade_id, valor=valor))
    async with _sm(engine)() as s:
        d = await deb.enviar_para_gestor(s, tenant_id=tenant_id, debito_id=d.id,
                                         usuario_id=solicitante, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.gestor_autorizar(s, tenant_id=tenant_id, debito_id=d.id,
                                       usuario_id=gestor, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id,
                                           usuario_id=validador)
        d = await deb.validar(s, tenant_id=tenant_id, debito_id=d.id,
                              usuario_id=validador, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=autorizador, id_natureza=None, valor_maximo="999999.00"))
    grupo = GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id])
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, grupos=[grupo])
    async with _sm(engine)() as s:
        parcela = (await s.execute(
            select(Parcela).where(Parcela.id_debito == d.id))).scalar_one()
    async with _sm(engine)() as s:
        await aut.liberar_parcelas(s, tenant_id=tenant_id, usuario_id=autorizador,
                                   parcela_ids=[parcela.id])
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, parcela.id


@pytest.mark.asyncio
async def test_criar_lote_feliz(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte, conta = await _fonte_conta(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            unidade_id = await id_unidade_padrao(s, tenant.id)
        forn1 = await _fornecedor2(admin_engine, tenant.id, nome="Fornecedor Lote 1")
        forn2 = await _fornecedor2(admin_engine, tenant.id, nome="Fornecedor Lote 2")
        d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn1, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)
        d2, p2 = await _debito_liberado(admin_engine, tenant.id, forn=forn2, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)

        async with _sm(admin_engine)() as s:
            lote = await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta.id,
                                        parcela_ids=[p1, p2], usuario_id=d1.id_usuario_solicitante)
        assert lote.situacao == "RASCUNHO"
        assert lote.valor_total == Decimal("2000.00")
        assert lote.numero.startswith("L-")

        async with _sm(admin_engine)() as s:
            vinculos = await lot.parcelas_do_lote(s, tenant_id=tenant.id, lote_id=lote.id)
        assert {v.id_parcela for v in vinculos} == {p1, p2}
        assert all(v.situacao == "PENDENTE" for v in vinculos)

        # As duas parcelas somem de "elegíveis".
        async with _sm(admin_engine)() as s:
            elegiveis = await lot.parcelas_elegiveis_para_lote(s, tenant_id=tenant.id)
        assert p1 not in {p.id for p in elegiveis}
        assert p2 not in {p.id for p in elegiveis}
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_criar_lote_rejeita_conta_mista(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        async with _sm(admin_engine)() as s:
            unidade_id = await id_unidade_padrao(s, tenant.id)
        fonte, conta_a = await _fonte_conta(admin_engine, tenant.id)
        _fonte2, conta_b = await _fonte_conta(admin_engine, tenant.id)
        forn = await _fornecedor2(admin_engine, tenant.id)
        d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn, nat=nat,
                                        fonte=fonte, conta=conta_a, unidade_id=unidade_id)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta_b.id,
                                     parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 422
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_criar_lote_rejeita_parcela_nao_liberada(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        debito, conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            parcela = (await s.execute(
                select(Parcela).where(Parcela.id_debito == debito.id))).scalar_one()

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta_id,
                                     parcela_ids=[parcela.id], usuario_id=solicitante_id)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_criar_lote_vazio_e_422(admin_engine):
    tenant, solicitante_id = await _provisionar(admin_engine)
    try:
        _debito, conta_id = await _setup_debito(admin_engine, tenant.id, solicitante_id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta_id,
                                     parcela_ids=[], usuario_id=solicitante_id)
            assert e.value.status_code == 422
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_criar_lote_rejeita_parcela_ja_em_lote_ativo(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        async with _sm(admin_engine)() as s:
            unidade_id = await id_unidade_padrao(s, tenant.id)
        fonte, conta = await _fonte_conta(admin_engine, tenant.id)
        forn = await _fornecedor2(admin_engine, tenant.id)
        d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)

        async with _sm(admin_engine)() as s:
            await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta.id,
                                 parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta.id,
                                     parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_adicionar_remover_parcela_so_em_rascunho(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        async with _sm(admin_engine)() as s:
            unidade_id = await id_unidade_padrao(s, tenant.id)
        fonte, conta = await _fonte_conta(admin_engine, tenant.id)
        forn1 = await _fornecedor2(admin_engine, tenant.id, nome="Forn Add 1")
        forn2 = await _fornecedor2(admin_engine, tenant.id, nome="Forn Add 2")
        d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn1, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)
        d2, p2 = await _debito_liberado(admin_engine, tenant.id, forn=forn2, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)

        async with _sm(admin_engine)() as s:
            lote = await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta.id,
                                        parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)

        async with _sm(admin_engine)() as s:
            lote = await lot.adicionar_parcela(s, tenant_id=tenant.id, lote_id=lote.id,
                                               parcela_id=p2)
        assert lote.valor_total == Decimal("2000.00")

        async with _sm(admin_engine)() as s:
            lote = await lot.remover_parcela(s, tenant_id=tenant.id, lote_id=lote.id,
                                             parcela_id=p2)
        assert lote.valor_total == Decimal("1000.00")

        # Parcela removida volta a aparecer como elegível.
        async with _sm(admin_engine)() as s:
            elegiveis = await lot.parcelas_elegiveis_para_lote(s, tenant_id=tenant.id)
        assert p2 in {p.id for p in elegiveis}

        # Trava fora de RASCUNHO.
        async with _sm(admin_engine)() as s:
            await s.execute(text(
                "UPDATE pagamentos.lote_pagamento SET situacao='PROGRAMADO' WHERE id=:id"),
                {"id": lote.id})
            await s.commit()
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.adicionar_parcela(s, tenant_id=tenant.id, lote_id=lote.id,
                                            parcela_id=p2)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_cancelar_lote_libera_parcelas(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        async with _sm(admin_engine)() as s:
            unidade_id = await id_unidade_padrao(s, tenant.id)
        fonte, conta = await _fonte_conta(admin_engine, tenant.id)
        forn = await _fornecedor2(admin_engine, tenant.id)
        d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn, nat=nat,
                                        fonte=fonte, conta=conta, unidade_id=unidade_id)

        async with _sm(admin_engine)() as s:
            lote = await lot.criar_lote(s, tenant_id=tenant.id, id_conta_pagadora=conta.id,
                                        parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)

        async with _sm(admin_engine)() as s:
            cancelado = await lot.cancelar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                                usuario_id=d1.id_usuario_solicitante)
        assert cancelado.situacao == "CANCELADO"

        async with _sm(admin_engine)() as s:
            elegiveis = await lot.parcelas_elegiveis_para_lote(s, tenant_id=tenant.id)
        assert p1 in {p.id for p in elegiveis}

        # Cancelar de novo (já CANCELADO) é 409.
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.cancelar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                        usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


# ---------------------------------------------------------------------------
# Task 4 — programar, enviar, segregação de funções
# ---------------------------------------------------------------------------


async def _lote_de_um(admin_engine, tenant_id, *, nome_forn="Forn Envio"):
    """Monta fonte/conta/natureza/unidade + 1 débito LIBERADO + o lote
    RASCUNHO já criado. Devolve (lote, debito, id_parcela, conta)."""
    async with _sm(admin_engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
    async with _sm(admin_engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(admin_engine, tenant_id)
    forn = await _fornecedor2(admin_engine, tenant_id, nome=nome_forn)
    d1, p1 = await _debito_liberado(admin_engine, tenant_id, forn=forn, nat=nat,
                                    fonte=fonte, conta=conta, unidade_id=unidade_id)
    async with _sm(admin_engine)() as s:
        lote = await lot.criar_lote(s, tenant_id=tenant_id, id_conta_pagadora=conta.id,
                                    parcela_ids=[p1], usuario_id=d1.id_usuario_solicitante)
    return lote, d1, p1, conta


@pytest.mark.asyncio
async def test_programar_lote_vazio_e_409(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, p1, _conta = await _lote_de_um(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            await lot.remover_parcela(s, tenant_id=tenant.id, lote_id=lote.id, parcela_id=p1)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.programar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                         data_programada=date(2026, 9, 25),
                                         usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_enviar_lote_nao_programado_e_409(admin_engine):
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, _p1, _conta = await _lote_de_um(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.enviar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                      usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 409
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_programar_enviar_feliz(admin_engine):
    """Fluxo completo: envio move `situacao_pagamento` de PROGRAMADA (já
    gravada na liberação, F1) para ENVIADA_BANCO."""
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, _p1, _conta = await _lote_de_um(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            antes = await deb.obter_debito(s, tenant_id=tenant.id, debito_id=d1.id)
        assert antes.situacao_pagamento == "PROGRAMADA"

        async with _sm(admin_engine)() as s:
            lote = await lot.programar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                            data_programada=date(2026, 9, 25),
                                            usuario_id=d1.id_usuario_solicitante)
        assert lote.situacao == "PROGRAMADO"
        assert lote.data_programada == date(2026, 9, 25)

        # Um usuário que NÃO participou do rito deste débito pode enviar.
        enviador = await _criar_usuario(admin_engine, tenant.id, "Enviador")
        async with _sm(admin_engine)() as s:
            lote = await lot.enviar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                         usuario_id=enviador)
        assert lote.situacao == "ENVIADO"
        assert lote.enviado_em is not None
        assert lote.id_usuario_envio == enviador

        async with _sm(admin_engine)() as s:
            depois = await deb.obter_debito(s, tenant_id=tenant.id, debito_id=d1.id)
        assert depois.situacao_pagamento == "ENVIADA_BANCO"
    finally:
        await _cleanup(admin_engine, tenant.id)


@pytest.mark.asyncio
async def test_enviar_lote_segregacao_barra(admin_engine):
    """O solicitante do débito não pode enviar o lote que o contém — nem
    lote nem débito mudam de situação (all-or-nothing)."""
    tenant, _sol = await _provisionar(admin_engine)
    try:
        lote, d1, _p1, _conta = await _lote_de_um(admin_engine, tenant.id)
        async with _sm(admin_engine)() as s:
            lote = await lot.programar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                            data_programada=date(2026, 9, 25),
                                            usuario_id=d1.id_usuario_solicitante)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as e:
                await lot.enviar_lote(s, tenant_id=tenant.id, lote_id=lote.id,
                                      usuario_id=d1.id_usuario_solicitante)
            assert e.value.status_code == 403

        async with _sm(admin_engine)() as s:
            intacto = await lot.obter_lote(s, tenant_id=tenant.id, lote_id=lote.id)
        assert intacto.situacao == "PROGRAMADO"
        async with _sm(admin_engine)() as s:
            debito_intacto = await deb.obter_debito(s, tenant_id=tenant.id, debito_id=d1.id)
        assert debito_intacto.situacao_pagamento == "PROGRAMADA"
    finally:
        await _cleanup(admin_engine, tenant.id)

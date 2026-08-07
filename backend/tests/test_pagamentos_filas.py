"""Pagamentos — filas agregadas por conta (Task 2, R2c): `fila_autorizacao`,
`fila_liberacao`, `fila_tesouraria` em `services/pagamentos_filas.py`. Mesmo
padrão de `test_pagamentos_liberacao.py`; helpers duplicados para independência.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    AlcadaCreate, ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate,
    GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services import pagamentos_filas as filas
from app.services.provisioning_tenant import provisionar_tenant
from tests.fixtures.pagamentos import id_unidade_padrao


def _vence_em(dias: int) -> str:
    """Vencimento relativo a hoje.

    Datas absolutas apodrecem: este arquivo fixava `2026-08-01` e afirmava
    `vencida is False`, então virou vermelho sozinho quando o calendário passou
    dessa data — sem ninguém tocar em código de produção. O que o teste quer
    dizer é "vence no futuro", e é isso que ele passa a dizer.
    """
    return (date.today() + timedelta(days=dias)).isoformat()


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagfila")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Filas", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    return tenant


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


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
            "DELETE FROM pagamentos.contrato WHERE tenant_id=:t",
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


async def _base(engine, tenant_id, *, saldo_inicial="10000.00", nome_conta="Conta Fila"):
    """Fornecedor + natureza + fonte + conta prontos para um débito."""
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Fila LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome=nome_conta, banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))
        conta._id_unidade_teste = await id_unidade_padrao(s, tenant_id)
    return forn, nat, conta


def _payload_debito(forn, nat, conta, *, valor="1000.00", competencia="2026-07",
                    urgente=False, parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_unidade=conta._id_unidade_teste,
        id_fonte_recursos=conta.id_fonte_recursos, id_conta=conta.id,
        valor_total=valor, competencia=competencia, urgente=urgente,
        descricao="Compra de material", numero_ne="NE-2026-0001",  # empenho p/ autorizar (RN-01)
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento=_vence_em(30))],
    )


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _debito_aprovado(engine, tenant_id, *, base, valor="1000.00", competencia="2026-07",
                           urgente=False, parcelas=None, aprovador=None):
    """Débito RASCUNHO→ENVIADO→APROVADO com solicitante/aprovador distintos.
    Retorna (debito, solicitante_id, aprovador_id)."""
    forn, nat, conta = base
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    gestor = await _novo_usuario(engine, tenant_id, f"ges{uuid.uuid4().hex[:6]}")
    if aprovador is None:
        aprovador = await _novo_usuario(engine, tenant_id, f"apr{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, conta, valor=valor,
                                                           competencia=competencia,
                                                           urgente=urgente, parcelas=parcelas))
    async with _sm(engine)() as s:
        d = await deb.enviar_para_gestor(
            s, tenant_id=tenant_id, debito_id=d.id, usuario_id=solicitante,
            lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.gestor_autorizar(
            s, tenant_id=tenant_id, debito_id=d.id, usuario_id=gestor,
            lock_version=d.lock_version)
    async with _sm(engine)() as s:  # liquidação é pré-requisito p/ validar (RN-01)
        d = await deb.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador)
    async with _sm(engine)() as s:
        d = await deb.validar(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=aprovador,
                             lock_version=d.lock_version)
    return d, solicitante, aprovador


async def _dar_alcada(engine, tenant_id, usuario_id, *, valor_maximo="999999.00", id_natureza=None):
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=usuario_id, id_natureza=id_natureza, valor_maximo=valor_maximo))


async def _autorizador_com_alcada(engine, tenant_id, *, valor_maximo="999999.00"):
    uid = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")
    await _dar_alcada(engine, tenant_id, uid, valor_maximo=valor_maximo)
    return uid


async def _debito_autorizado(engine, tenant_id, *, base, valor="1000.00", competencia="2026-07",
                             urgente=False, parcelas=None, autorizador=None):
    """Débito RASCUNHO→...→APROVADO→AUTORIZADO. Retorna (debito, solicitante_id,
    aprovador_id, autorizador_id, op)."""
    d, solicitante, aprovador = await _debito_aprovado(
        engine, tenant_id, base=base, valor=valor, competencia=competencia,
        urgente=urgente, parcelas=parcelas)
    if autorizador is None:
        autorizador = await _autorizador_com_alcada(engine, tenant_id)
    async with _sm(engine)() as s:
        ops = await aut.autorizar_lote(
            s, tenant_id=tenant_id, usuario_id=autorizador,
            grupos=[GrupoAutorizacaoIn(id_fonte=d.id_fonte_recursos,
                                       id_conta_pagadora=d.id_conta, debito_ids=[d.id])])
        op = ops[0]
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, solicitante, aprovador, autorizador, op


# ============================ fila_autorizacao ==================================
async def test_fila_autorizacao_agrupa_por_fonte_urgente_primeiro(admin_engine):
    """v2.0: fila agrupada por FONTE; cada grupo traz débitos (urgentes primeiro)
    e as contas elegíveis da fonte com saldo/disponível."""
    t = await _provisionar(admin_engine)
    try:
        base_a = await _base(admin_engine, t.id, nome_conta="Conta A")  # fonte A
        base_b = await _base(admin_engine, t.id, nome_conta="Conta B")  # fonte B
        fonte_a_id = base_a[2].id_fonte_recursos
        fonte_b_id = base_b[2].id_fonte_recursos

        aprovador_unico = await _novo_usuario(admin_engine, t.id, f"aprX{uuid.uuid4().hex[:6]}")

        # Fonte B: normal (competencia 2026-06) + urgente (competencia 2026-07)
        d_normal, _s1, _apr1 = await _debito_aprovado(
            admin_engine, t.id, base=base_b, valor="500.00", competencia="2026-06",
            urgente=False, aprovador=aprovador_unico)
        d_urgente, _s2, _apr2 = await _debito_aprovado(
            admin_engine, t.id, base=base_b, valor="300.00", competencia="2026-07",
            urgente=True, aprovador=aprovador_unico)
        # Fonte A: 1 débito
        d_a, _s3, _apr3 = await _debito_aprovado(
            admin_engine, t.id, base=base_a, valor="900.00", competencia="2026-07",
            urgente=False, aprovador=aprovador_unico)

        async with _sm(admin_engine)() as s:
            grupos = await filas.fila_autorizacao(s, tenant_id=t.id)

        assert len(grupos) == 2
        por_fonte = {g.id_fonte: g for g in grupos}
        assert set(por_fonte) == {fonte_a_id, fonte_b_id}

        grupo_a = por_fonte[fonte_a_id]
        assert [it.id for it in grupo_a.debitos] == [d_a.id]
        # conta elegível da fonte A com disponível cheio
        assert [c.id_conta for c in grupo_a.contas_elegiveis] == [base_a[2].id]
        assert grupo_a.contas_elegiveis[0].disponivel == Decimal("10000.00")
        assert grupo_a.contas_elegiveis[0].abaixo_minimo is False

        async with _sm(admin_engine)() as s:
            nomes_u = await deb.nomes_usuarios(s, tenant_id=t.id, ids={aprovador_unico})

        grupo_b = por_fonte[fonte_b_id]
        assert [it.id for it in grupo_b.debitos] == [d_urgente.id, d_normal.id]
        item_urgente = grupo_b.debitos[0]
        assert item_urgente.urgente is True
        assert item_urgente.aprovado_por == nomes_u[aprovador_unico]
        assert item_urgente.aprovado_em is not None
        assert item_urgente.natureza_codigo == base_b[1].codigo
        assert item_urgente.nome_fornecedor == base_b[0].nome
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ fila_liberacao ==================================
async def test_fila_liberacao_agrupa_por_conta_com_op_e_ordena_por_vencimento(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, nome_conta="Conta Liberacao")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        d, _sol, _apr, _aut_id, op = await _debito_autorizado(
            admin_engine, t.id, base=base, valor="1000.00", parcelas=[
                ParcelaCreate(numero=1, valor="600.00", vencimento=_vence_em(40)),
                ParcelaCreate(numero=2, valor="400.00", vencimento=_vence_em(30)),
            ], autorizador=autorizador)

        async with _sm(admin_engine)() as s:
            grupos = await filas.fila_liberacao(s, tenant_id=t.id)

        assert len(grupos) == 1
        grupo = grupos[0]
        assert grupo.nome_conta == "Conta Liberacao"
        assert len(grupo.parcelas) == 2
        # ordenado por vencimento asc
        assert [p.numero for p in grupo.parcelas] == [2, 1]
        item = grupo.parcelas[0]
        assert item.id_debito == d.id
        assert item.qtd_parcelas == 2
        assert item.op_numero == op.numero
        assert item.op_id == op.id
        assert item.nome_fornecedor == base[0].nome
        assert item.vencida is False
        assert item.dias_atraso == 0
    finally:
        await _cleanup(admin_engine, t.id)


# ============================ fila_tesouraria ==================================
async def test_fila_tesouraria_liberadas_e_pagas_recentes(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, nome_conta="Conta Tesouraria")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")

        # débito 1: parcela LIBERADA
        d1, _s1, _a1, _aut1, op1 = await _debito_autorizado(
            admin_engine, t.id, base=base, valor="500.00", autorizador=autorizador)
        async with _sm(admin_engine)() as s:
            p1 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d1.id))[0]
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[p1.id], data_prevista=date(2026, 8, 5))

        # débito 2: parcela PAGA
        d2, _s2, _a2, _aut2, op2 = await _debito_autorizado(
            admin_engine, t.id, base=base, valor="700.00", autorizador=autorizador)
        async with _sm(admin_engine)() as s:
            p2 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d2.id))[0]
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador, parcela_ids=[p2.id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=p2.id,
                                    forma_pagamento="PIX")

        async with _sm(admin_engine)() as s:
            out = await filas.fila_tesouraria(s, tenant_id=t.id)

        assert len(out.liberadas) == 1
        lib = out.liberadas[0]
        assert lib.id == p1.id
        assert lib.data_liberacao is not None
        assert lib.liberado_por is not None
        assert lib.op_numero == op1.numero
        assert str(lib.data_prevista_pagamento) == "2026-08-05"

        pagas_ids = [p.id for p in out.pagas_recentes]
        assert p2.id in pagas_ids
        assert p1.id not in pagas_ids
        item_pago = next(p for p in out.pagas_recentes if p.id == p2.id)
        assert item_pago.data_pagamento is not None
        assert item_pago.op_numero == op2.numero
    finally:
        await _cleanup(admin_engine, t.id)

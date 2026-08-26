"""Pagamentos v2.0 — Autorização por grupo {fonte, conta pagadora, débitos}.

Cobre `services/pagamentos_autorizacao.py`. A partir da v2.0 a fonte vem do
empenho (gravada no débito) e a **conta pagadora** é escolhida na autorização,
apenas entre contas ATIVAS da mesma fonte; o valor é reservado nessa conta
(imutável). `autorizar_lote` recebe grupos e é all-or-nothing sobre todos eles:
valida fonte↔conta, segregação (solicitante/aprovadores), alçada e saldo
disponível projetado antes de gravar qualquer coisa.

Critérios de aceite do spec: CA-AUT-01 (só contas da fonte), CA-AUT-03 (conta de
outra fonte rejeitada), CA-AUT-04 (saldo insuficiente bloqueia), CA-AUT-05
(reserva reduz disponível), RF-AUT-11 (fonte sem conta ativa bloqueia), RF-AUT-15
(fontes distintas no mesmo grupo bloqueadas). Mesmo padrão de
`test_pagamentos_debitos.py` (provisionar_tenant + admin_engine).
"""
from __future__ import annotations

from decimal import Decimal
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
from app.services import pagamentos_caixa as caixa
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_debitos as deb
from app.services.provisioning_tenant import provisionar_tenant
from tests.fixtures.pagamentos import id_unidade_padrao


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


async def _provisionar(engine):
    slug = _slug("pagaut")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Autorizacao", admin_email=f"{slug}@t.local",
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
            "DELETE FROM pagamentos.posicao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.excecao_cronologica WHERE tenant_id=:t",
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


async def _fonte_conta(engine, tenant_id, *, saldo_inicial="10000.00", ativa=True):
    """Cria uma fonte e uma conta ligada a ela. Retorna (fonte, conta)."""
    async with _sm(engine)() as s:
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Aut", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO",
            saldo_inicial=saldo_inicial, ativa=ativa))
    return fonte, conta


async def _base(engine, tenant_id, *, saldo_inicial="10000.00"):
    """Fornecedor + natureza + fonte + conta prontos para um débito."""
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Aut LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        unidade_id = await id_unidade_padrao(s, tenant_id)
    fonte, conta = await _fonte_conta(engine, tenant_id, saldo_inicial=saldo_inicial)
    return forn, nat, fonte, conta, unidade_id


def _payload_debito(forn, nat, fonte, conta=None, *, unidade_id: int,
                    valor="1000.00", parcelas=None):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_fonte_recursos=fonte.id,
        id_conta=conta.id if conta is not None else None,
        id_unidade=unidade_id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        numero_ne="NE-2026-0001",  # empenho obrigatório para autorizar (RN-01)
        categoria="SERVICOS",  # débito sem contrato: exigida p/ confirmar_liquidacao (F3)
        parcelas=parcelas or [ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


def _grupo(fonte, conta, debitos) -> GrupoAutorizacaoIn:
    ds = debitos if isinstance(debitos, (list, tuple)) else [debitos]
    return GrupoAutorizacaoIn(id_fonte=fonte.id, id_conta_pagadora=conta.id,
                              debito_ids=[d.id for d in ds])


async def _autorizar(engine, tenant_id, usuario_id, *, fonte, conta, debitos):
    """Autoriza um único grupo. Retorna a lista de OPs criadas."""
    async with _sm(engine)() as s:
        return await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=usuario_id,
                                        grupos=[_grupo(fonte, conta, debitos)])


async def _novo_usuario(engine, tenant_id, sufixo):
    """Segundo usuário no tenant (para segregação)."""
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _debito_aprovado(engine, tenant_id, *, valor="1000.00", saldo_inicial="10000.00",
                           parcelas=None, base=None, liquidar=True):
    """Débito no rito v2.0 até ENVIADO_SECRETARIO (fila da autoridade): RASCUNHO →
    EM_VALIDACAO → (liquidação) → VALIDADO → ENVIADO_SECRETARIO, com solicitante e
    validador distintos. Retorna (debito, solicitante_id, validador_id, fonte, conta).
    Com liquidar=False para em EM_VALIDACAO (sem liquidação, não pode validar)."""
    if base is None:
        forn, nat, fonte, conta, unidade_id = await _base(
            engine, tenant_id, saldo_inicial=saldo_inicial)
    else:
        forn, nat, fonte, conta, unidade_id = base
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    gestor = await _novo_usuario(engine, tenant_id, f"ges{uuid.uuid4().hex[:6]}")
    validador = await _novo_usuario(engine, tenant_id, f"val{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        d = await deb.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(
                                       forn, nat, fonte, conta, unidade_id=unidade_id,
                                       valor=valor, parcelas=parcelas))
    async with _sm(engine)() as s:
        d = await deb.enviar_para_gestor(
            s, tenant_id=tenant_id, debito_id=d.id, usuario_id=solicitante,
            lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await deb.gestor_autorizar(
            s, tenant_id=tenant_id, debito_id=d.id, usuario_id=gestor,
            lock_version=d.lock_version)
    if liquidar:  # liquidação → validar (chega à fila da autoridade)
        async with _sm(engine)() as s:
            # F3: confirmar_liquidacao agora passa por `_registrar_transicao`
            # (fila=REGISTRADA) e incrementa lock_version — precisa capturar
            # o retorno, senão o `validar` abaixo usa lock_version obsoleto.
            d = await deb.confirmar_liquidacao(
                s, tenant_id=tenant_id, debito_id=d.id, usuario_id=validador)
        async with _sm(engine)() as s:
            d = await deb.validar(
                s, tenant_id=tenant_id, debito_id=d.id, usuario_id=validador,
                lock_version=d.lock_version)
    else:
        async with _sm(engine)() as s:
            d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, solicitante, validador, fonte, conta


async def _dar_alcada(engine, tenant_id, usuario_id, *, valor_maximo="999999.00", id_natureza=None):
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=usuario_id, id_natureza=id_natureza, valor_maximo=valor_maximo))


async def _autorizador_com_alcada(engine, tenant_id, *, valor_maximo="999999.00"):
    uid = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")
    await _dar_alcada(engine, tenant_id, uid, valor_maximo=valor_maximo)
    return uid


async def _debito_autorizado(engine, tenant_id, *, valor="1000.00", saldo_inicial="10000.00",
                             parcelas=None, base=None):
    """Débito RASCUNHO→...→APROVADO→AUTORIZADO. Retorna (debito, solicitante_id,
    aprovador_id, autorizador_id, fonte, conta)."""
    d, solicitante, aprovador, fonte, conta = await _debito_aprovado(
        engine, tenant_id, valor=valor, saldo_inicial=saldo_inicial, parcelas=parcelas, base=base)
    autorizador = await _autorizador_com_alcada(engine, tenant_id)
    await _autorizar(engine, tenant_id, autorizador, fonte=fonte, conta=conta, debitos=[d])
    async with _sm(engine)() as s:
        d = await deb.obter_debito(s, tenant_id=tenant_id, debito_id=d.id)
    return d, solicitante, aprovador, autorizador, fonte, conta


async def test_autorizar_gera_op_grava_conta_pagadora_e_reserva(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        ops = await _autorizar(admin_engine, t.id, autorizador, fonte=fonte, conta=conta, debitos=[d])
        assert len(ops) == 1
        op = ops[0]
        assert op.numero.startswith("OP-") and op.numero.endswith("-0001")
        assert op.valor_total == Decimal("1000.00")
        assert op.id_conta_pagadora == conta.id
        assert op.valor_reservado == Decimal("1000.00")
        # RF-AUT-16: saldo antes/projetado após a reserva gravados na OP
        assert op.saldo_antes == Decimal("10000.00")
        assert op.saldo_projetado_apos == Decimal("9000.00")
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            hist = await deb.listar_historico(s, tenant_id=t.id, debito_id=d.id)
            debs_op = await aut.debitos_da_ordem(s, tenant_id=t.id, ordem_id=op.id)
        assert d2.status == "AUTORIZADO"
        assert d2.id_conta_pagadora == conta.id      # gravada imutável na autorização
        assert hist[0].acao == "AUTORIZADO"
        assert [x.id for x in debs_op] == [d.id]
    finally:
        await _cleanup(admin_engine, t.id)


async def test_ca_aut_01_contas_elegiveis_apenas_da_fonte(admin_engine):
    """CA-AUT-01: contas_elegiveis lista só contas ATIVAS da fonte informada."""
    t = await _provisionar(admin_engine)
    try:
        fonte1, conta1 = await _fonte_conta(admin_engine, t.id)
        fonte2, conta2 = await _fonte_conta(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            elegiveis1 = await aut.contas_elegiveis(s, tenant_id=t.id, id_fonte=fonte1.id)
        ids = {c.id_conta for c in elegiveis1}
        assert ids == {conta1.id}
        assert conta2.id not in ids
        # conta mascarada expõe só os últimos 4 dígitos
        assert elegiveis1[0].conta_mascarada.startswith("****")
        # RF-AUT-05: reservado e disponível projetado expostos por conta elegível
        assert elegiveis1[0].reservado == Decimal("0")
        assert elegiveis1[0].disponivel_projetado == elegiveis1[0].disponivel
    finally:
        await _cleanup(admin_engine, t.id)


async def test_ca_aut_03_conta_de_outra_fonte_rejeitada(admin_engine):
    """CA-AUT-03/RN-06: autorizar pagando por conta que não é da fonte → 422."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte1, _conta1 = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        _fonte2, conta2 = await _fonte_conta(admin_engine, t.id)  # conta de OUTRA fonte
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(
                    s, tenant_id=t.id, usuario_id=autorizador,
                    grupos=[GrupoAutorizacaoIn(id_fonte=fonte1.id, id_conta_pagadora=conta2.id,
                                               debito_ids=[d.id])])
            assert exc.value.status_code == 422
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "ENVIADO_SECRETARIO" and d2.id_conta_pagadora is None
    finally:
        await _cleanup(admin_engine, t.id)


async def test_ca_aut_04_saldo_insuficiente_bloqueia_422(admin_engine):
    """CA-AUT-04: disponível projetado da conta pagadora < Σ → 422, sem gravar."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00", saldo_inicial="100.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 422
            assert "saldo" in exc.value.detail.lower()
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_ca_aut_05_reserva_reduz_disponivel(admin_engine):
    """CA-AUT-05: autorizar reserva na conta pagadora e reduz o disponível."""
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, saldo_inicial="1000.00")
        _forn, _nat, fonte, conta, _unidade_id = base
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)

        d_a, _sol_a, _apr_a, _f, _c = await _debito_aprovado(
            admin_engine, t.id, valor="800.00", base=base)
        await _autorizar(admin_engine, t.id, autorizador, fonte=fonte, conta=conta, debitos=[d_a])

        async with _sm(admin_engine)() as s:
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.comprometido == Decimal("800.00")
        assert saldo.disponivel == Decimal("200.00")

        # segunda autorização na mesma conta não cabe no disponível remanescente
        d_b, _sol_b, _apr_b, _f2, _c2 = await _debito_aprovado(
            admin_engine, t.id, valor="500.00", base=base)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         grupos=[_grupo(fonte, conta, [d_b])])
            assert exc.value.status_code == 422
        async with _sm(admin_engine)() as s:
            d_b2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_b.id)
        assert d_b2.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_rf_aut_11_fonte_sem_conta_ativa_bloqueia(admin_engine):
    """RF-AUT-11: fonte sem conta ativa → elegíveis vazio e autorização por
    conta inativa é 422."""
    t = await _provisionar(admin_engine)
    try:
        async with _sm(admin_engine)() as s:
            forn = await cad.criar_fornecedor(s, tenant_id=t.id, payload=FornecedorCreate(
                tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Forn LTDA"))
            nat = await cad.criar_natureza(s, tenant_id=t.id, payload=NaturezaCreate(
                codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
            unidade_id = await id_unidade_padrao(s, t.id)
        fonte, conta = await _fonte_conta(admin_engine, t.id, ativa=False)  # conta INATIVA

        async with _sm(admin_engine)() as s:
            elegiveis = await aut.contas_elegiveis(s, tenant_id=t.id, id_fonte=fonte.id)
        assert elegiveis == []

        # débito da fonte (sem conta sugerida) percorre o rito até ENVIADO_SECRETARIO
        sol = await _novo_usuario(admin_engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
        gestor = await _novo_usuario(admin_engine, t.id, f"ges{uuid.uuid4().hex[:6]}")
        val = await _novo_usuario(admin_engine, t.id, f"val{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            d = await deb.criar_debito(s, tenant_id=t.id, usuario_id=sol,
                                       payload=_payload_debito(
                                           forn, nat, fonte, conta=None,
                                           unidade_id=unidade_id))
        async with _sm(admin_engine)() as s:
            d = await deb.enviar_para_gestor(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=sol,
                lock_version=d.lock_version)
        async with _sm(admin_engine)() as s:
            d = await deb.gestor_autorizar(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=gestor,
                lock_version=d.lock_version)
        async with _sm(admin_engine)() as s:
            d = await deb.confirmar_liquidacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=val)
        async with _sm(admin_engine)() as s:
            d = await deb.validar(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=val,
                lock_version=d.lock_version)

        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 422
    finally:
        await _cleanup(admin_engine, t.id)


async def test_rf_aut_15_fontes_distintas_no_grupo_bloqueadas(admin_engine):
    """RF-AUT-15: débito de fonte diferente da declarada no grupo → 422."""
    t = await _provisionar(admin_engine)
    try:
        d1, _s1, _a1, fonte1, conta1 = await _debito_aprovado(admin_engine, t.id, valor="500.00")
        d2, _s2, _a2, _fonte2, _conta2 = await _debito_aprovado(admin_engine, t.id, valor="500.00")
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(
                    s, tenant_id=t.id, usuario_id=autorizador,
                    grupos=[GrupoAutorizacaoIn(id_fonte=fonte1.id, id_conta_pagadora=conta1.id,
                                               debito_ids=[d1.id, d2.id])])
            assert exc.value.status_code == 422
        async with _sm(admin_engine)() as s:
            d1b = await deb.obter_debito(s, tenant_id=t.id, debito_id=d1.id)
            d2b = await deb.obter_debito(s, tenant_id=t.id, debito_id=d2.id)
        assert d1b.status == "ENVIADO_SECRETARIO" and d2b.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_validar_sem_liquidacao_422(admin_engine):
    """RN-01/RF-VAL-02: sem liquidação confirmada, o débito não pode ser validado."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, val, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00", liquidar=False)  # fica em EM_VALIDACAO
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await deb.validar(
                    s, tenant_id=t.id, debito_id=d.id, usuario_id=val,
                    lock_version=d.lock_version)
            assert exc.value.status_code == 422
            assert "liquidação" in exc.value.detail.lower()
        # confirmando a liquidação: validar → autoriza
        async with _sm(admin_engine)() as s:
            d = await deb.confirmar_liquidacao(s, tenant_id=t.id, debito_id=d.id, usuario_id=val)
        async with _sm(admin_engine)() as s:
            d = await deb.validar(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=val,
                lock_version=d.lock_version)
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        ops = await _autorizar(admin_engine, t.id, autorizador, fonte=fonte, conta=conta, debitos=[d])
        assert len(ops) == 1
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_acima_da_alcada_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador_baixo = await _autorizador_com_alcada(admin_engine, t.id, valor_maximo="500.00")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador_baixo,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 403
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "ENVIADO_SECRETARIO"

        sem_alcada = await _novo_usuario(admin_engine, t.id, f"nal{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=sem_alcada,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 403
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d3.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_alcada_por_fonte_mais_especifica_vence(admin_engine):
    """RF-CAD-06: alçada escopada pela fonte do débito vence a geral (menor). Um
    autorizador com geral R$ 500 mas alçada da fonte R$ 5000 autoriza débito R$ 1000."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        autorizador = await _novo_usuario(admin_engine, t.id, f"au{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autorizador, id_natureza=None, valor_maximo="500.00"))  # geral, baixa
            await cad.criar_alcada(s, tenant_id=t.id, payload=AlcadaCreate(
                id_usuario=autorizador, id_natureza=None, id_fonte=fonte.id,
                valor_maximo="5000.00"))  # específica da fonte, alta
        ops = await _autorizar(admin_engine, t.id, autorizador, fonte=fonte, conta=conta, debitos=[d])
        assert len(ops) == 1
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "AUTORIZADO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizar_por_solicitante_ou_aprovador_403(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, solicitante, aprovador, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00")
        await _dar_alcada(admin_engine, t.id, solicitante)
        await _dar_alcada(admin_engine, t.id, aprovador)

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=solicitante,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 403

        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=aprovador,
                                         grupos=[_grupo(fonte, conta, [d])])
            assert exc.value.status_code == 403

        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_autorizacao_em_lote_all_or_nothing(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        base = await _base(admin_engine, t.id, saldo_inicial="1000.00")
        _forn, _nat, fonte, conta, _unidade_id = base
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)

        d_a, _sol_a, _apr_a, _f, _c = await _debito_aprovado(
            admin_engine, t.id, valor="600.00", base=base)
        d_b, _sol_b, _apr_b, _f2, _c2 = await _debito_aprovado(
            admin_engine, t.id, valor="600.00", base=base)

        # os dois somam 1200 > 1000 disponível → nada é gravado
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.autorizar_lote(s, tenant_id=t.id, usuario_id=autorizador,
                                         grupos=[_grupo(fonte, conta, [d_a, d_b])])
            assert exc.value.status_code == 422

        async with _sm(admin_engine)() as s:
            d_a2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_a.id)
            d_b2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d_b.id)
        assert d_a2.status == "ENVIADO_SECRETARIO"
        assert d_b2.status == "ENVIADO_SECRETARIO"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_deduz_saldo_e_finaliza_debito(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, fonte, conta = await _debito_aprovado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        autorizador = await _autorizador_com_alcada(admin_engine, t.id)
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        await _autorizar(admin_engine, t.id, autorizador, fonte=fonte, conta=conta, debitos=[d])
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[0].id])
        async with _sm(admin_engine)() as s:
            p1 = await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                         parcela_id=parcelas[0].id, forma_pagamento="PIX")
        assert p1.status == "PAGA" and p1.id_movimentacao is not None
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d2.status == "PAGO_PARCIAL"
        assert saldo.saldo_atual == Decimal("9400.00")
        assert saldo.comprometido == Decimal("400.00")
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[1].id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[1].id, forma_pagamento="TED")
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo2 = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d3.status == "PAGO"
        assert saldo2.saldo_atual == Decimal("9000.00")
        assert saldo2.comprometido == Decimal("0")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_de_debito_nao_autorizado_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, _fonte, _conta = await _debito_aprovado(admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcelas[0].id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            p2 = (await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id))[0]
        assert d2.status == "ENVIADO_SECRETARIO"
        assert p2.status == "A_PAGAR"
    finally:
        await _cleanup(admin_engine, t.id)


async def test_pagar_parcela_ja_paga_409(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _fonte, _conta = await _debito_autorizado(
            admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[0].id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            with pytest.raises(HTTPException) as exc:
                await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                        parcela_id=parcelas[0].id, forma_pagamento="PIX")
            assert exc.value.status_code == 409
    finally:
        await _cleanup(admin_engine, t.id)


async def test_estornar_parcela_repoe_saldo_e_reabre(admin_engine):
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _fonte, conta = await _debito_autorizado(
            admin_engine, t.id, valor="1000.00",
            parcelas=[ParcelaCreate(numero=1, valor="600.00", vencimento="2026-08-01"),
                      ParcelaCreate(numero=2, valor="400.00", vencimento="2026-09-01")])
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[0].id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[1].id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[1].id, forma_pagamento="TED")
        async with _sm(admin_engine)() as s:
            d1 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d1.status == "PAGO"

        async with _sm(admin_engine)() as s:
            p2_estornada = await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcelas[1].id,
                justificativa="Pagamento em duplicidade")
        assert p2_estornada.status == "A_PAGAR"
        assert p2_estornada.data_pagamento is None
        assert p2_estornada.forma_pagamento is None
        assert p2_estornada.id_movimentacao is None
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert d2.status == "PAGO_PARCIAL"
        assert saldo.saldo_atual == Decimal("9400.00")
        assert saldo.comprometido == Decimal("400.00")

        async with _sm(admin_engine)() as s:
            await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcelas[0].id,
                justificativa="Pagamento em duplicidade")
        async with _sm(admin_engine)() as s:
            d3 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            saldo2 = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        # pagamento integralmente revertido → ESTORNADO (v2.0 seção 13)
        assert d3.status == "ESTORNADO"
        assert saldo2.saldo_atual == Decimal("10000.00")
        assert saldo2.comprometido == Decimal("1000.00")
    finally:
        await _cleanup(admin_engine, t.id)


async def test_estornar_parcela_com_justificativa_longa_trunca_descricao(admin_engine):
    """justificativa com 255 chars pode estourar o String(255) da descrição
    (que também inclui o prefixo 'Estorno parcela N — débito #ID: '). A
    descrição gravada deve ser truncada em 255 chars — sem erro de banco."""
    t = await _provisionar(admin_engine)
    try:
        d, _sol, _apr, autorizador, _fonte, _conta = await _debito_autorizado(
            admin_engine, t.id, valor="1000.00")
        tesoureiro = await _novo_usuario(admin_engine, t.id, f"tes{uuid.uuid4().hex[:6]}")
        justificativa_longa = "J" * 255
        async with _sm(admin_engine)() as s:
            parcelas = await deb.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=autorizador,
                                       parcela_ids=[parcelas[0].id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=tesoureiro,
                                    parcela_id=parcelas[0].id, forma_pagamento="PIX")
        async with _sm(admin_engine)() as s:
            p_estornada = await aut.estornar_parcela(
                s, tenant_id=t.id, usuario_id=tesoureiro, parcela_id=parcelas[0].id,
                justificativa=justificativa_longa)
        assert p_estornada.status == "A_PAGAR"
        async with _sm(admin_engine)() as s:
            d2 = await deb.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.status == "ESTORNADO"  # reversão integral (v2.0 seção 13)
    finally:
        await _cleanup(admin_engine, t.id)

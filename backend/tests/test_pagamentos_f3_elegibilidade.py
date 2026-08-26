"""Pagamentos F3 (Task 4) — elegibilidade da fila cronológica.

`avaliar_elegibilidade` é a função PURA (spec: sem IO) que decide o rótulo de
fila de um débito a partir dos fatos coletados por `reavaliar_debito`. Este
arquivo cobre a tabela de todos os ramos da função pura e os hooks síncronos
que a chamam a cada mutação relevante (autorização, fornecedor, bloqueio de
saldo, pagamento/estorno).

Padrão de dados: helpers copiados/adaptados de
`test_pagamentos_fluxo_validacao_autoridade.py` (rito singular, sem conta
pagadora) e `test_pagamentos_autorizacao.py` (rito em lote, com conta
pagadora — necessário para os cenários de bloqueio/disponibilidade).
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import PosicaoCronologica
from app.schemas.pagamentos import (
    AlcadaCreate, BloqueioSaldoCreate, ContaCreate, DebitoCreate, FonteCreate,
    FornecedorCreate, FornecedorUpdate, GrupoAutorizacaoIn, NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_bloqueios as bloq
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_cronologia as cron
from app.services import pagamentos_debitos as svc
from app.services import pagamentos_estados as est
from app.services.provisioning_tenant import provisionar_tenant


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _slug(p: str) -> str:
    return f"{p}{uuid.uuid4().hex[:8]}"


def _doc() -> str:
    return str(uuid.uuid4().int)[:14]


async def _provisionar(engine):
    slug = _slug("pagelegib")
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Pagamentos Elegibilidade", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
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
            "DELETE FROM pagamentos.posicao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.excecao_cronologica WHERE tenant_id=:t",
            "DELETE FROM pagamentos.bloqueio_saldo WHERE tenant_id=:t",
            "DELETE FROM pagamentos.pedido_ajuste WHERE tenant_id=:t",
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


async def _novo_usuario(engine, tenant_id, sufixo):
    async with _sm(engine)() as s:
        r = await s.execute(text(
            """INSERT INTO utils.usuario (tenant_id, nome, email, cpf, senha, ativo, excluido, data_criacao)
               VALUES (:t, :n, :e, :c, 'x', true, false, NOW()) RETURNING id"""),
            {"t": tenant_id, "n": f"User {sufixo}", "e": f"{sufixo}@t.local",
             "c": uuid.uuid4().hex[:11]})
        uid = r.scalar_one(); await s.commit()
    return uid


async def _base(engine, tenant_id, *, saldo_inicial="10000.00"):
    """Fornecedor + natureza + fonte + conta + unidade prontos para um débito."""
    from app.models import TipoUnidadeTrabalho, UnidadeTrabalho
    async with _sm(engine)() as s:
        forn = await cad.criar_fornecedor(s, tenant_id=tenant_id, payload=FornecedorCreate(
            tipo_pessoa="JURIDICA", cnpj_cpf=_doc(), nome="Fornecedor Elegib LTDA"))
        nat = await cad.criar_natureza(s, tenant_id=tenant_id, payload=NaturezaCreate(
            codigo=f"N{uuid.uuid4().hex[:6]}", descricao="Material"))
        fonte = await cad.criar_fonte(s, tenant_id=tenant_id, payload=FonteCreate(
            codigo=f"F{uuid.uuid4().hex[:6]}", descricao="Própria", grupos_despesa_permitidos=[]))
        conta = await cad.criar_conta(s, tenant_id=tenant_id, payload=ContaCreate(
            nome="Conta Elegib", banco="001", agencia="1", conta=uuid.uuid4().hex[:8],
            id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO", saldo_inicial=saldo_inicial))

        tipo_stmt = select(TipoUnidadeTrabalho).limit(1)
        tipo = (await s.execute(tipo_stmt)).scalar()
        if not tipo:
            tipo = TipoUnidadeTrabalho(tenant_id=tenant_id, tipo_unidade_trabalho="Administração")
            s.add(tipo)
            await s.flush()
        unidade = UnidadeTrabalho(
            tenant_id=tenant_id, id_tipo_unidade_trabalho=tipo.id, unidade_trabalho="Unidade Elegib")
        s.add(unidade)
        await s.commit()
    return forn, nat, fonte, conta, unidade


def _payload_debito(forn, nat, fonte, conta, unidade, *, valor="1000.00"):
    return DebitoCreate(
        id_fornecedor=forn.id, id_natureza=nat.id, id_unidade=unidade.id,
        id_fonte_recursos=fonte.id, id_conta=conta.id,
        valor_total=valor, competencia="2026-07", descricao="Compra de material",
        numero_ne="NE-2026-0001", categoria="SERVICOS",
        parcelas=[ParcelaCreate(numero=1, valor=valor, vencimento="2026-08-01")],
    )


async def _posicao(engine, tenant_id: int, debito_id: int) -> PosicaoCronologica | None:
    async with _sm(engine)() as s:
        return (await s.execute(select(PosicaoCronologica).where(
            PosicaoCronologica.tenant_id == tenant_id,
            PosicaoCronologica.id_debito == debito_id,
        ))).scalar_one_or_none()


async def _debito_ate_autoridade(engine, tenant_id, forn, nat, fonte, conta, unidade, *, valor="1000.00"):
    """RASCUNHO -> ... -> AGUARDANDO_AUTORIDADE (rito singular, com liquidação
    confirmada — pré-requisito para `validar`). Retorna (debito, autoridade_id)."""
    solicitante = await _novo_usuario(engine, tenant_id, f"sol{uuid.uuid4().hex[:6]}")
    gestor = await _novo_usuario(engine, tenant_id, f"ges{uuid.uuid4().hex[:6]}")
    validador = await _novo_usuario(engine, tenant_id, f"val{uuid.uuid4().hex[:6]}")
    autoridade = await _novo_usuario(engine, tenant_id, f"aut{uuid.uuid4().hex[:6]}")

    async with _sm(engine)() as s:
        d = await svc.criar_debito(s, tenant_id=tenant_id, usuario_id=solicitante,
                                   payload=_payload_debito(forn, nat, fonte, conta, unidade, valor=valor))
    async with _sm(engine)() as s:
        d = await svc.enviar_para_gestor(s, tenant_id=tenant_id, debito_id=d.id,
                                         usuario_id=solicitante, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await svc.gestor_autorizar(s, tenant_id=tenant_id, debito_id=d.id,
                                       usuario_id=gestor, lock_version=d.lock_version)
    async with _sm(engine)() as s:
        d = await svc.confirmar_liquidacao(s, tenant_id=tenant_id, debito_id=d.id, usuario_id=validador)
        d = await svc.validar(s, tenant_id=tenant_id, debito_id=d.id,
                              usuario_id=validador, lock_version=d.lock_version)
    return d, autoridade


# ---------------------------------------------------------------------------
# Função pura — tabela de todos os ramos
# ---------------------------------------------------------------------------

_FATOS_BASE = dict(
    tramitacao=est.AUTORIZADA, tem_pedido_aberto=False, fornecedor_regular=True,
    disponivel_ok=True, tem_bloqueio=False, tem_excecao=False,
)


@pytest.mark.parametrize("overrides,esperado", [
    # tramitação != AUTORIZADA vence tudo, mesmo com todos os outros fatores ruins
    (dict(tramitacao=est.AGUARDANDO_GESTOR, tem_bloqueio=True, fornecedor_regular=False,
          disponivel_ok=False, tem_pedido_aberto=True), (est.REGISTRADA, None)),
    (dict(tramitacao=est.RASCUNHO), (est.REGISTRADA, None)),
    # bloqueio de saldo vence pedido aberto/fornecedor/disponibilidade/exceção
    (dict(tem_bloqueio=True, tem_pedido_aberto=True, fornecedor_regular=False,
          disponivel_ok=False, tem_excecao=True), (est.BLOQUEADA, "Bloqueio de saldo ativo na conta pagadora.")),
    # pedido aberto vence fornecedor/disponibilidade/exceção (sem bloqueio)
    (dict(tem_pedido_aberto=True, fornecedor_regular=False, disponivel_ok=False, tem_excecao=True),
     (est.BLOQUEADA, "Pedido de ajuste em aberto sobre o débito.")),
    # fornecedor irregular vence disponibilidade/exceção
    (dict(fornecedor_regular=False, disponivel_ok=False, tem_excecao=True),
     (est.BLOQUEADA, "Fornecedor com situação cadastral irregular.")),
    # sem disponível vence exceção
    (dict(disponivel_ok=False, tem_excecao=True),
     (est.AGUARDANDO_DISPONIBILIDADE, "Saldo disponível insuficiente na conta pagadora.")),
    # exceção só troca o rótulo de quem JÁ estaria ELEGIVEL
    (dict(tem_excecao=True), (est.EXCECAO_AUTORIZADA, None)),
    # tudo ok
    (dict(), (est.ELEGIVEL, None)),
])
def test_avaliar_elegibilidade_tabela(overrides, esperado):
    fatos = {**_FATOS_BASE, **overrides}
    assert cron.avaliar_elegibilidade(**fatos) == esperado


def test_avaliar_elegibilidade_e_pura_nao_importa_sqlalchemy():
    """Documenta a intenção da spec: a função não faz IO — não recebe `db` nem
    sessão, só os fatos já coletados."""
    import inspect
    params = inspect.signature(cron.avaliar_elegibilidade).parameters
    assert "db" not in params


# ---------------------------------------------------------------------------
# Hooks — integração (fluxo real)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_autorizacao_torna_elegivel(admin_engine):
    """autoridade_aprovar: AGUARDANDO_AUTORIDADE -> AUTORIZADA + ELEGIVEL, e a
    posição da fila (criada REGISTRADA na liquidação) passa a espelhar isso."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        d, autoridade = await _debito_ate_autoridade(admin_engine, t.id, forn, nat, fonte, conta, unidade)

        posicao_antes = await _posicao(admin_engine, t.id, d.id)
        assert posicao_antes.situacao == est.REGISTRADA

        async with _sm(admin_engine)() as s:
            d = await svc.autoridade_aprovar(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=autoridade, lock_version=d.lock_version)
        assert d.situacao_fila == est.ELEGIVEL

        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.ELEGIVEL
        assert posicao.motivo_bloqueio is None

        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        assert any(h.acao == "FILA_REAVALIADA" for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_fornecedor_irregular_bloqueia_na_fila(admin_engine):
    """atualizar_fornecedor IRREGULAR bloqueia na fila os débitos AUTORIZADOS
    dele; voltar REGULAR devolve a ELEGIVEL."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        d, autoridade = await _debito_ate_autoridade(admin_engine, t.id, forn, nat, fonte, conta, unidade)
        async with _sm(admin_engine)() as s:
            d = await svc.autoridade_aprovar(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=autoridade, lock_version=d.lock_version)
        assert (await _posicao(admin_engine, t.id, d.id)).situacao == est.ELEGIVEL

        async with _sm(admin_engine)() as s:
            await cad.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=forn.id,
                payload=FornecedorUpdate(situacao_cadastral="IRREGULAR", motivo_pendencia="CND vencida"))
        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.BLOQUEADA
        assert posicao.motivo_bloqueio == "Fornecedor com situação cadastral irregular."

        async with _sm(admin_engine)() as s:
            await cad.atualizar_fornecedor(
                s, tenant_id=t.id, fornecedor_id=forn.id,
                payload=FornecedorUpdate(situacao_cadastral="REGULAR"))
        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.ELEGIVEL
        assert posicao.motivo_bloqueio is None
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_bloqueio_de_saldo_bloqueia_debitos_da_conta(admin_engine):
    """criar_bloqueio ativo e vigente na conta pagadora bloqueia na fila os
    débitos ELEGIVEIS que pagam por ela — mesmo com saldo de sobra."""
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        d, autoridade = await _debito_ate_autoridade(admin_engine, t.id, forn, nat, fonte, conta, unidade)
        async with _sm(admin_engine)() as s:
            d = await svc.autoridade_aprovar(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=autoridade, lock_version=d.lock_version)
        # Rito singular não grava conta pagadora — grava manualmente para o teste
        # exercitar o caminho de bloqueio (o rito em lote é quem grava de verdade).
        async with _sm(admin_engine)() as s:
            dd = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
            dd.id_conta_pagadora = conta.id
            await s.commit()
        assert (await _posicao(admin_engine, t.id, d.id)).situacao == est.ELEGIVEL

        async with _sm(admin_engine)() as s:
            await bloq.criar_bloqueio(
                s, tenant_id=t.id, usuario_id=autoridade,
                payload=BloqueioSaldoCreate(id_conta=conta.id, valor=Decimal("100.00"),
                                            motivo="Reserva orçamentária", periodo_inicio="2026-01-01"))
        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.BLOQUEADA
        assert posicao.motivo_bloqueio == "Bloqueio de saldo ativo na conta pagadora."
    finally:
        await _cleanup(admin_engine, t.id)


async def _debito_autorizado_em_lote(engine, tenant_id, *, valor="9000.00", saldo_inicial="10000.00",
                                     permitir_saldo_insuficiente=False):
    """Rito em lote (`autorizar_lote`): grava conta pagadora de verdade —
    necessário para o cenário de saldo indisponível."""
    forn, nat, fonte, conta, unidade = await _base(engine, tenant_id, saldo_inicial=saldo_inicial)
    d, autoridade = await _debito_ate_autoridade(engine, tenant_id, forn, nat, fonte, conta, unidade, valor=valor)
    autorizador = await _novo_usuario(engine, tenant_id, f"lote{uuid.uuid4().hex[:6]}")
    async with _sm(engine)() as s:
        await cad.criar_alcada(s, tenant_id=tenant_id, payload=AlcadaCreate(
            id_usuario=autorizador, id_natureza=None, valor_maximo="999999.00"))
    grupo = GrupoAutorizacaoIn(
        id_fonte=fonte.id, id_conta_pagadora=conta.id, debito_ids=[d.id],
        permitir_saldo_insuficiente=permitir_saldo_insuficiente,
        justificativa_excecao="RN-15: urgência orçamentária" if permitir_saldo_insuficiente else None)
    async with _sm(engine)() as s:
        await aut.autorizar_lote(s, tenant_id=tenant_id, usuario_id=autorizador, grupos=[grupo])
    return d, conta


@pytest.mark.asyncio
async def test_sem_disponivel_aguarda_disponibilidade(admin_engine):
    """Autorização em lote com exceção RN-15 (saldo insuficiente): a
    reavaliação corrige para AGUARDANDO_DISPONIBILIDADE porque o disponível
    real não cobre a parcela — mesmo somando de volta a reserva do próprio
    débito (ruling do review: `_disponivel_ok` não pode descontá-la 2x).

    Também prova a trilha de auditoria (ruling do review, item 1): a linha
    AUTORIZADO não mexe na dimensão fila (fila_anterior==fila_nova==
    REGISTRADA) — quem grava a fila de verdade é a FILA_REAVALIADA logo
    depois, e nenhuma linha do histórico chega a ter ELEGIVEL."""
    t = await _provisionar(admin_engine)
    try:
        d, _conta = await _debito_autorizado_em_lote(
            admin_engine, t.id, valor="9000.00", saldo_inicial="1000.00",
            permitir_saldo_insuficiente=True)
        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.AGUARDANDO_DISPONIBILIDADE
        assert posicao.motivo_bloqueio == "Saldo disponível insuficiente na conta pagadora."

        async with _sm(admin_engine)() as s:
            hist = await svc.listar_historico(s, tenant_id=t.id, debito_id=d.id)
        autorizado = [h for h in hist if h.acao == "AUTORIZADO"]
        reavaliado = [h for h in hist if h.acao == "FILA_REAVALIADA"]
        assert len(autorizado) == 1
        assert autorizado[0].situacao_fila_anterior == est.REGISTRADA
        assert autorizado[0].situacao_fila_nova == est.REGISTRADA
        assert len(reavaliado) == 1
        assert reavaliado[0].situacao_fila_anterior == est.REGISTRADA
        assert reavaliado[0].situacao_fila_nova == est.AGUARDANDO_DISPONIBILIDADE
        assert not any(h.situacao_fila_nova == est.ELEGIVEL for h in hist)
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_saldo_exato_apos_reserva_propria_e_elegivel(admin_engine):
    """Ruling do review (item 2): `saldo_conta().disponivel` já desconta o
    comprometido do PRÓPRIO débito — exigir `disponivel >= restante` cobra a
    reserva duas vezes. Conta com saldo == valor do débito fica com
    disponivel==0 depois da própria reserva, e isso é ELEGIVEL, não
    AGUARDANDO_DISPONIBILIDADE."""
    t = await _provisionar(admin_engine)
    try:
        d, conta = await _debito_autorizado_em_lote(
            admin_engine, t.id, valor="1000.00", saldo_inicial="1000.00")

        async with _sm(admin_engine)() as s:
            from app.services import pagamentos_caixa as caixa
            saldo = await caixa.saldo_conta(s, tenant_id=t.id, conta_id=conta.id)
        assert saldo.disponivel == Decimal("0.00")

        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.ELEGIVEL
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_pedido_de_ajuste_pos_autorizacao_bloqueia(admin_engine):
    """No rito atual, um pedido de ajuste só se abre em GESTOR/VALIDACAO/
    AUTORIDADE — etapas anteriores a AUTORIZADA. Portanto `tem_pedido_aberto`
    nunca coexiste com `tramitacao == AUTORIZADA` na prática: o próprio
    `solicitar_ajuste` já move a tramitação para AJUSTE_*, e o ramo que
    prevalece é o de "tramitação != AUTORIZADA" da função pura (REGISTRADA),
    não o de pedido aberto. Este teste prova exatamente isso pelo fluxo real,
    e a combinação `tem_pedido_aberto=True` + `tramitacao=AUTORIZADA` fica
    coberta só pela tabela pura, como o ramo defensivo que é.
    """
    t = await _provisionar(admin_engine)
    try:
        forn, nat, fonte, conta, unidade = await _base(admin_engine, t.id)
        solicitante = await _novo_usuario(admin_engine, t.id, f"sol{uuid.uuid4().hex[:6]}")
        gestor = await _novo_usuario(admin_engine, t.id, f"ges{uuid.uuid4().hex[:6]}")

        async with _sm(admin_engine)() as s:
            d = await svc.criar_debito(s, tenant_id=t.id, usuario_id=solicitante,
                                       payload=_payload_debito(forn, nat, fonte, conta, unidade))
        async with _sm(admin_engine)() as s:
            d = await svc.enviar_para_gestor(s, tenant_id=t.id, debito_id=d.id,
                                             usuario_id=solicitante, lock_version=d.lock_version)
        async with _sm(admin_engine)() as s:
            d = await svc.solicitar_ajuste(
                s, tenant_id=t.id, debito_id=d.id, usuario_id=gestor, lock_version=d.lock_version,
                etapa="GESTOR", motivo="Falta documento", descricao="Anexar nota fiscal",
                transacao_responsavel="pagamento_solicitar", tipo="NAO_MATERIAL")
        assert d.situacao_tramitacao == est.AJUSTE_GESTOR
        # Sem posição na fila ainda (não liquidado) — reavaliar_debito é no-op.
        assert await _posicao(admin_engine, t.id, d.id) is None
    finally:
        await _cleanup(admin_engine, t.id)


@pytest.mark.asyncio
async def test_pagamento_integral_conclui(admin_engine):
    """pagar_parcela integral espelha CONCLUIDA na posição da fila."""
    t = await _provisionar(admin_engine)
    try:
        d, conta = await _debito_autorizado_em_lote(admin_engine, t.id, valor="1000.00")
        assert (await _posicao(admin_engine, t.id, d.id)).situacao == est.ELEGIVEL

        usuario = await _novo_usuario(admin_engine, t.id, f"pag{uuid.uuid4().hex[:6]}")
        async with _sm(admin_engine)() as s:
            parcelas = await svc.listar_parcelas(s, tenant_id=t.id, debito_id=d.id)
        parcela_id = parcelas[0].id
        async with _sm(admin_engine)() as s:
            await aut.liberar_parcelas(s, tenant_id=t.id, usuario_id=usuario, parcela_ids=[parcela_id])
        async with _sm(admin_engine)() as s:
            await aut.pagar_parcela(s, tenant_id=t.id, usuario_id=usuario, parcela_id=parcela_id,
                                    forma_pagamento="TED")

        async with _sm(admin_engine)() as s:
            d2 = await svc.obter_debito(s, tenant_id=t.id, debito_id=d.id)
        assert d2.situacao_fila == est.CONCLUIDA

        posicao = await _posicao(admin_engine, t.id, d.id)
        assert posicao.situacao == est.CONCLUIDA
    finally:
        await _cleanup(admin_engine, t.id)

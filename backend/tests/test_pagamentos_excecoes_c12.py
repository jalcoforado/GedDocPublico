"""Pagamentos Onda C — fatia C1.2: relatório de exceções.

Cada regra é provada nos dois sentidos: um registro que a dispara e um que
NÃO, no mesmo tenant. Um relatório de exceção que acusa tudo é tão inútil
quanto um que não acusa nada.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas.pagamentos import (
    ContaCreate, DebitoCreate, FonteCreate, FornecedorCreate, MovimentacaoCreate,
    NaturezaCreate, ParcelaCreate,
)
from app.services import pagamentos_caixa as caixa_svc
from app.services import pagamentos_cadastros as cad_svc
from app.services import pagamentos_debitos as deb_svc
from app.services import pagamentos_excecoes as exc_svc
from app.services.provisioning_tenant import provisionar_tenant
from tests.fixtures.pagamentos import id_unidade_padrao


def _sm(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _regra(rel: dict, codigo: str) -> dict:
    return next(r for r in rel["regras"] if r["codigo"] == codigo)


async def _base(engine):
    """Tenant com catálogo mínimo e dois fornecedores: um regular, um irregular."""
    slug = f"exc12-{uuid.uuid4().hex[:8]}"
    async with _sm(engine)() as s:
        tenant, _ = await provisionar_tenant(
            s, slug=slug, nome="Pref Exceções", admin_email=f"{slug}@t.local",
            admin_nome="Adm", admin_cpf=uuid.uuid4().hex[:11], plano="basico",
        )
    tid = tenant.id
    async with _sm(engine)() as db:
        usuario_id = (
            await db.execute(text("SELECT id FROM utils.usuario WHERE tenant_id=:t LIMIT 1"),
                             {"t": tid})
        ).scalar_one()
        nat = await cad_svc.criar_natureza(
            db, tenant_id=tid, payload=NaturezaCreate(codigo="E-3390", descricao="Consumo"))
        fonte = await cad_svc.criar_fonte(
            db, tenant_id=tid,
            payload=FonteCreate(codigo="E-1500", descricao="Ordinários",
                                grupos_despesa_permitidos=["CUSTEIO"]))
        conta = await cad_svc.criar_conta(
            db, tenant_id=tid,
            payload=ContaCreate(nome="Conta Exc", banco="BB", agencia="1", conta="1",
                                id_fonte_recursos=fonte.id, grupo_despesa="CUSTEIO",
                                saldo_inicial=Decimal("1000.00"),
                                saldo_minimo_alerta=Decimal("100.00")))
        regular = await cad_svc.criar_fornecedor(
            db, tenant_id=tid,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf="10.000.000/0001-01",
                                     nome="Fornecedor Regular"))
        irregular = await cad_svc.criar_fornecedor(
            db, tenant_id=tid,
            payload=FornecedorCreate(tipo_pessoa="JURIDICA", cnpj_cpf="10.000.000/0001-02",
                                     nome="Fornecedor Irregular",
                                     situacao_cadastral="IRREGULAR",
                                     motivo_pendencia="CADIN"))
    return tid, usuario_id, nat.id, fonte.id, conta.id, regular.id, irregular.id


async def _cria_debito(engine, tid, usuario_id, *, nat, fonte, conta, forn,
                       descricao, urgente=False, justificativa_urgencia=None):
    hoje = date.today()
    async with _sm(engine)() as db:
        unidade_id = await id_unidade_padrao(db, tid)
        return await deb_svc.criar_debito(
            db, tenant_id=tid, usuario_id=usuario_id,
            payload=DebitoCreate(
                id_fornecedor=forn, id_natureza=nat, id_fonte_recursos=fonte,
                id_unidade=unidade_id,
                id_conta=conta, valor_total=Decimal("100.00"),
                competencia=f"{hoje.year:04d}-{hoje.month:02d}", descricao=descricao,
                urgente=urgente, justificativa_urgencia=justificativa_urgencia,
                parcelas=[ParcelaCreate(numero=1, valor=Decimal("100.00"),
                                        vencimento=hoje + timedelta(days=10))]),
        )


@pytest.mark.asyncio
async def test_urgente_sem_justificativa_discrimina(admin_engine):
    """Dispara só para o urgente SEM justificativa."""
    tid, uid, nat, fonte, conta, reg, _irr = await _base(admin_engine)
    d_sem = await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta,
                               forn=reg, descricao="Urgente sem motivo", urgente=True)
    await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta, forn=reg,
                       descricao="Urgente justificado", urgente=True,
                       justificativa_urgencia="Risco de desabastecimento")
    await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta, forn=reg,
                       descricao="Comum", urgente=False)

    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid)

    r = _regra(rel, "URGENTE_SEM_JUSTIFICATIVA")
    assert r["total"] == 1
    assert r["itens"][0]["id_debito"] == d_sem.id


@pytest.mark.asyncio
async def test_fornecedor_irregular_so_conta_debito_em_andamento(admin_engine):
    """RASCUNHO não é despesa em andamento — não deve poluir o relatório."""
    tid, uid, nat, fonte, conta, reg, irr = await _base(admin_engine)
    # Fica em RASCUNHO: não conta.
    await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta,
                       forn=irr, descricao="Rascunho com irregular")

    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid)
    assert _regra(rel, "FORNECEDOR_IRREGULAR")["total"] == 0

    # Empurra para EM_VALIDACAO: passa a contar.
    d = await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta,
                           forn=irr, descricao="Em curso com irregular")
    async with _sm(admin_engine)() as db:
        await deb_svc.enviar_para_gestor(
            db, tenant_id=tid, debito_id=d.id, usuario_id=uid,
            lock_version=d.lock_version)
    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid)

    r = _regra(rel, "FORNECEDOR_IRREGULAR")
    assert r["total"] == 1
    assert r["itens"][0]["fornecedor"] == "Fornecedor Irregular"
    assert r["itens"][0]["situacao"] == "IRREGULAR"


@pytest.mark.asyncio
async def test_conta_abaixo_do_minimo(admin_engine):
    """A conta nasce com 1000 e mínimo 100; só entra no relatório após a saída."""
    tid, uid, _nat, _fonte, conta, _reg, _irr = await _base(admin_engine)

    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid)
    assert _regra(rel, "CONTA_ABAIXO_MINIMO")["total"] == 0

    async with _sm(admin_engine)() as db:
        await caixa_svc.lancar_movimentacao(
            db, tenant_id=tid, usuario_id=uid,
            payload=MovimentacaoCreate(id_conta=conta, tipo="SAIDA",
                                       valor=Decimal("950.00"), origem="AJUSTE",
                                       data=date.today(), descricao="Sangria"))
    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid)

    r = _regra(rel, "CONTA_ABAIXO_MINIMO")
    assert r["total"] == 1
    assert Decimal(r["itens"][0]["saldo"]) == Decimal("50.00")


@pytest.mark.asyncio
async def test_limite_corta_a_lista_mas_nao_o_total(admin_engine):
    """Truncar sem informar transformaria '2 exceções' em conclusão falsa."""
    tid, uid, nat, fonte, conta, reg, _irr = await _base(admin_engine)
    for i in range(3):
        await _cria_debito(admin_engine, tid, uid, nat=nat, fonte=fonte, conta=conta,
                           forn=reg, descricao=f"Urgente {i}", urgente=True)

    async with _sm(admin_engine)() as db:
        rel = await exc_svc.relatorio_excecoes(db, tenant_id=tid, limite_por_regra=2)

    r = _regra(rel, "URGENTE_SEM_JUSTIFICATIVA")
    assert r["total"] == 3, "o total tem de refletir a realidade"
    assert r["exibindo"] == 2
    assert len(r["itens"]) == 2


@pytest.mark.asyncio
async def test_nao_vaza_entre_tenants(admin_engine):
    """Exceção de um município não pode aparecer no relatório de outro."""
    tid_a, uid_a, nat, fonte, conta, reg, _irr = await _base(admin_engine)
    tid_b, *_ = await _base(admin_engine)

    await _cria_debito(admin_engine, tid_a, uid_a, nat=nat, fonte=fonte, conta=conta,
                       forn=reg, descricao="Urgente do tenant A", urgente=True)

    async with _sm(admin_engine)() as db:
        rel_a = await exc_svc.relatorio_excecoes(db, tenant_id=tid_a)
        rel_b = await exc_svc.relatorio_excecoes(db, tenant_id=tid_b)

    assert _regra(rel_a, "URGENTE_SEM_JUSTIFICATIVA")["total"] == 1
    assert _regra(rel_b, "URGENTE_SEM_JUSTIFICATIVA")["total"] == 0
    assert rel_b["total_excecoes"] == 0


@pytest.mark.asyncio
async def test_marcador_rn15_casa_com_o_que_a_autorizacao_grava(admin_engine):
    """Guarda da dívida conhecida: a regra depende de LIKE sobre texto livre.

    Se alguém mudar a frase em `autorizar_lote` sem mudar `MARCADOR_RN15`, a
    exceção mais sensível do rito passa a não ser detectada — silenciosamente.
    """
    import inspect

    from app.services import pagamentos_autorizacao as aut

    fonte_codigo = inspect.getsource(aut.autorizar_lote)
    assert exc_svc.MARCADOR_RN15 in fonte_codigo, (
        "o marcador da RN-15 divergiu de `autorizar_lote` — o relatório de "
        "exceções pararia de detectar autorização com saldo insuficiente"
    )

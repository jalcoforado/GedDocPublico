"""F4 — guardas entre o caminho em LOTE e o pagamento AVULSO.

O lote não muda `Parcela.status`: a parcela fica `LIBERADA` do RASCUNHO até o
retorno do banco, e só `LotePagamentoParcela.situacao` sabe que ela está num
lote. Sem as guardas abaixo, uma parcela já enviada ao banco podia ser paga
também pelo `POST /pagamentos/parcelas/{id}/pagar` avulso, e o retorno do lote
lançava uma SEGUNDA `MovimentacaoConta` SAIDA — saldo descontado em dobro por
um único pagamento real.

E a segregação de funções que `enviar_lote` passou a exigir valia só para o
lote: o avulso, com a mesma permissão `pagamento_pagar`, executava o mesmo
pagamento sem checar quem decidiu o débito.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text

from app.models import MovimentacaoConta, Parcela
from app.schemas.pagamentos import NaturezaCreate, RetornoParcelaIn
from app.services import pagamentos_autorizacao as aut
from app.services import pagamentos_cadastros as cad
from app.services import pagamentos_lotes as lot
from tests.fixtures.pagamentos import id_unidade_padrao
from tests.test_pagamentos_f4_lote import (
    _criar_usuario,
    _debito_liberado,
    _fonte_conta,
    _fornecedor2,
    _lote_ate_enviado,
    _lote_de_um,
    _provisionar,
    _sm,
)
from tests.test_pagamentos_f4_retencao import _post, _usuario_com


async def _saidas_da_parcela(engine, parcela_id: int) -> int:
    async with _sm(engine)() as s:
        return (await s.execute(select(func.count()).select_from(MovimentacaoConta).where(
            MovimentacaoConta.id_parcela == parcela_id,
            MovimentacaoConta.tipo == "SAIDA"))).scalar_one()


async def _pagar_avulso(engine, tenant_id: int, usuario_id: int, parcela_id: int):
    async with _sm(engine)() as s:
        return await aut.pagar_parcela(s, tenant_id=tenant_id, usuario_id=usuario_id,
                                       parcela_id=parcela_id, forma_pagamento="PIX",
                                       data_pagamento=date.today())


@pytest.mark.asyncio
@pytest.mark.parametrize("etapa", ["RASCUNHO", "ENVIADO"])
async def test_avulso_recusa_parcela_em_lote_ativo(admin_engine, etapa):
    tenant, _sol = await _provisionar(admin_engine)
    if etapa == "RASCUNHO":
        _lote, _d, p1, _conta = await _lote_de_um(admin_engine, tenant.id)
    else:
        _lote, _d, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
    tesoureiro = await _criar_usuario(admin_engine, tenant.id, "Tesoureiro Neutro")

    with pytest.raises(HTTPException) as e:
        await _pagar_avulso(admin_engine, tenant.id, tesoureiro, p1)
    assert e.value.status_code == 409
    assert "lote" in e.value.detail
    assert await _saidas_da_parcela(admin_engine, p1) == 0


@pytest.mark.asyncio
async def test_avulso_volta_a_valer_depois_que_o_lote_falha(admin_engine):
    """Retorno FALHOU devolve a parcela à elegibilidade (continua LIBERADA): o
    vínculo morto não pode bloquear o pagamento avulso para sempre."""
    tenant, _sol = await _provisionar(admin_engine)
    lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
    async with _sm(admin_engine)() as s:
        await lot.processar_retorno(
            s, tenant_id=tenant.id, lote_id=lote.id,
            retornos=[RetornoParcelaIn(parcela_id=p1, resultado="FALHOU",
                                       motivo_falha="conta do favorecido encerrada")],
            usuario_id=d1.id_usuario_solicitante)
    tesoureiro = await _criar_usuario(admin_engine, tenant.id, "Tesoureiro Neutro")

    p = await _pagar_avulso(admin_engine, tenant.id, tesoureiro, p1)
    assert p.status == "PAGA"
    assert await _saidas_da_parcela(admin_engine, p1) == 1


@pytest.mark.asyncio
async def test_retorno_recusa_parcela_que_nao_esta_mais_liberada(admin_engine):
    """Rede de segurança do lado do lote: se a parcela deixou de estar LIBERADA
    por qualquer caminho, o retorno não lança outra SAIDA."""
    tenant, _sol = await _provisionar(admin_engine)
    lote, d1, p1, _conta = await _lote_ate_enviado(admin_engine, tenant.id)
    async with _sm(admin_engine)() as s:
        await s.execute(text("UPDATE pagamentos.parcela SET status = 'PAGA' WHERE id = :id"),
                        {"id": p1})
        await s.commit()

    async with _sm(admin_engine)() as s:
        with pytest.raises(HTTPException) as e:
            await lot.processar_retorno(
                s, tenant_id=tenant.id, lote_id=lote.id,
                retornos=[RetornoParcelaIn(parcela_id=p1, resultado="PAGA")],
                usuario_id=d1.id_usuario_solicitante)
    assert e.value.status_code == 409
    assert await _saidas_da_parcela(admin_engine, p1) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("papel", ["id_usuario_solicitante", "id_gestor_decisor", "id_validador"])
async def test_avulso_respeita_segregacao_de_funcoes(admin_engine, papel):
    tenant, _sol = await _provisionar(admin_engine)
    async with _sm(admin_engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
            codigo=f"NS{papel[-6:]}", descricao="Material"))
    async with _sm(admin_engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant.id)
    fonte, conta = await _fonte_conta(admin_engine, tenant.id)
    forn = await _fornecedor2(admin_engine, tenant.id, nome="Forn Segregacao")
    d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn, nat=nat,
                                    fonte=fonte, conta=conta, unidade_id=unidade_id)

    with pytest.raises(HTTPException) as e:
        await _pagar_avulso(admin_engine, tenant.id, getattr(d1, papel), p1)
    assert e.value.status_code == 403
    assert await _saidas_da_parcela(admin_engine, p1) == 0

    neutro = await _criar_usuario(admin_engine, tenant.id, "Tesoureiro Neutro")
    p = await _pagar_avulso(admin_engine, tenant.id, neutro, p1)
    assert p.status == "PAGA"


@pytest.mark.asyncio
async def test_http_usuario_comum_opera_lote_e_segregacao_chega_como_403(admin_engine):
    """A suíte chama o service direto; aqui a cadeia real do FastAPI — gate de
    permissão para usuário NÃO super-usuário, serialização dos *Out e o 403 de
    segregação — roda de ponta a ponta."""
    tenant, _sol = await _provisionar(admin_engine)
    async with _sm(admin_engine)() as s:
        nat = await cad.criar_natureza(s, tenant_id=tenant.id, payload=NaturezaCreate(
            codigo="NHTTP1", descricao="Material"))
    async with _sm(admin_engine)() as s:
        unidade_id = await id_unidade_padrao(s, tenant.id)
    fonte, conta = await _fonte_conta(admin_engine, tenant.id)
    forn = await _fornecedor2(admin_engine, tenant.id, nome="Forn HTTP")
    d1, p1 = await _debito_liberado(admin_engine, tenant.id, forn=forn, nat=nat,
                                    fonte=fonte, conta=conta, unidade_id=unidade_id)
    tesoureiro = await _usuario_com(admin_engine, tenant.id, ["pagamento_pagar"])
    sem_permissao = await _usuario_com(admin_engine, tenant.id, [])

    r = await _post(admin_engine, tenant.id, tenant.slug, sem_permissao, "/api/v2/pagamentos/lotes",
                    {"id_conta_pagadora": conta.id, "parcela_ids": [p1]})
    assert r.status_code == 403, r.text[:300]

    r = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro, "/api/v2/pagamentos/lotes",
                    {"id_conta_pagadora": conta.id, "parcela_ids": [p1]})
    assert r.status_code == 201, r.text[:300]
    lote_id = r.json()["id"]

    r = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro,
                    f"/api/v2/pagamentos/lotes/{lote_id}/programar",
                    {"data_programada": date.today().isoformat()})
    assert r.status_code == 200, r.text[:300]

    # quem decidiu o débito como gestor não pode enviar, mesmo tendo a permissão
    async with _sm(admin_engine)() as s:
        await s.execute(text(
            "INSERT INTO utils.usuario_grupo (tenant_id, id_usuario, id_grupo, ativo, excluido, app) "
            "SELECT tenant_id, :g, id_grupo, true, false, app FROM utils.usuario_grupo "
            "WHERE id_usuario = :t"), {"g": d1.id_gestor_decisor, "t": tesoureiro})
        await s.commit()
    r = await _post(admin_engine, tenant.id, tenant.slug, d1.id_gestor_decisor,
                    f"/api/v2/pagamentos/lotes/{lote_id}/enviar", {})
    assert r.status_code == 403, r.text[:300]

    r = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro,
                    f"/api/v2/pagamentos/lotes/{lote_id}/enviar", {})
    assert r.status_code == 200, r.text[:300]

    # parcela já no banco: o avulso via HTTP é recusado
    r = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro,
                    f"/api/v2/pagamentos/parcelas/{p1}/pagar", {"forma_pagamento": "PIX"})
    assert r.status_code == 409, r.text[:300]

    r = await _post(admin_engine, tenant.id, tenant.slug, tesoureiro,
                    f"/api/v2/pagamentos/lotes/{lote_id}/retorno",
                    {"retornos": [{"parcela_id": p1, "resultado": "PAGA"}]})
    assert r.status_code == 200, r.text[:300]
    assert await _saidas_da_parcela(admin_engine, p1) == 1
    async with _sm(admin_engine)() as s:
        assert (await s.execute(select(Parcela.status).where(Parcela.id == p1))).scalar_one() == "PAGA"

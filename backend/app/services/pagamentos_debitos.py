"""Débitos de Pagamentos (R2) — CRUD de rascunho e transições de workflow.
Transições SÓ por aqui; cada uma grava debito_historico na MESMA transação."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Debito, DebitoHistorico, Fornecedor, Parcela, Usuario
from ..schemas.pagamentos import DebitoCreate, DebitoUpdate
from . import audit
from . import pagamentos_ajustes as ajustes
from . import pagamentos_cadastros as cad
from . import pagamentos_estados as est
from . import pagamentos_guardas as grd
from . import pagamentos_versionamento as pv


def _utcnow() -> datetime:
    return datetime.utcnow()


class PagamentoDebitoError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


def _validar_parcelas(parcelas, valor_total: Decimal) -> None:
    numeros = sorted(p.numero for p in parcelas)
    if numeros != list(range(1, len(parcelas) + 1)):
        raise PagamentoDebitoError("Parcelas devem ser numeradas 1..N sem repetição.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)


async def _validar_refs(db, *, tenant_id: int, payload) -> None:
    await cad.obter_fornecedor(db, tenant_id=tenant_id, fornecedor_id=payload.id_fornecedor)
    await cad.obter_natureza(db, tenant_id=tenant_id, natureza_id=payload.id_natureza)
    await cad.obter_fonte(db, tenant_id=tenant_id, fonte_id=payload.id_fonte_recursos)
    # Conta é apenas uma sugestão (não-vinculante); se informada, deve ser da mesma fonte.
    if payload.id_conta is not None:
        conta = await cad.obter_conta(db, tenant_id=tenant_id, conta_id=payload.id_conta)
        if conta.id_fonte_recursos != payload.id_fonte_recursos:
            raise PagamentoDebitoError(
                "Conta sugerida não pertence à fonte de recursos informada.",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    if payload.id_contrato is not None:
        await cad.obter_contrato(db, tenant_id=tenant_id, contrato_id=payload.id_contrato)
    await cad.obter_unidade(db, tenant_id=tenant_id, unidade_id=payload.id_unidade)


def _sincronizar_status_legado(d: Debito) -> None:
    """Recalcula `Debito.status` a partir das três dimensões.

    Ponto ÚNICO de escrita da coluna legada. Havendo dois, eles divergem — é
    exatamente o risco registrado na spec §4.2, e a mitigação é este ser o
    único. Nenhum outro lugar do código pode atribuir a `d.status`.
    """
    d.status = est.status_legado(
        d.situacao_tramitacao, d.situacao_fila, d.situacao_pagamento)


def _registrar_transicao(db, *, debito: Debito, acao: str, usuario_id: int | None,
                         tramitacao: str | None = None, fila: str | None = None,
                         pagamento: str | None = None,
                         justificativa: str | None = None,
                         ip: str | None = None) -> None:
    """Aplica a mudança nas dimensões informadas, deriva o status legado e grava
    a trilha — tudo na MESMA transação do caller.

    Passar `tramitacao` exige que a transição seja legal no grafo. As outras
    duas dimensões não têm grafo nesta fatia: a fila é responsabilidade da F3 e
    a execução, da F4.
    """
    if tramitacao is not None and tramitacao != debito.situacao_tramitacao:
        if not est.transicao_permitida(debito.situacao_tramitacao, tramitacao):
            raise PagamentoDebitoError(
                f"Transição inválida: de '{debito.situacao_tramitacao}' "
                f"não se vai para '{tramitacao}'.", status.HTTP_409_CONFLICT)
    status_anterior = debito.status
    situacao_tramitacao_anterior = debito.situacao_tramitacao
    situacao_fila_anterior = debito.situacao_fila
    situacao_pagamento_anterior = debito.situacao_pagamento
    if tramitacao is not None:
        debito.situacao_tramitacao = tramitacao
    if fila is not None:
        debito.situacao_fila = fila
    if pagamento is not None:
        debito.situacao_pagamento = pagamento
    _sincronizar_status_legado(debito)
    debito.lock_version = (debito.lock_version or 0) + 1
    db.add(DebitoHistorico(
        tenant_id=debito.tenant_id, id_debito=debito.id,
        status_anterior=status_anterior if acao != "CRIADO" else None,
        status_novo=debito.status, acao=acao, justificativa=justificativa,
        id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow(),
        versao_debito=debito.versao,
        situacao_tramitacao_anterior=situacao_tramitacao_anterior,
        situacao_tramitacao_nova=debito.situacao_tramitacao,
        situacao_fila_anterior=situacao_fila_anterior,
        situacao_fila_nova=debito.situacao_fila,
        situacao_pagamento_anterior=situacao_pagamento_anterior,
        situacao_pagamento_nova=debito.situacao_pagamento))


async def detectar_duplicidade(db, *, tenant_id: int, id_fornecedor: int, numero_nf: str | None,
                               numero_ne: str | None, valor_total, competencia: str,
                               id_contrato: int | None = None,
                               excluir_id: int | None = None) -> list[int]:
    """IDs de débitos ativos com mesmo credor+NF+empenho+contrato+valor+competência
    (RF-SOL-09). Só considera quando há nota fiscal (numero_nf) — o documento que
    caracteriza a despesa. Ignora débitos já REJEITADO/CANCELADO."""
    if not numero_nf:
        return []
    stmt = select(Debito.id).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.id_fornecedor == id_fornecedor, Debito.numero_nf == numero_nf,
        Debito.valor_total == valor_total, Debito.competencia == competencia,
        Debito.status.notin_(("REJEITADO", "CANCELADO")))
    if numero_ne:
        stmt = stmt.where(Debito.numero_ne == numero_ne)
    if id_contrato is not None:
        stmt = stmt.where(Debito.id_contrato == id_contrato)
    if excluir_id is not None:
        stmt = stmt.where(Debito.id != excluir_id)
    return list((await db.execute(stmt)).scalars().all())


async def criar_debito(db: AsyncSession, *, tenant_id: int, usuario_id: int,
                       payload: DebitoCreate) -> Debito:
    await _validar_refs(db, tenant_id=tenant_id, payload=payload)
    _validar_parcelas(payload.parcelas, payload.valor_total)
    dups = await detectar_duplicidade(
        db, tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor, numero_nf=payload.numero_nf,
        numero_ne=payload.numero_ne, valor_total=payload.valor_total, competencia=payload.competencia,
        id_contrato=payload.id_contrato)
    if dups:
        raise PagamentoDebitoError(
            f"Possível duplicidade: já existe(m) débito(s) {dups} com mesmo credor, NF, "
            f"empenho, contrato, valor e competência.", status.HTTP_409_CONFLICT)
    d = Debito(tenant_id=tenant_id, id_fornecedor=payload.id_fornecedor,
               id_natureza=payload.id_natureza, id_fonte_recursos=payload.id_fonte_recursos,
               id_conta=payload.id_conta, id_contrato=payload.id_contrato,
               valor_total=payload.valor_total,
               competencia=payload.competencia, numero_ne=payload.numero_ne,
               numero_nf=payload.numero_nf, criticidade=payload.criticidade,
               urgente=payload.urgente, justificativa_urgencia=payload.justificativa_urgencia,
               descricao=payload.descricao,
               situacao_tramitacao=est.RASCUNHO, situacao_fila=est.NAO_REGISTRADA,
               situacao_pagamento=est.NAO_INICIADA, status="RASCUNHO",
               id_unidade=payload.id_unidade,
               id_usuario_solicitante=usuario_id, criado_em=_utcnow())
    db.add(d); await db.flush()
    for p in payload.parcelas:
        db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                       valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    _registrar_transicao(db, debito=d, acao="CRIADO", usuario_id=usuario_id)
    await db.commit(); await db.refresh(d)
    return d


async def obter_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                       for_update: bool = False) -> Debito:
    stmt = select(Debito).where(Debito.id == debito_id,
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False))
    if for_update:
        stmt = stmt.with_for_update()
    d = (await db.execute(stmt)).scalar_one_or_none()
    if d is None:
        raise PagamentoDebitoError("Débito não encontrado", status.HTTP_404_NOT_FOUND)
    return d


async def listar_debitos(db: AsyncSession, *, tenant_id: int, status_f: str | None = None,
                         tramitacao_f: str | None = None,
                         solicitante_id: int | None = None, id_fonte: int | None = None,
                         id_natureza: int | None = None, id_fornecedor: int | None = None,
                         id_contrato: int | None = None, urgente: bool | None = None,
                         competencia: str | None = None) -> list[Debito]:
    """Lista débitos com filtros do painel (RF-PNL-02): fonte, categoria (natureza),
    credor, contrato, status, urgência e competência."""
    stmt = select(Debito).where(Debito.tenant_id == tenant_id, Debito.excluido.is_(False))
    if status_f:
        stmt = stmt.where(Debito.status == status_f)
    if tramitacao_f:
        stmt = stmt.where(Debito.situacao_tramitacao == tramitacao_f)
    if solicitante_id is not None:
        stmt = stmt.where(Debito.id_usuario_solicitante == solicitante_id)
    if id_fonte is not None:
        stmt = stmt.where(Debito.id_fonte_recursos == id_fonte)
    if id_natureza is not None:
        stmt = stmt.where(Debito.id_natureza == id_natureza)
    if id_fornecedor is not None:
        stmt = stmt.where(Debito.id_fornecedor == id_fornecedor)
    if id_contrato is not None:
        stmt = stmt.where(Debito.id_contrato == id_contrato)
    if urgente is not None:
        stmt = stmt.where(Debito.urgente.is_(urgente))
    if competencia:
        stmt = stmt.where(Debito.competencia == competencia)
    return list((await db.execute(stmt.order_by(Debito.id.desc()))).scalars().all())


async def listar_parcelas(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[Parcela]:
    return list((await db.execute(select(Parcela).where(
        Parcela.tenant_id == tenant_id, Parcela.id_debito == debito_id,
        Parcela.excluido.is_(False)).order_by(Parcela.numero))).scalars().all())


async def listar_historico(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[DebitoHistorico]:
    return list((await db.execute(select(DebitoHistorico).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id)
        .order_by(DebitoHistorico.criado_em.desc(), DebitoHistorico.id.desc()))).scalars().all())


async def listar_versoes(db: AsyncSession, *, tenant_id: int, debito_id: int):
    """Versões congeladas do débito — `GET /debitos/{id}/versoes` (F2)."""
    return await pv.listar_versoes(db, tenant_id=tenant_id, debito_id=debito_id)


async def atualizar_debito(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, payload: DebitoUpdate) -> Debito:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.situacao_tramitacao not in (
        est.RASCUNHO, est.AJUSTE_GESTOR, est.AJUSTE_VALIDACAO, est.AJUSTE_AUTORIDADE,
    ):
        raise PagamentoDebitoError(
            "Só é possível editar débitos em rascunho ou em ajuste.",
            status.HTTP_409_CONFLICT)
    dados = payload.model_dump(exclude_unset=True)
    parcelas_novas = dados.pop("parcelas", None)
    valor_total = dados.get("valor_total", d.valor_total)
    if parcelas_novas is not None:
        _validar_parcelas(payload.parcelas, valor_total)
    elif "valor_total" in dados:
        atuais = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
        soma = sum((p.valor for p in atuais), Decimal("0"))
        if soma != valor_total:
            raise PagamentoDebitoError(
                f"Soma das parcelas ({soma}) difere do novo valor total ({valor_total}).",
                status.HTTP_422_UNPROCESSABLE_ENTITY)
    # valida refs alteradas
    class _Ref:  # payload efetivo para _validar_refs
        id_fornecedor = dados.get("id_fornecedor", d.id_fornecedor)
        id_natureza = dados.get("id_natureza", d.id_natureza)
        id_fonte_recursos = dados.get("id_fonte_recursos", d.id_fonte_recursos)
        id_conta = dados.get("id_conta", d.id_conta)
        id_contrato = dados.get("id_contrato", d.id_contrato)
        id_unidade = dados.get("id_unidade", d.id_unidade)
    await _validar_refs(db, tenant_id=tenant_id, payload=_Ref)
    if d.situacao_tramitacao != est.RASCUNHO:
        alterados = pv.campos_materiais_alterados(d, dados)
        if alterados:
            campos = ", ".join(sorted(alterados))
            await pv.congelar_versao(
                db, debito=d, motivo=f"Alteração material: {campos}",
                usuario_id=usuario_id)
            await audit.log(
                db, tenant_id=tenant_id, id_usuario=usuario_id,
                acao="debito.versao_criada", entidade="debito", id_entidade=d.id,
                payload={"campos_alterados": sorted(alterados), "versao": d.versao})
    for k, v in dados.items():
        setattr(d, k, v)
    if parcelas_novas is not None:
        for p in await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id):
            p.excluido = True; p.atualizado_em = _utcnow()
        for p in payload.parcelas:
            db.add(Parcela(tenant_id=tenant_id, id_debito=d.id, numero=p.numero,
                           valor=p.valor, vencimento=p.vencimento, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def excluir_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> None:
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    if d.status not in ("RASCUNHO", "REJEITADO", "CANCELADO"):
        raise PagamentoDebitoError("Só é possível excluir rascunhos/rejeitados/cancelados.",
                                   status.HTTP_409_CONFLICT)
    d.excluido = True; d.atualizado_em = _utcnow(); await db.commit()


async def nomes_fornecedores(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Fornecedor.id, Fornecedor.nome).where(
        Fornecedor.tenant_id == tenant_id, Fornecedor.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def nomes_usuarios(db: AsyncSession, *, tenant_id: int, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = (await db.execute(select(Usuario.id, Usuario.nome).where(
        Usuario.tenant_id == tenant_id, Usuario.id.in_(ids)))).all()
    return {r[0]: r[1] for r in rows}


async def validadores_do_debito(db: AsyncSession, *, tenant_id: int, debito_id: int) -> set[int]:
    """Usuários que VALIDARAM o débito — não podem autorizá-lo (RF-SEG-01)."""
    rows = (await db.execute(select(DebitoHistorico.id_usuario).where(
        DebitoHistorico.tenant_id == tenant_id, DebitoHistorico.id_debito == debito_id,
        DebitoHistorico.acao == "VALIDADO"))).scalars().all()
    return {r for r in rows if r is not None}


# ---- Máquina de estados do pedido — Especificação v2.0 seção 13 (16 status) ----
ST_RASCUNHO = "RASCUNHO"
ST_EM_VALIDACAO = "EM_VALIDACAO"
ST_DEVOLVIDO = "DEVOLVIDO"
ST_VALIDADO = "VALIDADO"
ST_ENVIADO_SECRETARIO = "ENVIADO_SECRETARIO"
ST_AGUARDANDO_AUTORIZACAO = "AGUARDANDO_AUTORIZACAO"
ST_AUTORIZADO = "AUTORIZADO"
ST_ENVIADO_TESOURARIA = "ENVIADO_TESOURARIA"
ST_EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
ST_PAGO = "PAGO"
ST_PAGO_PARCIAL = "PAGO_PARCIAL"
ST_CONCILIADO = "CONCILIADO"
ST_REJEITADO = "REJEITADO"
ST_SUSPENSO = "SUSPENSO"
ST_CANCELADO = "CANCELADO"
ST_ESTORNADO = "ESTORNADO"

EDITAVEIS = (ST_RASCUNHO, ST_DEVOLVIDO)                      # pedido pode ser editado
AUTORIZAVEIS = (ST_ENVIADO_SECRETARIO, ST_AGUARDANDO_AUTORIZACAO)  # fila da autoridade
EM_TESOURARIA = (ST_ENVIADO_TESOURARIA, ST_EM_PROCESSAMENTO, ST_PAGO_PARCIAL)  # execução
# Débitos cuja autorização mantém valor RESERVADO na conta pagadora (inclui
# ESTORNADO: a autorização/OP permanece; basta re-liberar para repagar).
COM_RESERVA = (ST_AUTORIZADO, *EM_TESOURARIA, ST_ESTORNADO)


def _exigir_status(d: Debito, *esperados: str) -> None:
    if d.status not in esperados:
        raise PagamentoDebitoError(
            f"Transição inválida: débito está '{d.status}' (esperado: {', '.join(esperados)}).",
            status.HTTP_409_CONFLICT)


_ETAPA_DO_AJUSTE = {
    "GESTOR": est.AJUSTE_GESTOR,
    "VALIDACAO": est.AJUSTE_VALIDACAO,
    "AUTORIDADE": est.AJUSTE_AUTORIDADE,
}
# Para onde volta depois de respondido. Nesta fatia o retorno é sempre à etapa
# que pediu — a regra de "alteração material volta ao gestor" chega na F2, junto
# com o versionamento que sabe distinguir material de não material.
_RETORNO_DO_AJUSTE = {
    est.AJUSTE_GESTOR: est.AGUARDANDO_GESTOR,
    est.AJUSTE_VALIDACAO: est.AGUARDANDO_VALIDACAO,
    est.AJUSTE_AUTORIDADE: est.AGUARDANDO_AUTORIDADE,
}


async def _carregar_para_decisao(db, *, tenant_id: int, debito_id: int,
                                 lock_version: int) -> Debito:
    """Carrega com lock de linha e confere a versão otimista.

    O `for_update` é o que impede duas decisões concorrentes de lerem o mesmo
    `lock_version` e passarem as duas pela conferência.
    """
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id, for_update=True)
    grd.assert_lock_version(d, esperado=lock_version)
    return d


async def enviar_para_gestor(db: AsyncSession, *, tenant_id: int, debito_id: int,
                             usuario_id: int, lock_version: int,
                             ip: str | None = None) -> Debito:
    """Unidade setorial envia a solicitação ao gestor da pasta.

    Sucede `enviar_validacao`, que mandava direto para a conferência documental
    — pulando o juízo de mérito, que é do gestor.
    """
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.RASCUNHO:
        raise PagamentoDebitoError(
            f"Só se envia ao gestor uma solicitação em rascunho "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    parcelas = await listar_parcelas(db, tenant_id=tenant_id, debito_id=d.id)
    if not parcelas:
        raise PagamentoDebitoError("Débito sem parcelas.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    soma = sum((p.valor for p in parcelas), Decimal("0"))
    if soma != d.valor_total:
        raise PagamentoDebitoError(
            f"Soma das parcelas ({soma}) difere do valor total ({d.valor_total}).",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    _registrar_transicao(db, debito=d, acao="ENVIADO", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_GESTOR, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def gestor_autorizar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int,
                           ip: str | None = None) -> Debito:
    """Gestor da pasta autoriza o mérito e a conveniência da despesa."""
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_GESTOR:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando o gestor "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="GERIR")
    d.id_gestor_decisor = usuario_id
    _registrar_transicao(db, debito=d, acao="AUTORIZADO_GESTOR", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_VALIDACAO, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def gestor_rejeitar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                          usuario_id: int, lock_version: int, justificativa: str,
                          ip: str | None = None) -> Debito:
    """Gestor rejeita a despesa. Encerra o processo; a decisão fica no histórico."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("A rejeição exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_GESTOR:
        raise PagamentoDebitoError(
            f"Só o gestor rejeita, e só enquanto a solicitação o aguarda "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="GERIR")
    d.id_gestor_decisor = usuario_id
    _registrar_transicao(db, debito=d, acao="REJEITADO_GESTOR", usuario_id=usuario_id,
                         tramitacao=est.REJEITADA_GESTOR, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def solicitar_ajuste(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int, etapa: str,
                           motivo: str, descricao: str, transacao_responsavel: str,
                           tipo: str, prazo: date | None = None,
                           campos_relacionados: list[str] | None = None,
                           ip: str | None = None) -> Debito:
    """Devolve para correção, a partir de qualquer das três etapas decisórias.

    F2: além da transição de estado, abre um `PedidoAjuste` estruturado — com
    responsável (`transacao_responsavel`), materialidade (`tipo`) e prazo —
    que é o que a unidade vê e responde. `motivo` dobra também como a
    justificativa gravada no histórico da transição.
    """
    destino = _ETAPA_DO_AJUSTE.get(etapa)
    if destino is None:
        raise PagamentoDebitoError(f"Etapa desconhecida: '{etapa}'.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    origem_por_etapa = {
        "GESTOR": est.AGUARDANDO_GESTOR,
        "VALIDACAO": est.AGUARDANDO_VALIDACAO,
        "AUTORIDADE": est.AGUARDANDO_AUTORIDADE,
    }
    origem = origem_por_etapa[etapa]
    if d.situacao_tramitacao != origem:
        raise PagamentoDebitoError(
            f"A etapa '{etapa}' não é a responsável atual por esta solicitação "
            f"(ela está em '{d.situacao_tramitacao}').",
            status.HTTP_409_CONFLICT,
        )
    ato_por_etapa = {
        "GESTOR": "GERIR",
        "VALIDACAO": "VALIDAR",
        "AUTORIDADE": "AUTORIZAR",
    }
    grd.assert_segregacao(d, usuario_id=usuario_id, ato=ato_por_etapa[etapa])
    motivo_limpo = (motivo or "").strip()
    if not motivo_limpo:
        raise PagamentoDebitoError(
            "O pedido de ajuste exige que se diga o que precisa ser corrigido.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    _registrar_transicao(db, debito=d, acao="AJUSTE_SOLICITADO", usuario_id=usuario_id,
                         tramitacao=destino, justificativa=motivo_limpo, ip=ip)
    pedido = await ajustes.criar_pedido(
        db, tenant_id=tenant_id, debito=d, usuario_id=usuario_id, etapa=etapa,
        motivo=motivo_limpo, descricao=descricao, transacao_responsavel=transacao_responsavel,
        tipo=tipo, prazo=prazo, campos_relacionados=campos_relacionados)
    await audit.log(
        db, tenant_id=tenant_id, id_usuario=usuario_id,
        acao="debito.ajuste_solicitado", entidade="debito", id_entidade=d.id,
        payload={"pedido_ajuste_id": pedido.id, "etapa": etapa,
                 "transacao_responsavel": transacao_responsavel, "tipo": tipo})
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def responder_ajuste(db: AsyncSession, *, tenant_id: int, debito_id: int,
                           usuario_id: int, lock_version: int,
                           ip: str | None = None) -> Debito:
    """Unidade reenvia após responder o(s) pedido(s) de ajuste pendente(s).

    Reenvio (F2, §4.3): exige que TODOS os pedidos `ABERTO` da etapa tenham
    sido respondidos ou cancelados — 409 caso contrário. O destino depende da
    materialidade (Ruling 3, revisado no review final): se, desde a abertura
    do mais antigo pedido AINDA NÃO RESOLVIDO desta rodada — RESPONDIDO ou
    CANCELADO, não só RESPONDIDO —, o débito ganhou versão nova
    (`d.versao > menor versao_debito da rodada`), as aprovações de gestor e
    validador são invalidadas e o débito volta ao GESTOR, não à etapa que
    pediu o ajuste — reabrir o mérito depois de mudar algo material é o ponto
    central da fatia. Considerar também os CANCELADOS fecha a fuga em que a
    validação cancela e reabre o pedido pós-edição: um pedido novo, nascido já
    na versão editada, não pode "esquecer" que a edição aconteceu. Sem
    alteração material, o retorno é o de sempre: à etapa que abriu o ajuste
    (`_RETORNO_DO_AJUSTE`).
    """
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    etapa = ajustes.ETAPA_POR_SITUACAO.get(d.situacao_tramitacao)
    if etapa is None:
        raise PagamentoDebitoError(
            f"Esta solicitação não tem ajuste pendente "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    abertos = await ajustes.pedidos_pendentes_da_etapa(
        db, tenant_id=tenant_id, debito_id=debito_id, etapa=etapa)
    if abertos:
        lista = "; ".join(f"#{p.id}: {p.motivo}" for p in abertos)
        raise PagamentoDebitoError(
            f"Há pedido(s) de ajuste ainda não respondido(s): {lista}.",
            status.HTTP_409_CONFLICT)
    todos = await ajustes.listar_pedidos(db, tenant_id=tenant_id, debito_id=debito_id)
    respondidos = [p for p in todos
                   if p.etapa_solicitante == etapa and p.situacao == "RESPONDIDO"]
    # Materialidade (Ruling do review final): comparar `d.versao` só contra os
    # RESPONDIDO deixa escapar o caso em que o pedido que testemunhou a edição
    # foi CANCELADO e substituído por outro, nascido já na versão pós-edição —
    # o `min` do pedido novo "esquece" a versão antiga e material vira False
    # incorretamente. A correção usa os pedidos da etapa desta RODADA, isto é,
    # com `situacao != 'RESOLVIDO'`: como `abertos` já foi conferido vazio
    # acima, o que sobra é exatamente RESPONDIDO + CANCELADO. `RESOLVIDO` só é
    # atribuído aqui embaixo, ao final desta própria função — nunca em nenhum
    # outro ponto do código —, então pedidos RESOLVIDOS pertencem sempre a uma
    # passagem ANTERIOR por esta etapa (já fechada por um reenvio passado) e
    # ficam de fora, não reativando materialidade antiga.
    rodada_atual = [p for p in todos
                    if p.etapa_solicitante == etapa and p.situacao != "RESOLVIDO"]
    material = bool(rodada_atual) and d.versao > min(p.versao_debito for p in rodada_atual)
    destino = est.AGUARDANDO_GESTOR if material else _RETORNO_DO_AJUSTE[d.situacao_tramitacao]
    if material:
        d.id_gestor_decisor = None
        d.id_validador = None
        # Linha de histórico própria — NÃO é uma transição do grafo (a
        # tramitação não muda aqui; a mudança de tramitação é a de
        # `_registrar_transicao` logo abaixo). INSERT direto de propósito.
        db.add(DebitoHistorico(
            tenant_id=tenant_id, id_debito=d.id,
            status_anterior=d.status, status_novo=d.status,
            acao="APROVACOES_INVALIDADAS",
            justificativa=f"Aprovações de gestor e validador invalidadas pela versão {d.versao}.",
            id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow(),
            versao_debito=d.versao,
            situacao_tramitacao_anterior=d.situacao_tramitacao,
            situacao_tramitacao_nova=d.situacao_tramitacao))
        await audit.log(
            db, tenant_id=tenant_id, id_usuario=usuario_id,
            acao="debito.aprovacoes_invalidadas", entidade="debito", id_entidade=d.id,
            payload={"versao": d.versao})
    _registrar_transicao(db, debito=d, acao="REENVIADO", usuario_id=usuario_id,
                         tramitacao=destino, ip=ip)
    agora = _utcnow()
    for p in respondidos:
        p.situacao = "RESOLVIDO"
        p.resolvido_em = agora
    d.atualizado_em = agora; await db.commit(); await db.refresh(d)
    return d


async def validar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                  usuario_id: int, lock_version: int,
                  ip: str | None = None) -> Debito:
    """Validador da Secretaria de Finanças aprova a conformidade documental e financeira.

    Não rejeita — só aprova ou devolve para ajuste via `solicitar_ajuste`.
    A rejeição é prerrogativa do Gestor (antes) e da Autoridade (depois).

    AGUARDANDO_VALIDACAO → AGUARDANDO_AUTORIDADE."""
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_VALIDACAO:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando a validação financeira "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    if not d.liquidacao_confirmada:
        raise PagamentoDebitoError(
            "A liquidação deve ser confirmada antes da validação financeira.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    from . import pagamentos_checklist as checklist
    pendentes = await checklist.checklist_pendente(
        db, tenant_id=tenant_id, debito_id=debito_id)
    if pendentes:
        raise PagamentoDebitoError(
            "Checklist obrigatório pendente: " + "; ".join(pendentes),
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="VALIDAR")
    d.id_validador = usuario_id
    _registrar_transicao(db, debito=d, acao="VALIDADO", usuario_id=usuario_id,
                         tramitacao=est.AGUARDANDO_AUTORIDADE, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def autoridade_aprovar(db: AsyncSession, *, tenant_id: int, debito_id: int,
                             usuario_id: int, lock_version: int,
                             ip: str | None = None) -> Debito:
    """Autoridade competente aprova a despesa; segue para o pagador.

    AGUARDANDO_AUTORIDADE → AUTORIZADA + ELEGIVEL."""
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_AUTORIDADE:
        raise PagamentoDebitoError(
            f"Esta solicitação não está aguardando autorização "
            f"(está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="AUTORIZAR")
    _registrar_transicao(db, debito=d, acao="AUTORIZADO", usuario_id=usuario_id,
                         tramitacao=est.AUTORIZADA, fila=est.ELEGIVEL, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def autoridade_indeferir(db: AsyncSession, *, tenant_id: int, debito_id: int,
                               usuario_id: int, lock_version: int, justificativa: str,
                               ip: str | None = None) -> Debito:
    """Autoridade rejeita a despesa. Encerra o processo.

    AGUARDANDO_AUTORIDADE → INDEFERIDA_AUTORIDADE."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("A indeferição exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao != est.AGUARDANDO_AUTORIDADE:
        raise PagamentoDebitoError(
            f"Só a autoridade indeferir, e só enquanto a solicitação a aguarda "
            f"(esta está em '{d.situacao_tramitacao}').", status.HTTP_409_CONFLICT)
    grd.assert_segregacao(d, usuario_id=usuario_id, ato="AUTORIZAR")
    _registrar_transicao(db, debito=d, acao="INDEFERIDO", usuario_id=usuario_id,
                         tramitacao=est.INDEFERIDA_AUTORIDADE, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def cancelar(db: AsyncSession, *, tenant_id: int, debito_id: int, usuario_id: int,
                   lock_version: int, justificativa: str,
                   ip: str | None = None) -> Debito:
    """Cancela a solicitação de qualquer etapa não-terminal. Encerra o processo.

    É um porto seguro para quando a solicitação não pode prosseguir — erro de entrada,
    despesa já paga por outro caminho, mudança de política, etc."""
    justificativa = (justificativa or "").strip()
    if not justificativa:
        raise PagamentoDebitoError("O cancelamento exige justificativa.",
                                   status.HTTP_422_UNPROCESSABLE_ENTITY)
    d = await _carregar_para_decisao(db, tenant_id=tenant_id, debito_id=debito_id,
                                     lock_version=lock_version)
    if d.situacao_tramitacao in est.TERMINAIS or d.situacao_tramitacao == est.AUTORIZADA:
        raise PagamentoDebitoError(
            f"Solicitação já encerrada ou autorizada ('{d.situacao_tramitacao}'); "
            "não pode ser cancelada.",
            status.HTTP_409_CONFLICT)
    _registrar_transicao(db, debito=d, acao="CANCELADO", usuario_id=usuario_id,
                         tramitacao=est.CANCELADA, justificativa=justificativa, ip=ip)
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


async def confirmar_liquidacao(db: AsyncSession, *, tenant_id: int, debito_id: int,
                               usuario_id: int, data_liquidacao=None, ip: str | None = None) -> Debito:
    """Confirma a liquidação (recebimento/atesto) — pré-requisito para validar/autorizar
    (RF-VAL-02/RN-01). Permitido nas etapas pré-validação; não muda o status."""
    d = await obter_debito(db, tenant_id=tenant_id, debito_id=debito_id)
    _exigir_status(d, ST_RASCUNHO, ST_DEVOLVIDO, ST_EM_VALIDACAO, ST_VALIDADO)
    d.liquidacao_confirmada = True
    d.data_liquidacao = data_liquidacao or _utcnow().date()
    db.add(DebitoHistorico(tenant_id=tenant_id, id_debito=d.id, status_anterior=d.status,
                           status_novo=d.status, acao="LIQUIDADO",
                           justificativa=f"Liquidação em {d.data_liquidacao.isoformat()}",
                           id_usuario=usuario_id, ip_origem=ip, criado_em=_utcnow()))
    d.atualizado_em = _utcnow(); await db.commit(); await db.refresh(d)
    return d


def debito_out(d: Debito, *, nome_fornecedor: str) -> dict:
    return {
        "id": d.id, "id_fornecedor": d.id_fornecedor, "nome_fornecedor": nome_fornecedor,
        "id_natureza": d.id_natureza, "id_fonte_recursos": d.id_fonte_recursos,
        "id_conta": d.id_conta, "id_conta_pagadora": d.id_conta_pagadora,
        "id_contrato": d.id_contrato,
        "valor_total": d.valor_total, "competencia": d.competencia,
        "numero_ne": d.numero_ne, "numero_nf": d.numero_nf, "criticidade": d.criticidade,
        "urgente": d.urgente, "justificativa_urgencia": d.justificativa_urgencia,
        "descricao": d.descricao, "status": d.status,
        "situacao_tramitacao": d.situacao_tramitacao,
        "situacao_fila": d.situacao_fila,
        "situacao_pagamento": d.situacao_pagamento,
        "id_unidade": d.id_unidade, "versao": d.versao,
        "lock_version": d.lock_version,
        "id_gestor_decisor": d.id_gestor_decisor, "id_validador": d.id_validador,
        "id_usuario_solicitante": d.id_usuario_solicitante,
        "liquidacao_confirmada": d.liquidacao_confirmada, "data_liquidacao": d.data_liquidacao,
        "criado_em": d.criado_em, "atualizado_em": d.atualizado_em,
    }

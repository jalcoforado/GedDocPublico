"""Pedido de ajuste como entidade (F2, migration 0105).

Até a F1 o "ajuste" era só uma transição de estado (`AJUSTE_*`) mais uma
justificativa solta no histórico. Esta fatia dá ao pedido vida própria:
`PedidoAjuste` sabe quem pediu, o que pediu (motivo curto + descrição livre),
qual transação vai responder, se é material, prazo e campos relacionados —
e tem seu próprio ciclo `ABERTO -> RESPONDIDO/CANCELADO`.

Regra central (Ruling 2 da spec F2): um pedido `RESPONDIDO` não impede que a
mesma etapa abra outro pedido sobre o mesmo débito — só o `ABERTO` bloqueia
reenvio. Por isso `pedidos_pendentes_da_etapa` filtra por `situacao == ABERTO`,
nunca por "existe algum pedido".
"""
from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..cli.seed_bootstrap import MODULO_TRANSACOES
from ..database import tenant_filter
from ..models import Debito
from ..models.pagamentos import PedidoAjuste
from . import pagamentos_estados as est

TRANSACOES_PAGAMENTOS: frozenset[str] = frozenset(MODULO_TRANSACOES["pagamentos"])

# Etapa que abriu o pedido -> transação de tramitação do débito enquanto ele
# está pendente. Espelha `_ETAPA_DO_AJUSTE` de `pagamentos_debitos.py`; vive
# aqui também porque Task 4/7 consultam por essa chave.
ETAPA_POR_SITUACAO: dict[str, str] = {
    est.AJUSTE_GESTOR: "GESTOR",
    est.AJUSTE_VALIDACAO: "VALIDACAO",
    est.AJUSTE_AUTORIDADE: "AUTORIDADE",
}

TIPOS_VALIDOS = frozenset({"MATERIAL", "NAO_MATERIAL"})


def _utcnow() -> datetime:
    return datetime.utcnow()


class PedidoAjusteError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=code, detail=detail)


async def criar_pedido(db: AsyncSession, *, tenant_id: int, debito: Debito, usuario_id: int,
                       etapa: str, motivo: str, descricao: str, transacao_responsavel: str,
                       tipo: str, prazo: date | None = None,
                       campos_relacionados: list[str] | None = None) -> PedidoAjuste:
    """Cria o pedido em `ABERTO`. NÃO comita — participa da transação do caller
    (`solicitar_ajuste`/o endpoint de pedido adicional)."""
    if transacao_responsavel not in TRANSACOES_PAGAMENTOS:
        raise PedidoAjusteError(
            f"Transação responsável desconhecida: '{transacao_responsavel}'.",
            status.HTTP_422_UNPROCESSABLE_ENTITY)
    if tipo not in TIPOS_VALIDOS:
        raise PedidoAjusteError(f"Tipo desconhecido: '{tipo}'.",
                                status.HTTP_422_UNPROCESSABLE_ENTITY)
    motivo = (motivo or "").strip()
    if not motivo:
        raise PedidoAjusteError("O pedido de ajuste exige um motivo.",
                                status.HTTP_422_UNPROCESSABLE_ENTITY)
    descricao = (descricao or "").strip()
    if not descricao:
        raise PedidoAjusteError("O pedido de ajuste exige uma descrição.",
                                status.HTTP_422_UNPROCESSABLE_ENTITY)
    pedido = PedidoAjuste(
        tenant_id=tenant_id, id_debito=debito.id, versao_debito=debito.versao,
        etapa_solicitante=etapa, id_usuario_solicitante=usuario_id,
        motivo=motivo, descricao=descricao, transacao_responsavel=transacao_responsavel,
        tipo=tipo, prazo=prazo, campos_relacionados=campos_relacionados,
        situacao="ABERTO", criado_em=_utcnow(),
    )
    db.add(pedido)
    await db.flush()
    return pedido


async def listar_pedidos(db: AsyncSession, *, tenant_id: int, debito_id: int) -> list[PedidoAjuste]:
    stmt = select(PedidoAjuste).where(
        PedidoAjuste.tenant_id == tenant_id, PedidoAjuste.id_debito == debito_id,
    ).order_by(PedidoAjuste.criado_em.desc(), PedidoAjuste.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def obter_pedido(db: AsyncSession, *, tenant_id: int, debito_id: int,
                       pedido_id: int) -> PedidoAjuste:
    stmt = select(PedidoAjuste).where(
        PedidoAjuste.id == pedido_id, PedidoAjuste.tenant_id == tenant_id,
        PedidoAjuste.id_debito == debito_id,
    )
    p = (await db.execute(stmt)).scalar_one_or_none()
    if p is None:
        raise PedidoAjusteError("Pedido de ajuste não encontrado", status.HTTP_404_NOT_FOUND)
    return p


async def pedidos_pendentes_da_etapa(db: AsyncSession, *, tenant_id: int, debito_id: int,
                                     etapa: str) -> list[PedidoAjuste]:
    """Pedidos `ABERTO` da etapa informada sobre este débito.

    `RESPONDIDO` não conta como pendente (Ruling 2) — é o que permite reenvio
    de um novo pedido pela mesma etapa sem que o anterior, já respondido,
    bloqueie. Cobre também os pedidos SINTÉTICOS do backfill da 0105: eles
    nascem `ABERTO` com `etapa_solicitante` correta, então caem aqui igual a
    um pedido criado pelo fluxo novo.
    """
    stmt = select(PedidoAjuste).where(
        PedidoAjuste.tenant_id == tenant_id, PedidoAjuste.id_debito == debito_id,
        PedidoAjuste.etapa_solicitante == etapa, PedidoAjuste.situacao == "ABERTO",
    ).order_by(PedidoAjuste.criado_em.desc(), PedidoAjuste.id.desc())
    return list((await db.execute(stmt)).scalars().all())


async def responder_pedido(db: AsyncSession, *, tenant_id: int, debito_id: int, pedido_id: int,
                           usuario_id: int, resposta: str) -> PedidoAjuste:
    resposta = (resposta or "").strip()
    if not resposta:
        raise PedidoAjusteError("A resposta ao pedido de ajuste não pode ser vazia.",
                                status.HTTP_422_UNPROCESSABLE_ENTITY)
    p = await obter_pedido(db, tenant_id=tenant_id, debito_id=debito_id, pedido_id=pedido_id)
    if p.situacao != "ABERTO":
        raise PedidoAjusteError(
            f"Pedido já está '{p.situacao}'; só pedido ABERTO pode ser respondido.",
            status.HTTP_409_CONFLICT)
    p.situacao = "RESPONDIDO"
    p.resposta = resposta
    p.id_usuario_resposta = usuario_id
    p.respondido_em = _utcnow()
    await db.flush()
    return p


async def pendencias_do_usuario(db: AsyncSession, *, tenant_id: int,
                                transacoes: frozenset[str] | set[str]) -> list[tuple[PedidoAjuste, str]]:
    """Pedidos `ABERTO` cuja `transacao_responsavel` está entre as transações
    do usuário (F2, Task 6 — `GET /pagamentos/minha-fila`).

    Devolve pares `(pedido, descricao_debito)`: a descrição vem de `Debito`
    via join, não de `PedidoAjuste` — o pedido não guarda a descrição do
    débito, só o motivo/descrição do próprio ajuste. `Debito.excluido` é
    conferido para não expor pendência de um débito que já foi excluído.
    """
    if not transacoes:
        return []
    stmt = tenant_filter(
        select(PedidoAjuste, Debito.descricao).join(
            Debito, Debito.id == PedidoAjuste.id_debito,
        ).where(
            PedidoAjuste.situacao == "ABERTO",
            PedidoAjuste.transacao_responsavel.in_(transacoes),
            Debito.excluido.is_(False),
        ).order_by(PedidoAjuste.criado_em.desc(), PedidoAjuste.id.desc()),
        PedidoAjuste, tenant_id,
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


async def cancelar_pedido(db: AsyncSession, *, tenant_id: int, debito_id: int, pedido_id: int,
                          usuario_id: int) -> PedidoAjuste:
    p = await obter_pedido(db, tenant_id=tenant_id, debito_id=debito_id, pedido_id=pedido_id)
    if p.situacao != "ABERTO":
        raise PedidoAjusteError(
            f"Pedido já está '{p.situacao}'; só pedido ABERTO pode ser cancelado.",
            status.HTTP_409_CONFLICT)
    p.situacao = "CANCELADO"
    p.resolvido_em = _utcnow()
    await db.flush()
    return p

"""Trail do processo — sequência de unidades visitadas.

Útil pra UI mostrar "por onde passou" como uma faixa horizontal de cards
ligados por setas, ou como mini-organograma destacando os nodos.

Saída: lista de passos ordenados cronologicamente. Cada passo:
- ordem: 0..N
- id_unidade: int
- unidade_nome: str
- unidade_sigla: str | None
- tipo: "abertura" | "encaminhamento"
- data: datetime ISO
- recebido_em: datetime ISO | None (None = pendente OU é abertura)
- cancelado: bool
- atual: bool (último passo NÃO cancelado é o "atual")
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Encaminhamento, Processo, UnidadeTrabalho


async def trail(
    db: AsyncSession, *, processo_id: int, tenant_id: int
) -> list[dict[str, Any]]:
    proc = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if proc is None:
        return []

    # Encaminhamentos do processo ordenados por id (proxy de tempo já que
    # data_hora_movimentacao vive em Movimentacao — id basta).
    encs = (
        await db.execute(
            select(Encaminhamento)
            .where(
                Encaminhamento.id_processo == processo_id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.excluido.is_(False),
            )
            .order_by(Encaminhamento.id)
        )
    ).scalars().all()

    # Coleta ids únicos de unidade pra um único query de nomes
    uids: set[int] = {proc.id_unidade_proprietaria}
    for e in encs:
        if e.id_unidade_origem is not None:
            uids.add(e.id_unidade_origem)
        uids.add(e.id_unidade_destino)
    unid_rows = (
        await db.execute(
            select(UnidadeTrabalho.id, UnidadeTrabalho.unidade_trabalho, UnidadeTrabalho.sigla)
            .where(UnidadeTrabalho.id.in_(uids))
        )
    ).all()
    unidade_por_id: dict[int, dict[str, Any]] = {
        uid: {"nome": nome, "sigla": sigla} for uid, nome, sigla in unid_rows
    }

    def _info(uid: int) -> tuple[str, str | None]:
        info = unidade_por_id.get(uid)
        if info is None:
            return f"#{uid}", None
        return info["nome"], info["sigla"]

    passos: list[dict[str, Any]] = []

    # Passo 0 = abertura na unidade proprietária
    nome_p, sigla_p = _info(proc.id_unidade_proprietaria)
    passos.append(
        {
            "ordem": 0,
            "id_unidade": proc.id_unidade_proprietaria,
            "unidade_nome": nome_p,
            "unidade_sigla": sigla_p,
            "tipo": "abertura",
            "data": proc.data_hora_abertura.isoformat(),
            "recebido_em": proc.data_hora_abertura.isoformat(),
            "cancelado": False,
            "atual": False,
        }
    )

    # Cada encaminhamento vira um passo no destino
    for i, e in enumerate(encs, start=1):
        nome, sigla = _info(e.id_unidade_destino)
        passos.append(
            {
                "ordem": i,
                "id_unidade": e.id_unidade_destino,
                "unidade_nome": nome,
                "unidade_sigla": sigla,
                "tipo": "encaminhamento",
                "data": e.data_hora_recebimento.isoformat()
                if e.data_hora_recebimento
                else None,
                "recebido_em": e.data_hora_recebimento.isoformat()
                if e.data_hora_recebimento
                else None,
                "cancelado": bool(e.cancelado),
                "atual": False,
            }
        )

    # Marca o último passo NÃO-cancelado como atual
    for p in reversed(passos):
        if not p["cancelado"]:
            p["atual"] = True
            break

    return passos

"""Favoritos e marcadores de processo (F5, benchmark SUiTE).

Os dois são toggles: favoritar/desfavoritar e definir marcadores não geram
entrada em `processo_trail` nem `audit_log` — não são atos do processo, são
preferência de organização pessoal (favorito) ou classificação (marcador),
no mesmo espírito de `atribuir_responsavel` registrar no histórico só a
DESIGNAÇÃO, nunca a navegação.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Marcador, Processo, ProcessoFavorito, ProcessoMarcador


class MarcadorError(Exception):
    pass


async def _processo_existe(db: AsyncSession, processo_id: int, tenant_id: int) -> bool:
    return (
        await db.execute(
            select(Processo.id).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none() is not None


async def favoritar(db: AsyncSession, processo_id: int, *, tenant_id: int, usuario_id: int) -> None:
    """Sem-op silencioso quando o processo não existe (ou é de outro tenant):
    `require_acesso_processo` só cobre sigilo, não existência — é o
    `get_processo_detail(...) is None -> 404` do router, chamado logo depois,
    quem resolve o "não existe". Levantar erro aqui viraria 500 (o INSERT bate
    na FK) ou um 400 que mentiria sobre a causa."""
    if not await _processo_existe(db, processo_id, tenant_id):
        return
    existe = (
        await db.execute(
            select(ProcessoFavorito.id).where(
                ProcessoFavorito.tenant_id == tenant_id,
                ProcessoFavorito.id_usuario == usuario_id,
                ProcessoFavorito.id_processo == processo_id,
            )
        )
    ).scalar_one_or_none()
    if existe is not None:
        return  # idempotente
    db.add(
        ProcessoFavorito(
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            id_processo=processo_id,
            criado_em=datetime.now(),
        )
    )
    await db.commit()


async def desfavoritar(db: AsyncSession, processo_id: int, *, tenant_id: int, usuario_id: int) -> None:
    await db.execute(
        delete(ProcessoFavorito).where(
            ProcessoFavorito.tenant_id == tenant_id,
            ProcessoFavorito.id_usuario == usuario_id,
            ProcessoFavorito.id_processo == processo_id,
        )
    )
    await db.commit()


async def definir_marcadores(
    db: AsyncSession,
    processo_id: int,
    *,
    tenant_id: int,
    ids_marcador: list[int],
    usuario_id: int | None,
) -> None:
    """Substitui o conjunto inteiro pelo informado (idempotente: mandar o
    mesmo conjunto duas vezes deixa o banco no mesmo estado).

    Sem-op silencioso quando o processo não existe: mesmo raciocínio de
    `favoritar` — o 404 é responsabilidade do `get_processo_detail(...) is
    None` no router, chamado logo depois. `MarcadorError` fica reservado para
    o que É 400 de verdade: marcador inválido no conjunto pedido.
    """
    if not await _processo_existe(db, processo_id, tenant_id):
        return

    if ids_marcador:
        validos = (
            await db.execute(
                select(Marcador.id).where(
                    Marcador.id.in_(ids_marcador),
                    Marcador.tenant_id == tenant_id,
                    Marcador.excluido.is_(False),
                )
            )
        ).scalars().all()
        invalidos = set(ids_marcador) - set(validos)
        if invalidos:
            raise MarcadorError(f"Marcador(es) inexistente(s) no tenant: {sorted(invalidos)}")

    await db.execute(
        delete(ProcessoMarcador).where(
            ProcessoMarcador.tenant_id == tenant_id,
            ProcessoMarcador.id_processo == processo_id,
        )
    )
    for id_marcador in ids_marcador:
        db.add(
            ProcessoMarcador(
                tenant_id=tenant_id,
                id_processo=processo_id,
                id_marcador=id_marcador,
                id_usuario=usuario_id,
                criado_em=datetime.now(),
            )
        )
    await db.commit()

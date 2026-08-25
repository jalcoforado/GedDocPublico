"""Gestão de sistemas integrados M2M (C2.3) — realm admin (permissão dos
cadastros de pagamentos), não confundir com o realm M2M em si
(`auth/sistema_integrado.py`), que autentica a CHAMADA de um sistema externo.

O segredo só existe em claro no instante de `criar_sistema` — devolvido UMA
vez no schema de resposta e nunca mais recuperável (nem por quem administra):
só o bcrypt fica gravado."""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..models import SistemaIntegrado
from ..schemas.pagamentos import SistemaIntegradoCreate

PREFIXO_TAMANHO = 8  # + "apy_" = 12 chars, cabe em varchar(12)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _gerar_prefixo() -> str:
    return "apy_" + uuid.uuid4().hex[:PREFIXO_TAMANHO]


def _gerar_segredo() -> str:
    return secrets.token_urlsafe(32)


async def criar_sistema(
    db: AsyncSession, *, tenant_id: int, payload: SistemaIntegradoCreate, usuario_id: int
) -> tuple[SistemaIntegrado, str]:
    """Cria a credencial e devolve `(linha, chave_completa)`. `chave_completa`
    (`<prefixo>.<segredo>`) só existe aqui — nunca é reconstruível depois."""
    segredo = _gerar_segredo()
    prefixo = _gerar_prefixo()
    sistema = SistemaIntegrado(
        tenant_id=tenant_id,
        nome=payload.nome,
        prefixo=prefixo,
        hash_chave=hash_password(segredo),
        escopo_leitura=payload.escopo_leitura,
        escopo_escrita=payload.escopo_escrita,
        ativo=True,
        criado_em=_utcnow(),
        id_usuario_criador=usuario_id,
    )
    db.add(sistema)
    await db.commit()
    await db.refresh(sistema)
    return sistema, f"{prefixo}.{segredo}"


async def listar_sistemas(db: AsyncSession, *, tenant_id: int) -> list[SistemaIntegrado]:
    stmt = (
        select(SistemaIntegrado)
        .where(SistemaIntegrado.tenant_id == tenant_id)
        .order_by(SistemaIntegrado.criado_em.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def obter_sistema(db: AsyncSession, *, tenant_id: int, sistema_id: int) -> SistemaIntegrado:
    stmt = select(SistemaIntegrado).where(
        SistemaIntegrado.id == sistema_id, SistemaIntegrado.tenant_id == tenant_id
    )
    sistema = (await db.execute(stmt)).scalar_one_or_none()
    if sistema is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sistema integrado não encontrado")
    return sistema


async def revogar_sistema(db: AsyncSession, *, tenant_id: int, sistema_id: int) -> SistemaIntegrado:
    sistema = await obter_sistema(db, tenant_id=tenant_id, sistema_id=sistema_id)
    if sistema.revogado_em is None:
        sistema.ativo = False
        sistema.revogado_em = _utcnow()
        await db.commit()
        await db.refresh(sistema)
    return sistema

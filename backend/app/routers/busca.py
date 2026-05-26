"""Busca global cross-entidade — Fase 24.

Search simples por ILIKE em 3 entidades: processo (numero), manifestante
(nome + cpf_cnpj), usuário (nome + email). Limite hard de 8 resultados
por categoria pra resposta rápida. Pra full-text e ranking, futuro.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Manifestante, Processo, Usuario

router = APIRouter(prefix="/busca", tags=["busca"])


@router.get("")
async def busca_global(
    q: str = Query("", min_length=2, max_length=80),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Retorna resultados em 3 buckets (processos/manifestantes/usuarios).
    Cada bucket tem no máximo 8 resultados."""
    q = q.strip()
    if len(q) < 2:
        return {"processos": [], "manifestantes": [], "usuarios": [], "q": q}

    like = f"%{q}%"

    # Processos por número (case-insensitive)
    procs = (
        await db.execute(
            select(Processo.id, Processo.numero_processo, Processo.data_hora_abertura)
            .where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.numero_processo.ilike(like),
            )
            .order_by(Processo.data_hora_abertura.desc())
            .limit(8)
        )
    ).all()

    # Manifestantes por nome ou CPF/CNPJ
    manifs = (
        await db.execute(
            select(Manifestante.id, Manifestante.nome, Manifestante.cpf_cnpj)
            .where(
                Manifestante.tenant_id == tenant_id,
                Manifestante.excluido.is_(False),
                or_(
                    Manifestante.nome.ilike(like),
                    Manifestante.cpf_cnpj.ilike(like),
                ),
            )
            .order_by(Manifestante.nome)
            .limit(8)
        )
    ).all()

    # Usuários por nome ou email
    usrs = (
        await db.execute(
            select(Usuario.id, Usuario.nome, Usuario.email)
            .where(
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
                or_(Usuario.nome.ilike(like), Usuario.email.ilike(like)),
            )
            .order_by(Usuario.nome)
            .limit(8)
        )
    ).all()

    return {
        "q": q,
        "processos": [
            {
                "id": p_id,
                "numero": numero,
                "data_abertura": data.isoformat() if data else None,
            }
            for p_id, numero, data in procs
        ],
        "manifestantes": [
            {"id": m_id, "nome": nome, "cpf_cnpj": cpf}
            for m_id, nome, cpf in manifs
        ],
        "usuarios": [
            {"id": u_id, "nome": nome, "email": email}
            for u_id, nome, email in usrs
        ],
    }

"""Busca global cross-entidade — Fase 24.

Search simples por ILIKE em 3 entidades: processo (numero), manifestante
(nome + cpf_cnpj), usuário (nome + email). Limite hard de 8 resultados
por categoria pra resposta rápida. Pra full-text e ranking, futuro.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.perms import require_permission
from ..database import get_db
from ..models import Manifestante, Processo, Usuario
from .processos import acesso_niveis_dep

router = APIRouter(prefix="/busca", tags=["busca"])


@router.get(
    "",
    dependencies=[Depends(require_permission("processo"))],
)
async def busca_global(
    q: str = Query("", min_length=2, max_length=80),
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
    niveis: list[str] | None = Depends(acesso_niveis_dep),
):
    """Retorna resultados em 3 buckets (processos/manifestantes/usuarios).
    Cada bucket tem no máximo 8 resultados."""
    q = q.strip()
    if len(q) < 2:
        return {"processos": [], "manifestantes": [], "usuarios": [], "q": q}

    like = f"%{q}%"
    # CPF/CNPJ de manifestante é gravado sem máscara: "123.456.789-09" procura
    # "12345678909", e o CNPJ alfanumérico "12.ABC.345/01DE-35" procura
    # "12ABC34501DE35" (o ilike cobre maiúscula e minúscula).
    chave_doc = "".join(ch for ch in q if ch.isascii() and ch.isalnum())
    like_doc = f"%{chave_doc}%" if chave_doc else like

    # Processos por número (case-insensitive)
    procs = (
        await db.execute(
            select(Processo.id, Processo.numero_processo, Processo.data_hora_abertura)
            .where(
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
                Processo.numero_processo.ilike(like),
                # Sigilo: o mesmo recorte da listagem. O detalhe de processo
                # sigiloso responde 404 para não revelar que ele existe; a
                # busca listava o número dele a qualquer um com `processo`.
                *([Processo.nivel_sigilo.in_(niveis)] if niveis is not None else []),
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
                    Manifestante.cpf_cnpj.ilike(like_doc),
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

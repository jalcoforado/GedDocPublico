"""Apoio compartilhado para cenários de pagamentos."""
from sqlalchemy import select

from app.models import UnidadeTrabalho


async def id_unidade_padrao(session, tenant_id: int) -> int:
    """Retorna uma unidade ativa criada pelo provisionamento do tenant."""
    unidade_id = (await session.execute(
        select(UnidadeTrabalho.id).where(
            UnidadeTrabalho.tenant_id == tenant_id,
            UnidadeTrabalho.excluido.is_(False),
        ).order_by(UnidadeTrabalho.id).limit(1)
    )).scalar_one_or_none()
    assert unidade_id is not None, "tenant de teste deve possuir unidade de trabalho"
    return unidade_id

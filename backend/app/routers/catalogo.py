"""Endpoints de leitura para popular selects do frontend."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..auth.modulos import require_modulo
from ..database import get_db, tenant_filter
from ..models import Nivel, Prioridade, Sistema, TipoUnidadeTrabalho, Transacao, Usuario
from ..schemas.grupo import NivelOut, SistemaOut, TransacaoOut
from ..schemas.processo import PrioridadeOut
from ..schemas.unidade import TipoUnidadeOut

router = APIRouter(prefix="/catalogo", tags=["catalogo"])

# Efeito colateral aceito (achado na revisão da Task 2/3, 2026-07-30, registrado
# num lugar só no review final): `/niveis`, `/sistemas`, `/transacoes` e
# `/prioridades` não declaravam `require_tenant_id` — nenhuma delas filtra por
# tenant no corpo do endpoint. `require_modulo(...)` injeta essa dependência
# por baixo (ela mesma precisa do tenant para resolver a contratação). Fora do
# nginx, com `STRICT_TENANT_RESOLUTION=true` e Host sem subdomínio resolvível,
# essas 4 rotas passam a poder responder 400 onde antes davam 200. `/tipos-unidade`
# já declarava `require_tenant_id` por conta própria (filtra `TipoUnidadeTrabalho`
# por tenant) e não é afetada. Aceito por ora; atrás do nginx (produção) o
# tenant sempre resolve, então não há regressão observável ali. Mesmo efeito em
# `/estados`, `/cidades`, `/bairros` (`routers/localizacao.py`) e `/jobs/agenda`
# (`routers/jobs.py`) — comentário próprio em cada arquivo.


@router.get(
    "/niveis",
    response_model=list[NivelOut],
    dependencies=[Depends(require_modulo("administracao"))],
)
async def list_niveis(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NivelOut]:
    stmt = select(Nivel).where(Nivel.excluido.is_(False)).order_by(Nivel.valor)
    return [NivelOut.model_validate(n) for n in (await db.execute(stmt)).scalars().all()]


@router.get(
    "/sistemas",
    response_model=list[SistemaOut],
    dependencies=[Depends(require_modulo("administracao"))],
)
async def list_sistemas(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SistemaOut]:
    stmt = select(Sistema).where(Sistema.excluido.is_(False)).order_by(Sistema.sistema)
    return [SistemaOut.model_validate(s) for s in (await db.execute(stmt)).scalars().all()]


@router.get(
    "/transacoes",
    response_model=list[TransacaoOut],
    dependencies=[Depends(require_modulo("administracao"))],
)
async def list_transacoes(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TransacaoOut]:
    stmt = (
        select(Transacao)
        .where(Transacao.excluido.is_(False))
        .order_by(Transacao.transacao)
    )
    return [TransacaoOut.model_validate(t) for t in (await db.execute(stmt)).scalars().all()]


@router.get(
    "/tipos-unidade",
    response_model=list[TipoUnidadeOut],
    dependencies=[Depends(require_modulo("administracao"))],
)
async def list_tipos_unidade(
    _: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[TipoUnidadeOut]:
    stmt = select(TipoUnidadeTrabalho).where(TipoUnidadeTrabalho.excluido.is_(False))
    stmt = tenant_filter(stmt, TipoUnidadeTrabalho, tenant_id).order_by(
        TipoUnidadeTrabalho.tipo_unidade_trabalho
    )
    return [
        TipoUnidadeOut.model_validate(t)
        for t in (await db.execute(stmt)).scalars().all()
    ]


# Mesmo efeito colateral do comentário no topo do arquivo: `/prioridades`
# também não declarava `require_tenant_id`.
@router.get(
    "/prioridades",
    response_model=list[PrioridadeOut],
    dependencies=[Depends(require_modulo("protocolo"))],
)
async def list_prioridades(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PrioridadeOut]:
    stmt = (
        select(Prioridade)
        .where(Prioridade.excluido.is_(False), Prioridade.ativo.is_(True))
        .order_by(Prioridade.fator)
    )
    return [PrioridadeOut.model_validate(p) for p in (await db.execute(stmt)).scalars().all()]

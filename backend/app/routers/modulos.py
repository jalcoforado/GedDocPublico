from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user
from ..config import get_settings
from ..database import get_db
from ..models import ConfiguracoesModulos, Modulo, Usuario
from ..schemas.permissao import ModuloItem, ModulosMeResponse

router = APIRouter(prefix="/modulos", tags=["modulos"])


@router.get("/me", response_model=ModulosMeResponse)
async def me(
    _: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ModulosMeResponse:
    settings = get_settings()
    stmt = (
        select(Modulo, ConfiguracoesModulos)
        .join(ConfiguracoesModulos, ConfiguracoesModulos.id_modulo == Modulo.id)
        .where(
            ConfiguracoesModulos.ativo.is_(True),
            ConfiguracoesModulos.ambiente == settings.environment,
        )
        .order_by(Modulo.modulo)
    )
    rows = (await db.execute(stmt)).all()
    items = [
        ModuloItem(id=m.id, modulo=m.modulo or "", icone=m.icone, url=cm.url)
        for m, cm in rows
    ]
    return ModulosMeResponse(items=items)

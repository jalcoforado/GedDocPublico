from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.deps import get_current_user, require_tenant_id
from ..database import get_db
from ..models import Usuario
from ..schemas.permissao import PermissaoItem, PermissaoMeResponse
from ..services.permissoes import load_permissions

router = APIRouter(prefix="/permissoes", tags=["permissoes"])


@router.get("/me", response_model=PermissaoMeResponse)
async def me(
    user: Usuario = Depends(get_current_user),
    tenant_id: int = Depends(require_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> PermissaoMeResponse:
    perms = await load_permissions(db, user.id, tenant_id=tenant_id)
    return PermissaoMeResponse(
        usuario_id=user.id,
        is_super_usuario=perms.is_super_usuario,
        nivel_valor=perms.nivel_valor,
        permissoes=[
            PermissaoItem(
                codigo=p.codigo,
                transacao=p.transacao,
                inserir=p.inserir,
                atualizar=p.atualizar,
                excluir=p.excluir,
            )
            for p in perms.items
        ],
    )

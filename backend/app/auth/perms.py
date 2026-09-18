"""Permission enforcement helper.

Provides a FastAPI dependency factory `require_permission(codigo, action)`
that checks whether the current user has the given permission. Super-usuários
bypass all checks.

The permission system mirrors the PHP `Usuario::permissions()` (see
`services/permissoes.py`). Codes are short strings like "unidadeTrabalho",
"workflow", "usuario"; actions are "inserir" | "atualizar" | "excluir" or
None (just "ver/access").

Usage:

    @router.post("", dependencies=[Depends(require_permission("unidadeTrabalho", "inserir"))])
    async def create_unidade(...):
        ...

Or to also receive the user:

    user: Usuario = Depends(require_permission("unidadeTrabalho", "atualizar"))
"""
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Usuario
from ..services.permissoes import load_permissions
from .deps import get_current_user, ler_unidade_contexto, require_tenant_id

Action = Literal["inserir", "atualizar", "excluir"]


def require_permission(codigo: str, action: Action | None = None):
    """Cria uma FastAPI dependency que exige a permissão `(codigo, action)`.

    `action=None` significa "qualquer acesso à transação" (ler basta).
    Super-usuário (nivel.valor == 0) bypassa todas as checagens.
    """

    async def _check(
        user: Usuario = Depends(get_current_user),
        tenant_id: int = Depends(require_tenant_id),
        db: AsyncSession = Depends(get_db),
        # Anotação SEM `| None` de propósito: FastAPI só reconhece o
        # parâmetro especial `Request` (injeção automática, sem Depends())
        # pelo tipo exato — Optional quebraria com "Invalid args for
        # response field". O default None é só para as MUITAS chamadas
        # diretas de `_check(...)` na suíte, fora do ciclo do FastAPI, que
        # nunca passam `request` (mesmo padrão de test_pr4d_http_gates.py).
        request: Request = None,
    ) -> Usuario:
        unidade_contexto = await ler_unidade_contexto(request, db)
        perms = await load_permissions(
            db, user.id, tenant_id=tenant_id, id_unidade_contexto=unidade_contexto
        )
        if codigo in perms.codigos_bloqueados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Módulo não contratado para a transação '{codigo}'",
            )
        if perms.is_super_usuario:
            return user
        item = next((p for p in perms.items if p.codigo == codigo), None)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sem permissão para a transação '{codigo}'",
            )
        if action is not None and not getattr(item, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sem permissão de '{action}' em '{codigo}'",
            )
        return user

    return _check


def require_any_permission(*codigos: str):
    """Dependency que exige QUALQUER uma das transações (leitura). Super-usuário bypassa."""

    async def _check(
        user: Usuario = Depends(get_current_user),
        tenant_id: int = Depends(require_tenant_id),
        db: AsyncSession = Depends(get_db),
        # Anotação SEM `| None` de propósito: FastAPI só reconhece o
        # parâmetro especial `Request` (injeção automática, sem Depends())
        # pelo tipo exato — Optional quebraria com "Invalid args for
        # response field". O default None é só para as MUITAS chamadas
        # diretas de `_check(...)` na suíte, fora do ciclo do FastAPI, que
        # nunca passam `request` (mesmo padrão de test_pr4d_http_gates.py).
        request: Request = None,
    ) -> Usuario:
        unidade_contexto = await ler_unidade_contexto(request, db)
        perms = await load_permissions(
            db, user.id, tenant_id=tenant_id, id_unidade_contexto=unidade_contexto
        )
        disponiveis = [c for c in codigos if c not in perms.codigos_bloqueados]
        if not disponiveis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Módulo não contratado para nenhuma das transações exigidas",
            )
        if perms.is_super_usuario or any(p.codigo in disponiveis for p in perms.items):
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Sem permissão (requer uma de: {', '.join(codigos)})",
        )

    return _check

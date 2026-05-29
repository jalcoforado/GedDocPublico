"""Reset de senha temporária de usuário (PR 3b).

Regras (decisão 5):
- Usuário **escopado ao tenant** (404 se não for do tenant — sem cross-tenant).
- Gera senha temporária; persiste **só** o hash moderno (`senha_bcrypt`) e
  zera `senha` (MD5 legado) — assim a senha antiga deixa de valer e nada fica
  em claro no banco.
- Retorna a senha em claro **uma única vez** (o caller a devolve na resposta).
- Audita o reset (ator + afetado; marca claramente se o afetado é SU). A senha
  **não** entra no payload de auditoria.
- Não envia e-mail; não implementa `must_change_password` (fora de escopo).
"""
from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..models import Usuario
from .audit import log as audit_log
from .permissoes import load_permissions


async def resetar_senha_usuario(
    db: AsyncSession,
    *,
    usuario_id: int,
    tenant_id: int,
    ator_usuario_id: int,
    request: Request | None = None,
) -> tuple[Usuario, str]:
    """Gera senha temporária para `usuario_id` (do tenant). Comita. Retorna
    `(usuario, senha_temporaria)` — a senha só existe aqui em claro."""
    user = (
        await db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id,
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado"
        )

    senha_temp = secrets.token_urlsafe(12)
    user.senha_bcrypt = hash_password(senha_temp)
    user.senha = ""  # zera MD5 legado: a senha antiga deixa de funcionar

    # Marca claramente se o afetado é super-usuário (decisão 5).
    perms_afetado = await load_permissions(db, user.id, tenant_id=tenant_id)
    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=ator_usuario_id,
        acao="usuario.senha_resetada",
        entidade="usuario",
        id_entidade=user.id,
        payload={
            "id_usuario_afetado": user.id,
            "afetado_super_usuario": perms_afetado.is_super_usuario,
        },
        request=request,
    )

    await db.commit()
    await db.refresh(user)
    return user, senha_temp

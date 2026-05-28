"""Operações de conta do próprio usuário (PR2c).

`alterar_senha`: troca self-service de senha. Valida a senha atual (aceitando
credencial legada MD5 só para AUTENTICAR a troca) e grava a nova senha
**somente em bcrypt** (`senha_bcrypt`). Nunca grava MD5 — assim a próxima
assinatura deixa de cair no bloqueio de credencial legada.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password, verify_password
from ..models import Usuario
from .audit import log as audit_log


class ContaError(Exception):
    pass


async def alterar_senha(
    db: AsyncSession,
    *,
    usuario: Usuario,
    senha_atual: str,
    nova_senha: str,
) -> None:
    ok, _needs_rehash = verify_password(
        senha_atual, bcrypt_hash=usuario.senha_bcrypt, md5_hash=usuario.senha
    )
    if not ok:
        raise ContaError("Senha atual incorreta")
    if len(nova_senha) < 6:
        raise ContaError("A nova senha deve ter ao menos 6 caracteres")

    # Grava apenas bcrypt — desbloqueia a assinatura (sem dependência de MD5).
    usuario.senha_bcrypt = hash_password(nova_senha)

    await audit_log(
        db,
        tenant_id=usuario.tenant_id,
        id_usuario=usuario.id,
        acao="usuario.senha_alterada",
        entidade="usuario",
        id_entidade=usuario.id,
        payload={"metodo": "bcrypt"},
    )
    await db.commit()

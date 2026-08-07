"""Operações de conta do próprio usuário (PR2c + SEC-1 Commit 3).

`alterar_senha`: troca self-service de senha. Valida a senha atual (aceitando
credencial legada MD5 só para AUTENTICAR a troca) e grava a nova senha
**somente em bcrypt** (`senha_bcrypt`). Nunca grava MD5 — assim a próxima
assinatura deixa de cair no bloqueio de credencial legada.

SEC-1 (Commit 3): ao trocar com sucesso, zera `must_change_password` e limpa
o MD5 legado. Esta é a porta de saída do estado de senha temporária — a rota
correspondente (`POST /auth/alterar-senha`) está na whitelist do guard
(Commit 2) para que o usuário flagged consiga concluir o fluxo.
"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import SENHA_MINIMA, hash_password, verify_password
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
    request: Request | None = None,
) -> None:
    ok, _needs_rehash = verify_password(
        senha_atual, bcrypt_hash=usuario.senha_bcrypt, md5_hash=usuario.senha
    )
    if not ok:
        raise ContaError("Senha atual incorreta")
    # Redundante com o `min_length` do schema quando a chamada vem por HTTP, e
    # é a ÚNICA barreira quando vem de dentro (o service é chamado direto por
    # CLI e por teste). Vale a duplicação; o que não vale é o número duplicado,
    # que foi como o schema e este `if` ficaram cada um com o seu.
    if len(nova_senha) < SENHA_MINIMA:
        raise ContaError(f"A nova senha deve ter ao menos {SENHA_MINIMA} caracteres")

    # Grava apenas bcrypt — desbloqueia a assinatura (sem dependência de MD5).
    usuario.senha_bcrypt = hash_password(nova_senha)
    # SEC-1 (Commit 3): limpa o MD5 legado para alinhar com provisionamento/
    # reset (que também zeram MD5). Se o usuário acabou de sair de uma senha
    # temporária, a antiga era só bcrypt; se veio de credencial PHP legada,
    # a partir daqui passa a usar só bcrypt.
    usuario.senha = ""
    # SEC-1 (Commit 3): zera flag de troca obrigatória. Próximas requisições
    # voltam a passar pelo gate sem 403.
    must_change_password_was_set = bool(usuario.must_change_password)
    usuario.must_change_password = False

    await audit_log(
        db,
        tenant_id=usuario.tenant_id,
        id_usuario=usuario.id,
        acao="usuario.senha_alterada",
        entidade="usuario",
        id_entidade=usuario.id,
        payload={
            "metodo": "bcrypt",
            "must_change_password_cleared": must_change_password_was_set,
        },
        request=request,
    )
    await db.commit()

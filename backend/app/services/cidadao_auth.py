"""Auth do cidadão (usuário externo).

Senha em MD5, espelhando `Positiv\\Hash` (mesma compatibilidade do admin login).
Cadastro busca duplicidade por CPF/CNPJ DENTRO do tenant atual — a mesma pessoa
pode existir como cidadão em mais de uma prefeitura, mas no mesmo tenant é único.

Fase 13a: cadastrar e login operam dentro de um tenant.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_md5, hash_password, verify_password
from ..models import UsuarioExterno
from ..schemas.cidadao import CadastroCidadaoRequest


class CidadaoAuthError(Exception):
    pass


def _normaliza_cpf_cnpj(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


async def cadastrar(
    db: AsyncSession,
    payload: CadastroCidadaoRequest,
    *,
    tenant_id: int,
    app: str,
) -> UsuarioExterno:
    cpf_cnpj = _normaliza_cpf_cnpj(payload.cpf_cnpj)
    if len(cpf_cnpj) not in (11, 14):
        raise CidadaoAuthError("CPF/CNPJ inválido")

    existe = (
        await db.execute(
            select(UsuarioExterno).where(
                UsuarioExterno.cpf_cnpj == cpf_cnpj,
                UsuarioExterno.tenant_id == tenant_id,
                UsuarioExterno.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if existe is not None:
        raise CidadaoAuthError("Já existe cadastro para este CPF/CNPJ")

    cidadao = UsuarioExterno(
        tenant_id=tenant_id,
        nome=payload.nome.strip(),
        cpf_cnpj=cpf_cnpj,
        email=payload.email.strip().lower(),
        senha=hash_md5(payload.senha),
        senha_bcrypt=hash_password(payload.senha),
        login_govbr=False,
        ativo=True,
        excluido=False,
        uid=uuid4(),
        data_criacao=datetime.utcnow(),
        data_limite_ativacao=datetime.utcnow() + timedelta(days=365),
        app=app,
        telefone=payload.telefone,
        telefone_whatsapp=payload.telefone_whatsapp,
    )
    db.add(cidadao)
    await db.commit()
    await db.refresh(cidadao)
    return cidadao


async def login(
    db: AsyncSession, *, tenant_id: int, cpf_cnpj: str, senha: str
) -> UsuarioExterno:
    cpf_cnpj_norm = _normaliza_cpf_cnpj(cpf_cnpj)
    cidadao = (
        await db.execute(
            select(UsuarioExterno).where(
                UsuarioExterno.cpf_cnpj == cpf_cnpj_norm,
                UsuarioExterno.tenant_id == tenant_id,
                UsuarioExterno.excluido.is_(False),
                UsuarioExterno.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if cidadao is None:
        raise CidadaoAuthError("CPF/CNPJ ou senha inválidos")
    ok, needs_rehash = verify_password(
        senha, bcrypt_hash=cidadao.senha_bcrypt, md5_hash=cidadao.senha
    )
    if not ok:
        raise CidadaoAuthError("CPF/CNPJ ou senha inválidos")
    if needs_rehash:
        cidadao.senha_bcrypt = hash_password(senha)
        await db.commit()
    return cidadao

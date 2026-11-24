"""Segredos de uso único da conta: convite, verificação de e-mail, redefinição
de senha e código de 2FA (migration 0137, tabela `aprimora_py.token_conta`).

Regras:

- O banco guarda só o HMAC-SHA256 do segredo, com a chave HS do sistema. Um
  dump da tabela não serve para entrar em conta nenhuma — e, no caso do código
  de 2FA (6 dígitos, espaço pequeno), não dá para testar o milhão de
  combinações offline sem a chave.
- Emitir um segredo novo invalida os anteriores da mesma finalidade para o
  mesmo titular (`usado_em` preenchido): só o link/código mais recente vale.
- Consumir marca `usado_em`. Link expirado, usado ou substituído = inválido,
  sem dizer qual dos três (não ajuda quem está tentando adivinhar).
- O código de 2FA aceita no máximo `MAX_TENTATIVAS_CODIGO` erros; depois disso
  ele morre e é preciso pedir outro.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import get_jwt_secret
from ..models import TokenConta

VALIDADE = {
    "convite": timedelta(days=7),
    "verificar_email": timedelta(days=2),
    "redefinir_senha": timedelta(hours=1),
    "codigo_2fa": timedelta(minutes=10),
}
MAX_TENTATIVAS_CODIGO = 5
# Intervalo mínimo entre dois envios para o mesmo titular e finalidade:
# segura quem aperta "reenviar" em sequência (e quem usaria o formulário para
# encher a caixa de alguém).
INTERVALO_REENVIO = timedelta(seconds=60)


@dataclass(frozen=True)
class Titular:
    """De quem é o segredo: um servidor OU um cidadão."""

    tenant_id: int
    id_usuario: int | None = None
    id_usuario_externo: int | None = None

    def __post_init__(self) -> None:
        if (self.id_usuario is None) == (self.id_usuario_externo is None):
            raise ValueError("Titular precisa de exatamente um: id_usuario ou id_usuario_externo")


class EnvioRecenteError(Exception):
    """Pediu um segredo novo antes de `INTERVALO_REENVIO`."""


async def _hmac(db: AsyncSession, finalidade: str, segredo: str) -> str:
    chave = (await get_jwt_secret(db)).encode()
    return hmac.new(chave, f"{finalidade}:{segredo}".encode(), hashlib.sha256).hexdigest()


def _do_titular(stmt, titular: Titular, finalidade: str):  # noqa: ANN001, ANN202
    stmt = stmt.where(
        TokenConta.tenant_id == titular.tenant_id,
        TokenConta.finalidade == finalidade,
    )
    if titular.id_usuario is not None:
        return stmt.where(TokenConta.id_usuario == titular.id_usuario)
    return stmt.where(TokenConta.id_usuario_externo == titular.id_usuario_externo)


async def emitir(
    db: AsyncSession, titular: Titular, finalidade: str, *, respeitar_intervalo: bool = True
) -> tuple[TokenConta, str]:
    """Cria o segredo e devolve `(linha, segredo_em_claro)`.

    O segredo em claro só existe aqui: vai para o e-mail e é descartado.
    Código de 2FA = 6 dígitos; os demais = 43 caracteres url-safe (256 bits).
    Não faz commit — quem chama decide junto com o envio.
    """
    agora = datetime.utcnow()
    if respeitar_intervalo:
        ultimo = (
            await db.execute(
                _do_titular(select(TokenConta.criado_em), titular, finalidade)
                .order_by(TokenConta.criado_em.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if ultimo is not None and agora - ultimo < INTERVALO_REENVIO:
            raise EnvioRecenteError()

    await db.execute(
        _do_titular(update(TokenConta), titular, finalidade)
        .where(TokenConta.usado_em.is_(None))
        .values(usado_em=agora)
    )
    segredo = (
        f"{secrets.randbelow(10**6):06d}" if finalidade == "codigo_2fa" else secrets.token_urlsafe(32)
    )
    linha = TokenConta(
        tenant_id=titular.tenant_id,
        id_usuario=titular.id_usuario,
        id_usuario_externo=titular.id_usuario_externo,
        finalidade=finalidade,
        segredo_hash=await _hmac(db, finalidade, segredo),
        tentativas=0,
        expira_em=agora + VALIDADE[finalidade],
        criado_em=agora,
    )
    db.add(linha)
    await db.flush()
    return linha, segredo


async def localizar(
    db: AsyncSession, segredo: str, finalidades: tuple[str, ...], *, tenant_id: int
) -> TokenConta | None:
    """Acha o link válido (não usado, não expirado) SEM consumi-lo."""
    for finalidade in finalidades:
        linha = (
            await db.execute(
                select(TokenConta).where(
                    TokenConta.tenant_id == tenant_id,
                    TokenConta.finalidade == finalidade,
                    TokenConta.segredo_hash == await _hmac(db, finalidade, segredo),
                    TokenConta.usado_em.is_(None),
                    TokenConta.expira_em > datetime.utcnow(),
                )
            )
        ).scalar_one_or_none()
        if linha is not None:
            return linha
    return None


async def consumir(
    db: AsyncSession, segredo: str, finalidades: tuple[str, ...], *, tenant_id: int
) -> TokenConta | None:
    """Acha e consome o link. `None` = inválido, expirado ou já usado."""
    linha = await localizar(db, segredo, finalidades, tenant_id=tenant_id)
    if linha is not None:
        linha.usado_em = datetime.utcnow()
    return linha


async def conferir_codigo(db: AsyncSession, id_token: int, codigo: str, *, tenant_id: int) -> bool:
    """Confere o código de 2FA da linha `id_token`. Consome se certo; conta o
    erro se errado (e mata o código na `MAX_TENTATIVAS_CODIGO`-ésima falha)."""
    linha = (
        await db.execute(
            select(TokenConta).where(
                TokenConta.id == id_token,
                TokenConta.tenant_id == tenant_id,
                TokenConta.finalidade == "codigo_2fa",
            )
        )
    ).scalar_one_or_none()
    agora = datetime.utcnow()
    if linha is None or linha.usado_em is not None or linha.expira_em <= agora:
        return False
    esperado = linha.segredo_hash
    recebido = await _hmac(db, "codigo_2fa", "".join(ch for ch in codigo if ch.isdigit()))
    if hmac.compare_digest(esperado, recebido):
        linha.usado_em = agora
        return True
    linha.tentativas += 1
    if linha.tentativas >= MAX_TENTATIVAS_CODIGO:
        linha.usado_em = agora
    return False

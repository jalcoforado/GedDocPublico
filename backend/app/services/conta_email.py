"""E-mails da conta: convite, confirmação de e-mail, redefinição de senha e
código de 2FA — e o envio em si.

O envio usa o mesmo SMTP das notificações (`SMTP_*` em `config.py`); sem
`SMTP_HOST` ele só registra no log (`email_stub_enviado`), como o resto do
sistema em dev. Em dev local, o Mailpit (`docker-compose.override.yml`) faz o
papel do servidor e mostra as mensagens numa caixa de entrada web.

O endereço dos links sai, nesta ordem, de `PUBLIC_BASE_URL` (prod com um
domínio fixo) ou do `Origin` da própria requisição — que traz a porta, ao
contrário do `Host` que o nginx repassa —, e por fim de `X-Forwarded-Proto` +
`Host`. O `Origin` só é aceito se for do mesmo host: senão, um formulário em
site alheio escolheria para onde o link do e-mail aponta.
"""
from __future__ import annotations

import logging
from email.message import EmailMessage
from urllib.parse import urlencode, urlparse

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Tenant, Usuario
from . import conta_tokens

logger = logging.getLogger(__name__)


async def enviar_email(*, para: str, assunto: str, texto: str, tenant_id: int | None = None) -> None:
    """Envia texto puro por SMTP; sem `SMTP_HOST`, só registra no log."""
    settings = get_settings()
    if not settings.smtp_host:
        logger.info(
            "email_stub_enviado",
            extra={"tenant_id": tenant_id, "to": para, "titulo": assunto},
        )
        return

    import aiosmtplib  # type: ignore[import-untyped]  # lazy: custo só com SMTP ligado

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = para
    msg["Subject"] = assunto
    msg.set_content(texto)
    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user or None,
        password=settings.smtp_password or None,
        start_tls=settings.smtp_use_tls,
        timeout=20,
    )
    logger.info(
        "email_smtp_enviado",
        extra={"tenant_id": tenant_id, "to": para, "host": settings.smtp_host},
    )


def url_publica(request: Request) -> str:
    base = get_settings().public_base_url.strip().rstrip("/")
    if base:
        return base
    host = request.headers.get("host", "")
    origem = request.headers.get("origin", "")
    if origem and urlparse(origem).hostname == host.split(":")[0]:
        return origem.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{proto}://{host}"


def link(request: Request, caminho: str, token: str) -> str:
    return f"{url_publica(request)}{caminho}?{urlencode({'token': token})}"


async def nome_do_orgao(db: AsyncSession, tenant_id: int) -> str:
    nome = (await db.execute(select(Tenant.nome).where(Tenant.id == tenant_id))).scalar_one_or_none()
    return nome or "Aprimora"


def _rodape(orgao: str) -> str:
    return f"\n\n—\n{orgao} · Aprimora\nEste e-mail foi enviado automaticamente; não é preciso respondê-lo."


def texto_convite(*, nome: str, orgao: str, url: str) -> tuple[str, str]:
    return (
        f"Seu acesso ao Aprimora — {orgao}",
        f"Olá, {nome}.\n\n"
        f"{orgao} criou um acesso ao Aprimora para você. Para ativar a conta e "
        f"escolher a sua senha, abra o link abaixo (vale por 7 dias):\n\n{url}\n\n"
        "Se você não esperava este convite, ignore este e-mail."
        + _rodape(orgao),
    )


def texto_verificar_email(*, nome: str, orgao: str, url: str) -> tuple[str, str]:
    return (
        "Confirme o seu e-mail",
        f"Olá, {nome}.\n\n"
        f"Recebemos o seu cadastro no portal do cidadão de {orgao}. Para ativá-lo, "
        f"confirme o seu e-mail pelo link abaixo (vale por 2 dias):\n\n{url}\n\n"
        "Se não foi você quem se cadastrou, ignore este e-mail."
        + _rodape(orgao),
    )


def texto_redefinir_senha(*, nome: str, orgao: str, url: str) -> tuple[str, str]:
    return (
        "Redefinição de senha",
        f"Olá, {nome}.\n\n"
        "Recebemos um pedido para redefinir a sua senha. Para escolher uma nova, "
        f"abra o link abaixo (vale por 1 hora):\n\n{url}\n\n"
        "Se você não pediu, ignore este e-mail: a sua senha atual continua valendo."
        + _rodape(orgao),
    )


def texto_codigo_2fa(*, nome: str, orgao: str, codigo: str) -> tuple[str, str]:
    return (
        f"Seu código de acesso: {codigo}",
        f"Olá, {nome}.\n\n"
        f"O seu código para entrar no Aprimora é:\n\n    {codigo}\n\n"
        "Ele vale por 10 minutos. Se não foi você quem tentou entrar, troque a "
        "sua senha: alguém a conhece."
        + _rodape(orgao),
    )


def mascarar_email(email: str) -> str:
    """`maria.silva@prefeitura.gov.br` → `ma•••••••@prefeitura.gov.br`."""
    usuario, _, dominio = email.partition("@")
    if not dominio:
        return "•••"
    visivel = usuario[:2] if len(usuario) > 3 else usuario[:1]
    return f"{visivel}{'•' * max(3, len(usuario) - len(visivel))}@{dominio}"


async def enviar_convite(db: AsyncSession, request: Request, user: Usuario) -> None:
    """Emite o convite do servidor e manda o e-mail. Usado na criação do
    usuário, no reenvio pelo administrador e no "esqueci a senha" de quem
    ainda não aceitou o convite. Faz commit (o segredo tem de existir antes
    de o e-mail sair)."""
    _, token = await conta_tokens.emitir(
        db,
        conta_tokens.Titular(tenant_id=user.tenant_id, id_usuario=user.id),
        "convite",
        respeitar_intervalo=False,
    )
    await db.commit()
    assunto, texto = texto_convite(
        nome=user.nome,
        orgao=await nome_do_orgao(db, user.tenant_id),
        url=link(request, "/login/convite", token),
    )
    await enviar_email(para=user.email, assunto=assunto, texto=texto, tenant_id=user.tenant_id)

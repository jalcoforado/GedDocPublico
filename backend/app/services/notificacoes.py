"""Motor de notificações multi-canal — Fase 17.

Camada de domínio que registra notificações no banco e despacha para
canais. Hoje:
- `in_app` é persistência pura (UI lista via API).
- `email` chama um driver plugável. Driver default = `_log_email_driver`
  que só loga (stub). Em prod basta setar env `SMTP_HOST` etc e trocar o
  driver (não implementado nesta fase).
- `whatsapp` reservado para a Fase 16.

Boas práticas aplicadas:
- Cada canal solicitado vira UMA linha na tabela (mesmo evento). Permite
  marcar lido em um sem afetar o outro e diagnosticar falhas por canal.
- Erros de envio externo NÃO levantam — gravam em `notificacao.erro` pra
  reenfileiramento futuro. In-app sempre é sucesso (só persiste).
- `enviado_em` só é setado nos canais externos depois do driver retornar OK.
  In-app fica com `enviado_em = criado_em` por convenção (já está disponível
  na UI no instante zero).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Notificacao, NotificacaoPreferencia, Usuario

logger = logging.getLogger("notificacoes")

CANAIS_VALIDOS = ("in_app", "email", "whatsapp")

# Defaults quando o usuário não tem row de preferência ainda
DEFAULT_PREFS = {
    "in_app": True,
    "email": True,
    "whatsapp": False,
}


@dataclass
class Destinatario:
    """Identifica quem recebe. Pelo menos um identificador (id_usuario,
    email ou telefone) precisa estar presente. Para canais externos
    (email/whatsapp) o motor resolve o endereço a partir de `id_usuario`
    se não vier explícito."""

    id_usuario: int | None = None
    email: str | None = None
    telefone: str | None = None

    def __post_init__(self) -> None:
        if self.id_usuario is None and not self.email and not self.telefone:
            raise ValueError(
                "Destinatario precisa de id_usuario, email ou telefone"
            )


async def enviar(
    db: AsyncSession,
    *,
    tenant_id: int,
    destinatarios: Sequence[Destinatario],
    canais: Sequence[str],
    tipo: str,
    titulo: str,
    mensagem: str,
    link_url: str | None = None,
    payload: dict[str, Any] | None = None,
    prioridade: str = "normal",
) -> list[Notificacao]:
    """Cria uma notificação por (destinatário × canal). Despacha externos.

    Retorna a lista das notificações criadas (já refreshed). Commit feito
    UMA vez no fim — caller pode confiar que ou tudo persistiu ou nada.
    """
    for c in canais:
        if c not in CANAIS_VALIDOS:
            raise ValueError(f"Canal inválido: {c!r}. Permitidos: {CANAIS_VALIDOS}")
    if not destinatarios:
        return []

    # Resolve emails/telefones para destinatários que só têm id_usuario
    precisa_email = "email" in canais and any(
        d.id_usuario is not None and not d.email for d in destinatarios
    )
    precisa_telefone = "whatsapp" in canais and any(
        d.id_usuario is not None and not d.telefone for d in destinatarios
    )
    emails_por_uid: dict[int, str] = {}
    telefones_por_uid: dict[int, str] = {}
    if precisa_email or precisa_telefone:
        uids = [d.id_usuario for d in destinatarios if d.id_usuario is not None]
        rows = (
            await db.execute(
                select(Usuario.id, Usuario.email, Usuario.telefone).where(
                    Usuario.id.in_(uids)
                )
            )
        ).all()
        for uid, em, tel in rows:
            if em:
                emails_por_uid[uid] = em
            if tel:
                telefones_por_uid[uid] = tel

    # Fase 17b — preferências por usuário interno. Email livre não tem
    # preferência (assume tudo true). Buscar todas as prefs num único query.
    prefs_por_uid: dict[int, NotificacaoPreferencia] = {}
    uids_internos = [d.id_usuario for d in destinatarios if d.id_usuario is not None]
    if uids_internos:
        prefs_rows = (
            await db.execute(
                select(NotificacaoPreferencia).where(
                    NotificacaoPreferencia.tenant_id == tenant_id,
                    NotificacaoPreferencia.id_usuario.in_(uids_internos),
                )
            )
        ).scalars().all()
        prefs_por_uid = {p.id_usuario: p for p in prefs_rows}

    def _canal_permitido(uid: int | None, canal: str) -> bool:
        """Email livre (sem uid) sempre permite todos os canais. Usuário
        interno consulta preferência (default se não tem row)."""
        if uid is None:
            return True
        pref = prefs_por_uid.get(uid)
        if pref is None:
            return DEFAULT_PREFS[canal]
        return {
            "in_app": pref.canal_in_app,
            "email": pref.canal_email,
            "whatsapp": pref.canal_whatsapp,
        }[canal]

    now = datetime.utcnow()
    criadas: list[Notificacao] = []
    for dest in destinatarios:
        for canal in canais:
            # Fase 17b — respeita preferência (opt-out por canal)
            if not _canal_permitido(dest.id_usuario, canal):
                continue

            # Resolve endpoint do canal externo
            endpoint_externo: str | None = None
            if canal == "email":
                endpoint_externo = dest.email or emails_por_uid.get(
                    dest.id_usuario or -1
                )
                if not endpoint_externo:
                    logger.warning(
                        "notificacao_email_sem_endereco",
                        extra={
                            "tenant_id": tenant_id,
                            "id_usuario": dest.id_usuario,
                            "tipo": tipo,
                        },
                    )
                    continue
            elif canal == "whatsapp":
                endpoint_externo = dest.telefone or telefones_por_uid.get(
                    dest.id_usuario or -1
                )
                if not endpoint_externo:
                    logger.warning(
                        "notificacao_whatsapp_sem_telefone",
                        extra={
                            "tenant_id": tenant_id,
                            "id_usuario": dest.id_usuario,
                            "tipo": tipo,
                        },
                    )
                    continue

            n = Notificacao(
                tenant_id=tenant_id,
                id_usuario=dest.id_usuario,
                destinatario_email=endpoint_externo if canal != "in_app" else None,
                canal=canal,
                tipo=tipo,
                titulo=titulo,
                mensagem=mensagem,
                link_url=link_url,
                payload=payload,
                prioridade=prioridade,
                criado_em=now,
                # in_app é entregue na hora; canais externos ficam pendentes
                enviado_em=now if canal == "in_app" else None,
            )
            db.add(n)
            criadas.append(n)

    await db.commit()
    for n in criadas:
        await db.refresh(n)

    # Despacho externo (in_app já foi servido só com persistência)
    for n in criadas:
        if n.canal == "in_app":
            continue
        try:
            if n.canal == "email":
                await _email_driver(n)
            elif n.canal == "whatsapp":
                await _whatsapp_driver(n)
            n.enviado_em = datetime.utcnow()
        except Exception as e:  # noqa: BLE001
            n.erro = str(e)[:1000]
            logger.exception(
                "notificacao_envio_falhou",
                extra={"id_notificacao": n.id, "canal": n.canal},
            )

    # Commit dos enviado_em / erros
    await db.commit()
    return criadas


async def _email_driver(n: Notificacao) -> None:
    """Email driver — Fase 17b.

    Se `SMTP_HOST` está setado: envia via aiosmtplib (STARTTLS opcional).
    Senão: stub log (mantém comportamento de dev).
    """
    settings = get_settings()
    if not settings.smtp_host:
        logger.info(
            "email_stub_enviado",
            extra={
                "tenant_id": n.tenant_id,
                "to": n.destinatario_email,
                "tipo": n.tipo,
                "titulo": n.titulo,
                "link": n.link_url,
            },
        )
        return

    # Real SMTP — import lazy pra evitar custo quando stub é ativo
    import aiosmtplib  # type: ignore[import-untyped]
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = n.destinatario_email
    msg["Subject"] = n.titulo

    corpo = n.mensagem
    if n.link_url:
        corpo += f"\n\nLink: {n.link_url}"
    msg.set_content(corpo)

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
        extra={
            "tenant_id": n.tenant_id,
            "to": n.destinatario_email,
            "tipo": n.tipo,
            "host": settings.smtp_host,
        },
    )


async def _whatsapp_driver(n: Notificacao) -> None:
    """WhatsApp driver — Fase 16.

    Provider selecionado via `WHATSAPP_PROVIDER` env:
    - `stub` (default): só loga. Útil pra dev.
    - `zenvia`: chama API REST da Zenvia.

    Em ambos os casos: `destinatario_email` carrega o telefone (E.164 esperado).
    Renomeei "endpoint do canal externo" em `enviar()` mas a coluna do banco
    continua `destinatario_email` pra não migrar — convenção é overload.
    """
    settings = get_settings()
    telefone = n.destinatario_email or ""
    body = n.mensagem
    if n.link_url:
        body += f"\n\n{n.link_url}"

    provider = (settings.whatsapp_provider or "stub").lower()
    if provider == "stub":
        logger.info(
            "whatsapp_stub_enviado",
            extra={
                "tenant_id": n.tenant_id,
                "to": telefone,
                "tipo": n.tipo,
                "titulo": n.titulo,
            },
        )
        return

    if provider == "zenvia":
        if not settings.zenvia_api_key or not settings.zenvia_from:
            raise RuntimeError(
                "Zenvia não configurado: setar ZENVIA_API_KEY e ZENVIA_FROM no .env"
            )
        # Import lazy pra não pagar custo no boot quando o provider é stub
        import httpx  # type: ignore[import-untyped]

        payload = {
            "from": settings.zenvia_from,
            "to": telefone,
            "contents": [{"type": "text", "text": body}],
        }
        headers = {
            "X-API-TOKEN": settings.zenvia_api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                settings.zenvia_api_url, json=payload, headers=headers
            )
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Zenvia respondeu {resp.status_code}: {resp.text[:300]}"
                )
        logger.info(
            "whatsapp_zenvia_enviado",
            extra={
                "tenant_id": n.tenant_id,
                "to": telefone,
                "tipo": n.tipo,
                "status": resp.status_code,
            },
        )
        return

    raise RuntimeError(
        f"WhatsApp provider desconhecido: {provider!r}. Use 'stub' ou 'zenvia'."
    )


# Helpers de preferência usados pelos endpoints
async def get_preferencia(
    db: AsyncSession, *, tenant_id: int, id_usuario: int
) -> dict[str, bool]:
    """Devolve preferências atuais (defaults se sem row)."""
    pref = (
        await db.execute(
            select(NotificacaoPreferencia).where(
                NotificacaoPreferencia.tenant_id == tenant_id,
                NotificacaoPreferencia.id_usuario == id_usuario,
            )
        )
    ).scalar_one_or_none()
    if pref is None:
        return dict(DEFAULT_PREFS)
    return {
        "in_app": pref.canal_in_app,
        "email": pref.canal_email,
        "whatsapp": pref.canal_whatsapp,
    }


async def set_preferencia(
    db: AsyncSession,
    *,
    tenant_id: int,
    id_usuario: int,
    in_app: bool | None = None,
    email: bool | None = None,
    whatsapp: bool | None = None,
) -> dict[str, bool]:
    """Upsert das preferências. Campos None mantêm valor atual (ou default)."""
    pref = (
        await db.execute(
            select(NotificacaoPreferencia).where(
                NotificacaoPreferencia.tenant_id == tenant_id,
                NotificacaoPreferencia.id_usuario == id_usuario,
            )
        )
    ).scalar_one_or_none()
    now = datetime.utcnow()
    if pref is None:
        pref = NotificacaoPreferencia(
            tenant_id=tenant_id,
            id_usuario=id_usuario,
            canal_in_app=in_app if in_app is not None else DEFAULT_PREFS["in_app"],
            canal_email=email if email is not None else DEFAULT_PREFS["email"],
            canal_whatsapp=whatsapp
            if whatsapp is not None
            else DEFAULT_PREFS["whatsapp"],
            criado_em=now,
        )
        db.add(pref)
    else:
        if in_app is not None:
            pref.canal_in_app = in_app
        if email is not None:
            pref.canal_email = email
        if whatsapp is not None:
            pref.canal_whatsapp = whatsapp
        pref.atualizado_em = now
    await db.commit()
    await db.refresh(pref)
    return {
        "in_app": pref.canal_in_app,
        "email": pref.canal_email,
        "whatsapp": pref.canal_whatsapp,
    }


async def contar_nao_lidas(
    db: AsyncSession, *, tenant_id: int, id_usuario: int
) -> int:
    """Conta notificações in_app não lidas pro Bell icon."""
    return (
        await db.execute(
            select(func.count(Notificacao.id)).where(
                Notificacao.tenant_id == tenant_id,
                Notificacao.id_usuario == id_usuario,
                Notificacao.canal == "in_app",
                Notificacao.lido_em.is_(None),
            )
        )
    ).scalar_one()

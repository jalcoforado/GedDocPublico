"""Validação pública de assinatura por código/token (PR2e).

Princípios (decisões fechadas no escopo):

- O lookup por token opaco **não é autorização**. Mesmo achando a linha pelo
  token, aplicamos uma validação restritiva própria antes de exibir qualquer
  coisa.
- **Não vazar existência**: token inexistente, revogado, processo sigiloso/
  não-ostensivo, anexo desentranhado, assinatura não-'assinada' ou tenant
  inativo → todos retornam a MESMA resposta neutra (o serviço devolve None; o
  router responde 404 `{valido:false}`).
- **Revogação automática é lazy**: re-checamos o estado ATUAL a cada consulta
  (sigilo, desentranhamento, status), sem depender de triggers eager.
- **Minimização (LGPD)**: a resposta positiva só carrega o probatório
  (signatário, data, hash, algoritmo, versão, nº do processo se ostensivo).
  Nunca IP/UA/método/evidências/CPF/matrícula/e-mail/dados do cidadão.

O serviço é chamado numa sessão já escopada ao tenant (resolvido pelo
subdomínio no `TenantMiddleware`), então o lookup é naturalmente
tenant-scoped (token + tenant_id) — sem necessidade de bypass de RLS.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import anexos as anexos_svc
from . import validacao_publica_throttle as throttle
from .audit import log as audit_log
from .sigilo import assert_acesso_processo
from ..models import (
    AnexoProcesso,
    AssinaturaAnexo,
    Processo,
    Tenant,
    Usuario,
    UsuarioAssinatura,
)
from ..schemas.assinatura import ValidacaoPublicaOut

AVISO = (
    "Assinatura eletrônica interna com evidências — não é assinatura "
    "qualificada ICP-Brasil."
)


class ValidacaoPublicaError(Exception):
    pass


async def _auditar_negativa(db: AsyncSession, *, tenant_id: int, ip: str | None) -> None:
    """Audita uma resposta neutra — no máx. 1x por IP por janela (não inunda).
    Não vincula a nenhuma linha (id_entidade=None) para não confirmar existência."""
    if await throttle.deve_auditar_negativa(ip):
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=None,
            acao="assinatura.validacao_publica_negada",
            entidade="assinatura_anexo",
            id_entidade=None,
            payload={"ip": ip},
        )
        await db.commit()


async def validar_publico(
    db: AsyncSession,
    codigo: str,
    *,
    tenant_id: int,
    tenant_slug: str,
    ip: str | None = None,
) -> ValidacaoPublicaOut | None:
    """Valida uma assinatura pelo código público. Retorna None para qualquer
    caso negativo (resposta neutra); o router mapeia para 404 `{valido:false}`."""
    codigo = (codigo or "").strip()
    if not codigo:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None

    aa = (
        await db.execute(
            select(AssinaturaAnexo).where(
                AssinaturaAnexo.codigo_validacao == codigo,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()

    # --- validação restritiva: qualquer falha → neutro (não vaza qual) ---
    if aa is None:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None
    if aa.validacao_publica_revogada:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None
    if aa.validacao_expira_em is not None and aa.validacao_expira_em < datetime.now():
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None
    if aa.status != "assinada" or not aa.assinado:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None
    if not aa.documento_hash:  # legado sem hash não é validável publicamente
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None

    # tenant ativo
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None or not tenant.ativo:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None

    # processo OSTENSIVO no estado atual (re-check lazy do sigilo)
    proc = (
        await db.execute(
            select(Processo).where(
                Processo.id == aa.id_processo,
                Processo.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if proc is None or proc.excluido or proc.nivel_sigilo != "ostensivo":
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None

    # anexo NÃO desentranhado (vínculo ativo no processo)
    ap = (
        await db.execute(
            select(AnexoProcesso).where(
                AnexoProcesso.id_anexo == aa.id_anexo,
                AnexoProcesso.id_processo == aa.id_processo,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ap is None or ap.desentranhado_em is not None:
        await _auditar_negativa(db, tenant_id=tenant_id, ip=ip)
        return None

    # --- passou nos gates: recalcula o hash atual e compara ---
    try:
        hash_atual, _algo = await anexos_svc.hash_anexo(
            db, aa.id_anexo, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
    except Exception:  # noqa: BLE001
        hash_atual = None
    integro = hash_atual is not None and hash_atual == aa.documento_hash

    nome = (
        await db.execute(
            select(Usuario.nome)
            .join(UsuarioAssinatura, UsuarioAssinatura.id_assinante == Usuario.id)
            .where(
                UsuarioAssinatura.id == aa.id_usuario_assinatura,
                UsuarioAssinatura.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=None,
        acao="assinatura.validada_publica",
        entidade="assinatura_anexo",
        id_entidade=aa.id,
        payload={"resultado": "valido", "integro": integro, "ip": ip},
    )
    await db.commit()

    detalhe = (
        "Conteúdo íntegro — confere com o hash da assinatura."
        if integro
        else "Documento alterado após a assinatura (hash divergente)."
    )
    return ValidacaoPublicaOut(
        valido=True,
        integro=integro,
        signatario=nome,
        processo_numero=proc.numero_processo,
        assinado_em=aa.dt_assinatura,
        hash=aa.documento_hash,
        algoritmo=aa.hash_algoritmo or "sha256",
        versao_documento=aa.documento_versao,
        status="assinada",
        detalhe=detalhe,
        aviso=AVISO,
    )


async def revogar_validacao_publica(
    db: AsyncSession,
    assinatura_anexo_id: int,
    *,
    tenant_id: int,
    usuario,
    motivo: str,
) -> AssinaturaAnexo:
    """Revogação MANUAL do código público (ação interna autenticada). A partir
    daqui o token passa a responder neutro na validação pública. Respeita o
    sigilo do processo (SigiloAcessoError → 404)."""
    aa = (
        await db.execute(
            select(AssinaturaAnexo).where(
                AssinaturaAnexo.id == assinatura_anexo_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if aa is None:
        raise ValidacaoPublicaError("Assinatura não encontrada")
    await assert_acesso_processo(
        db, tenant_id=tenant_id, processo_id=aa.id_processo, usuario=usuario
    )

    aa.validacao_publica_revogada = True
    aa.validacao_revogada_motivo = motivo
    aa.validacao_revogada_em = datetime.now()
    aa.validacao_revogada_por = usuario.id

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario.id,
        acao="assinatura.validacao_publica_revogada",
        entidade="assinatura_anexo",
        id_entidade=aa.id,
        payload={"id_processo": aa.id_processo, "motivo": motivo},
    )
    await db.commit()
    await db.refresh(aa)
    return aa

"""Solicitação e execução de assinaturas internas.

Modelo (espelha o PHP):
- solicitacao_assinatura: cabeçalho (processo + solicitante).
- usuario_assinatura: cada destinatário (1+) da solicitação.
- assinatura_anexo: cada par (destinatário × anexo); é onde o "assinado"
  efetivamente é registrado.

Fase 13a: todas as funções recebem `tenant_id` e propagam.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import verify_password
from .audit import log as audit_log
from . import anexos as anexos_svc
from . import assinatura_throttle as throttle
from ..models import (
    Anexo,
    AnexoProcesso,
    AssinaturaAnexo,
    Processo,
    SolicitacaoAssinatura,
    UsuarioAssinatura,
    Usuario,
)
from ..schemas.assinatura import (
    AssinanteStatus,
    AssinaturaAnexoStatus,
    EvidenciasOut,
    PendenciaAssinatura,
    SolicitacaoOut,
    SolicitarAssinaturaRequest,
    ValidacaoOut,
)


class AssinaturaError(Exception):
    pass


class AssinaturaThrottleError(AssinaturaError):
    """Excesso de tentativas malsucedidas — bloqueio temporário (HTTP 429)."""


class AssinaturaCredencialLegadaError(AssinaturaError):
    """Senha só valida por MD5 — não pode originar assinatura nova (HTTP 409)."""


async def _carregar_processo(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id,
                Processo.tenant_id == tenant_id,
                Processo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if p is None:
        raise AssinaturaError("Processo não encontrado")
    if not p.ativo:
        raise AssinaturaError("Processo inativo — não permite nova solicitação")
    return p


async def solicitar_assinatura(
    db: AsyncSession,
    processo_id: int,
    payload: SolicitarAssinaturaRequest,
    *,
    tenant_id: int,
    usuario_id: int,
    unidade_solicitante_id: int | None,
) -> SolicitacaoAssinatura:
    processo = await _carregar_processo(db, processo_id, tenant_id)

    assinantes = (
        await db.execute(
            select(Usuario).where(
                Usuario.id.in_(payload.id_assinantes),
                Usuario.tenant_id == tenant_id,
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalars().all()
    if len(assinantes) != len(set(payload.id_assinantes)):
        raise AssinaturaError("Algum assinante não foi encontrado ou está inativo")

    vinculo_rows = (
        await db.execute(
            select(AnexoProcesso, Anexo)
            .join(Anexo, Anexo.id == AnexoProcesso.id_anexo)
            .where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.id_anexo.in_(payload.id_anexos),
                AnexoProcesso.excluido.is_(False),
                Anexo.tenant_id == tenant_id,
                Anexo.excluido.is_(False),
                Anexo.ativo.is_(True),
            )
        )
    ).all()
    achados_ids = {a.id for _, a in vinculo_rows}
    faltando = set(payload.id_anexos) - achados_ids
    if faltando:
        raise AssinaturaError(
            f"Anexos {sorted(faltando)} não pertencem ao processo ou estão excluídos"
        )

    now = datetime.now()
    solicitacao = SolicitacaoAssinatura(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_solicitante=usuario_id,
        id_usuario=usuario_id,
        id_unidade_solicitante=unidade_solicitante_id,
        dt_inicio=now,
        realizada=False,
        cancelada=False,
        ativo=True,
        excluido=False,
    )
    db.add(solicitacao)
    await db.flush()

    for ordem, id_assin in enumerate(payload.id_assinantes, start=1):
        assinante = next(a for a in assinantes if a.id == id_assin)
        ua = UsuarioAssinatura(
            tenant_id=tenant_id,
            id_solicitacao_assinatura=solicitacao.id,
            id_assinante=id_assin,
            id_tipo_assinatura=payload.id_tipo_assinatura,
            id_unidade_trabalho=assinante.id_unidade_trabalho or processo.id_unidade_proprietaria,
            ordem=ordem,
            id_usuario=usuario_id,
            ativo=True,
            excluido=False,
            realizada=False,
        )
        db.add(ua)
        await db.flush()
        for id_anexo in payload.id_anexos:
            db.add(
                AssinaturaAnexo(
                    tenant_id=tenant_id,
                    id_usuario_assinatura=ua.id,
                    id_anexo=id_anexo,
                    assinado=False,
                    id_usuario=usuario_id,
                    id_processo=processo_id,
                    ativo=True,
                    excluido=False,
                )
            )

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.solicitada",
        entidade="solicitacao_assinatura",
        id_entidade=solicitacao.id,
        payload={
            "id_processo": processo_id,
            "id_assinantes": list(payload.id_assinantes),
            "id_anexos": list(payload.id_anexos),
        },
    )

    await db.commit()
    await db.refresh(solicitacao)
    return solicitacao


async def assinar(
    db: AsyncSession,
    assinatura_anexo_id: int,
    *,
    tenant_id: int,
    usuario_id: int,
    senha: str,
    tenant_slug: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AssinaturaAnexo:
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
        raise AssinaturaError("Assinatura não encontrada")
    if aa.assinado or aa.status == "assinada":
        raise AssinaturaError("Anexo já foi assinado")
    if aa.status in ("recusada", "cancelada"):
        raise AssinaturaError("Solicitação recusada/cancelada — não pode ser assinada")

    ua = (
        await db.execute(
            select(UsuarioAssinatura).where(
                UsuarioAssinatura.id == aa.id_usuario_assinatura,
                UsuarioAssinatura.tenant_id == tenant_id,
            )
        )
    ).scalar_one()
    if ua.id_assinante != usuario_id:
        raise AssinaturaError("Você não é o destinatário desta solicitação")

    # Throttle (fail-open) — bloqueio temporário após excesso de tentativas.
    if await throttle.esta_bloqueado(tenant_id, usuario_id, aa.id):
        raise AssinaturaThrottleError(
            "Muitas tentativas malsucedidas. Tente novamente em alguns minutos."
        )

    usuario = (
        await db.execute(
            select(Usuario).where(
                Usuario.id == usuario_id, Usuario.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    ok, needs_rehash = verify_password(
        senha, bcrypt_hash=usuario.senha_bcrypt, md5_hash=usuario.senha
    )
    if not ok:
        total = await throttle.registrar_falha(tenant_id, usuario_id, aa.id)
        # Tentativa falha auditada em commit próprio (só houve SELECTs até aqui).
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="assinatura.tentativa_falha",
            entidade="assinatura_anexo",
            id_entidade=aa.id,
            payload={"id_processo": aa.id_processo, "tentativa": total},
        )
        await db.commit()
        raise AssinaturaError("Senha incorreta")
    if needs_rehash:
        # Decisão: assinatura nova não nasce vinculada a credencial legada MD5.
        raise AssinaturaCredencialLegadaError(
            "Sua senha precisa ser atualizada para assinar. Faça login novamente "
            "ou altere a senha no seu perfil e tente de novo."
        )

    # Integridade: SHA-256 do conteúdo exato do anexo neste instante.
    documento_hash, hash_algoritmo = await anexos_svc.hash_anexo(
        db, aa.id_anexo, tenant_id=tenant_id, tenant_slug=tenant_slug
    )

    now = datetime.now()
    aa.assinado = True
    aa.dt_assinatura = now
    aa.id_usuario = usuario_id
    aa.status = "assinada"
    aa.nivel_assinatura = "simples"
    aa.metodo_autenticacao = "senha_bcrypt"
    aa.documento_hash = documento_hash
    aa.hash_algoritmo = hash_algoritmo
    aa.documento_versao = aa.documento_versao or 1
    aa.ip_assinatura = ip
    aa.user_agent_assinatura = user_agent[:512] if user_agent else None
    aa.evidencias = {
        "ip": ip,
        "user_agent": user_agent,
        "metodo_autenticacao": "senha_bcrypt",
        "documento_hash": documento_hash,
        "hash_algoritmo": hash_algoritmo,
        "dt_assinatura": now.isoformat(),
    }

    pendentes_user = (
        await db.execute(
            select(AssinaturaAnexo).where(
                AssinaturaAnexo.id_usuario_assinatura == ua.id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.excluido.is_(False),
                and_(
                    AssinaturaAnexo.id != aa.id,
                    AssinaturaAnexo.assinado.is_not(True),
                ),
            )
        )
    ).scalars().all()
    if not pendentes_user:
        ua.realizada = True
        ua.status = "realizada"

        solic = (
            await db.execute(
                select(SolicitacaoAssinatura).where(
                    SolicitacaoAssinatura.id == ua.id_solicitacao_assinatura,
                    SolicitacaoAssinatura.tenant_id == tenant_id,
                )
            )
        ).scalar_one()
        pendentes_solic = (
            await db.execute(
                select(UsuarioAssinatura).where(
                    UsuarioAssinatura.id_solicitacao_assinatura == solic.id,
                    UsuarioAssinatura.tenant_id == tenant_id,
                    UsuarioAssinatura.excluido.is_(False),
                    UsuarioAssinatura.realizada.is_(False),
                    UsuarioAssinatura.id != ua.id,
                )
            )
        ).scalars().all()
        if not pendentes_solic:
            solic.realizada = True
            solic.dt_fim = datetime.now()

    audit_id = await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.assinada",
        entidade="assinatura_anexo",
        id_entidade=aa.id,
        payload={
            "id_processo": aa.id_processo,
            "id_anexo": aa.id_anexo,
            "id_usuario_assinatura": aa.id_usuario_assinatura,
            "documento_hash": documento_hash,
            "hash_algoritmo": hash_algoritmo,
            "nivel": "simples",
            "metodo": "senha_bcrypt",
        },
    )
    aa.id_audit_log = audit_id

    await db.commit()
    await throttle.limpar(tenant_id, usuario_id, aa.id)
    await db.refresh(aa)
    return aa


async def cancelar_solicitacao(
    db: AsyncSession,
    solicitacao_id: int,
    *,
    tenant_id: int,
    usuario_id: int,
) -> SolicitacaoAssinatura:
    solic = (
        await db.execute(
            select(SolicitacaoAssinatura).where(
                SolicitacaoAssinatura.id == solicitacao_id,
                SolicitacaoAssinatura.tenant_id == tenant_id,
                SolicitacaoAssinatura.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if solic is None:
        raise AssinaturaError("Solicitação não encontrada")
    if solic.realizada:
        raise AssinaturaError("Solicitação já realizada — não pode ser cancelada")
    if solic.cancelada:
        raise AssinaturaError("Solicitação já cancelada")
    if usuario_id != solic.id_solicitante and usuario_id != solic.id_usuario:
        raise AssinaturaError("Apenas o solicitante pode cancelar")

    solic.cancelada = True
    solic.dt_fim = datetime.now()

    # Propaga status para os anexos ainda pendentes — impede assinar depois.
    await db.execute(
        update(AssinaturaAnexo)
        .where(
            AssinaturaAnexo.tenant_id == tenant_id,
            AssinaturaAnexo.status == "pendente",
            AssinaturaAnexo.id_usuario_assinatura.in_(
                select(UsuarioAssinatura.id).where(
                    UsuarioAssinatura.id_solicitacao_assinatura == solic.id,
                    UsuarioAssinatura.tenant_id == tenant_id,
                )
            ),
        )
        .values(status="cancelada")
    )

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.cancelada",
        entidade="solicitacao_assinatura",
        id_entidade=solic.id,
        payload={"id_processo": solic.id_processo},
    )

    await db.commit()
    await db.refresh(solic)
    return solic


async def recusar_assinatura(
    db: AsyncSession,
    solicitacao_id: int,
    *,
    tenant_id: int,
    usuario_id: int,
    motivo: str,
) -> UsuarioAssinatura:
    """O signatário recusa sua participação na solicitação (com motivo)."""
    solic = (
        await db.execute(
            select(SolicitacaoAssinatura).where(
                SolicitacaoAssinatura.id == solicitacao_id,
                SolicitacaoAssinatura.tenant_id == tenant_id,
                SolicitacaoAssinatura.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if solic is None:
        raise AssinaturaError("Solicitação não encontrada")
    if solic.cancelada:
        raise AssinaturaError("Solicitação cancelada")
    if solic.realizada:
        raise AssinaturaError("Solicitação já concluída")

    ua = (
        await db.execute(
            select(UsuarioAssinatura).where(
                UsuarioAssinatura.id_solicitacao_assinatura == solicitacao_id,
                UsuarioAssinatura.id_assinante == usuario_id,
                UsuarioAssinatura.tenant_id == tenant_id,
                UsuarioAssinatura.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if ua is None:
        raise AssinaturaError("Você não é signatário desta solicitação")
    if ua.realizada or ua.status == "realizada":
        raise AssinaturaError("Você já assinou — não é possível recusar")
    if ua.status == "recusada":
        raise AssinaturaError("Você já recusou esta solicitação")

    now = datetime.now()
    ua.status = "recusada"
    ua.motivo_recusa = motivo
    ua.dt_recusa = now

    await db.execute(
        update(AssinaturaAnexo)
        .where(
            AssinaturaAnexo.id_usuario_assinatura == ua.id,
            AssinaturaAnexo.tenant_id == tenant_id,
            AssinaturaAnexo.status == "pendente",
        )
        .values(status="recusada", motivo=motivo)
    )

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.recusada",
        entidade="usuario_assinatura",
        id_entidade=ua.id,
        payload={
            "id_solicitacao": solicitacao_id,
            "id_processo": solic.id_processo,
            "motivo": motivo,
        },
    )

    await db.commit()
    await db.refresh(ua)
    return ua


async def validar_assinatura(
    db: AsyncSession,
    assinatura_anexo_id: int,
    *,
    tenant_id: int,
    tenant_slug: str,
    usuario_id: int | None = None,
) -> ValidacaoOut:
    """Recalcula o hash do arquivo atual e compara com o registrado. Auditada
    on-demand (esta chamada É uma validação explícita)."""
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
        raise AssinaturaError("Assinatura não encontrada")

    legado = aa.nivel_assinatura == "legado" or not aa.documento_hash
    integro: bool | None
    hash_atual: str | None = None
    if legado:
        integro = None
        detalhe = "Assinatura legada — sem hash de integridade registrado."
    else:
        try:
            hash_atual, _algo = await anexos_svc.hash_anexo(
                db, aa.id_anexo, tenant_id=tenant_id, tenant_slug=tenant_slug
            )
        except Exception:  # noqa: BLE001
            hash_atual = None
        integro = hash_atual is not None and hash_atual == aa.documento_hash
        detalhe = (
            "Conteúdo íntegro — confere com o hash da assinatura."
            if integro
            else "Conteúdo divergente do hash assinado (documento alterado ou arquivo ausente)."
        )

    await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.validada",
        entidade="assinatura_anexo",
        id_entidade=aa.id,
        payload={"integro": integro, "legado": legado},
    )
    await db.commit()

    return ValidacaoOut(
        id_assinatura_anexo=aa.id,
        legado=legado,
        integro=integro,
        nivel=aa.nivel_assinatura,
        status=aa.status,
        documento_hash=aa.documento_hash,
        hash_atual=hash_atual,
        dt_assinatura=aa.dt_assinatura,
        detalhe=detalhe,
    )


async def consultar_evidencias(
    db: AsyncSession, assinatura_anexo_id: int, *, tenant_id: int
) -> EvidenciasOut:
    row = (
        await db.execute(
            select(AssinaturaAnexo, UsuarioAssinatura.id_assinante, Usuario.nome)
            .join(
                UsuarioAssinatura,
                UsuarioAssinatura.id == AssinaturaAnexo.id_usuario_assinatura,
            )
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante, isouter=True)
            .where(
                AssinaturaAnexo.id == assinatura_anexo_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).first()
    if row is None:
        raise AssinaturaError("Assinatura não encontrada")
    aa, _id_assinante, nome = row
    return EvidenciasOut(
        id_assinatura_anexo=aa.id,
        id_anexo=aa.id_anexo,
        id_processo=aa.id_processo,
        nome_assinante=nome,
        nivel=aa.nivel_assinatura,
        status=aa.status,
        metodo_autenticacao=aa.metodo_autenticacao,
        documento_hash=aa.documento_hash,
        hash_algoritmo=aa.hash_algoritmo,
        documento_versao=aa.documento_versao,
        ip_assinatura=aa.ip_assinatura,
        user_agent_assinatura=aa.user_agent_assinatura,
        dt_assinatura=aa.dt_assinatura,
        id_audit_log=aa.id_audit_log,
        evidencias=aa.evidencias,
    )


# ---------- Queries ----------

async def _hidratar_solicitacao(
    db: AsyncSession, solic: SolicitacaoAssinatura, tenant_id: int
) -> SolicitacaoOut:
    solicitante_nome = (
        await db.execute(
            select(Usuario.nome).where(
                Usuario.id == solic.id_solicitante, Usuario.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    numero_processo = (
        await db.execute(
            select(Processo.numero_processo).where(
                Processo.id == solic.id_processo, Processo.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()

    uas = (
        await db.execute(
            select(UsuarioAssinatura, Usuario.nome)
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante, isouter=True)
            .where(
                UsuarioAssinatura.id_solicitacao_assinatura == solic.id,
                UsuarioAssinatura.tenant_id == tenant_id,
                UsuarioAssinatura.excluido.is_(False),
            )
            .order_by(UsuarioAssinatura.ordem)
        )
    ).all()

    out_assinantes: list[AssinanteStatus] = []
    for ua, nome_assin in uas:
        anex_rows = (
            await db.execute(
                select(AssinaturaAnexo, Anexo.descricao)
                .join(Anexo, Anexo.id == AssinaturaAnexo.id_anexo)
                .where(
                    AssinaturaAnexo.id_usuario_assinatura == ua.id,
                    AssinaturaAnexo.tenant_id == tenant_id,
                    AssinaturaAnexo.excluido.is_(False),
                )
                .order_by(AssinaturaAnexo.id)
            )
        ).all()
        anexos_out = [
            AssinaturaAnexoStatus(
                id=aa.id,
                id_anexo=aa.id_anexo,
                anexo_descricao=desc,
                assinado=bool(aa.assinado),
                dt_assinatura=aa.dt_assinatura,
                status=aa.status,
                nivel=aa.nivel_assinatura,
                tem_hash=bool(aa.documento_hash),
            )
            for aa, desc in anex_rows
        ]
        out_assinantes.append(
            AssinanteStatus(
                id_usuario_assinatura=ua.id,
                id_assinante=ua.id_assinante,
                nome_assinante=nome_assin,
                realizada=ua.realizada,
                ordem=ua.ordem,
                status=ua.status,
                motivo_recusa=ua.motivo_recusa,
                anexos=anexos_out,
            )
        )

    return SolicitacaoOut(
        id=solic.id,
        id_processo=solic.id_processo,
        numero_processo=numero_processo,
        id_solicitante=solic.id_solicitante,
        nome_solicitante=solicitante_nome,
        realizada=solic.realizada,
        cancelada=solic.cancelada,
        dt_inicio=solic.dt_inicio,
        dt_fim=solic.dt_fim,
        assinantes=out_assinantes,
    )


async def listar_do_processo(
    db: AsyncSession, processo_id: int, *, tenant_id: int
) -> list[SolicitacaoOut]:
    rows = (
        await db.execute(
            select(SolicitacaoAssinatura)
            .where(
                SolicitacaoAssinatura.id_processo == processo_id,
                SolicitacaoAssinatura.tenant_id == tenant_id,
                SolicitacaoAssinatura.excluido.is_(False),
            )
            .order_by(SolicitacaoAssinatura.id.desc())
        )
    ).scalars().all()
    return [await _hidratar_solicitacao(db, s, tenant_id) for s in rows]


async def listar_minhas_pendentes(
    db: AsyncSession, usuario_id: int, *, tenant_id: int
) -> list[PendenciaAssinatura]:
    rows = (
        await db.execute(
            select(
                AssinaturaAnexo,
                Anexo.descricao,
                SolicitacaoAssinatura,
                Processo.numero_processo,
                Usuario.nome,
            )
            .join(UsuarioAssinatura, UsuarioAssinatura.id == AssinaturaAnexo.id_usuario_assinatura)
            .join(SolicitacaoAssinatura, SolicitacaoAssinatura.id == UsuarioAssinatura.id_solicitacao_assinatura)
            .join(Processo, Processo.id == SolicitacaoAssinatura.id_processo)
            .join(Anexo, Anexo.id == AssinaturaAnexo.id_anexo)
            .join(Usuario, Usuario.id == SolicitacaoAssinatura.id_solicitante, isouter=True)
            .where(
                UsuarioAssinatura.id_assinante == usuario_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.assinado.is_not(True),
                AssinaturaAnexo.excluido.is_(False),
                SolicitacaoAssinatura.cancelada.is_(False),
                SolicitacaoAssinatura.excluido.is_(False),
            )
            .order_by(SolicitacaoAssinatura.dt_inicio.desc(), AssinaturaAnexo.id)
        )
    ).all()
    return [
        PendenciaAssinatura(
            id_assinatura_anexo=aa.id,
            id_anexo=aa.id_anexo,
            anexo_descricao=desc,
            id_solicitacao=solic.id,
            id_processo=solic.id_processo,
            numero_processo=numero,
            nome_solicitante=nome,
            dt_inicio=solic.dt_inicio,
        )
        for aa, desc, solic, numero, nome in rows
    ]

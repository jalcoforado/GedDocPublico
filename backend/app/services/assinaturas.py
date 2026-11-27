"""Solicitação e execução de assinaturas internas.

Modelo (espelha o PHP):
- solicitacao_assinatura: cabeçalho (processo + solicitante).
- usuario_assinatura: cada destinatário (1+) da solicitação.
- assinatura_anexo: cada par (destinatário × anexo); é onde o "assinado"
  efetivamente é registrado.

Fase 13a: todas as funções recebem `tenant_id` e propagam.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import verify_password
from ..config import validacao_publica_url
from .audit import log as audit_log
from . import anexos as anexos_svc
from . import assinatura_throttle as throttle
from .pdf_selo_assinatura import SeloError, contar_paginas_pdf
from .sigilo import assert_acesso_processo
from .storage import obter_storage
from .validacao_publica import status_validacao_publica
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
    PosicaoSelo,
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


def _registrar_assinatura_com_senha(
    aa: AssinaturaAnexo,
    *,
    usuario_id: int,
    documento_hash: str,
    hash_algoritmo: str,
    ip: str | None,
    user_agent: str | None,
    posicao: PosicaoSelo | None = None,
) -> None:
    """Marca `aa` como assinada por senha, com as evidências de integridade.
    Comum a `assinar` (pedido a outra pessoa) e `autoassinar_sem_commit`
    (despacho, SI-62): as duas assinaturas têm de ser indistinguíveis na
    validação pública.

    `posicao` (SI-68) é onde o selo aparece no PDF servido. O despacho não
    passa posição e continua sem selo, como antes."""
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
    # Token público de validação (PR2e): opaco, ~128 bits, não-enumerável.
    aa.codigo_validacao = secrets.token_urlsafe(16)
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
    if posicao is not None:
        aa.selo_pagina = posicao.pagina
        aa.selo_x = posicao.x
        aa.selo_y = posicao.y
        aa.evidencias["posicao_selo"] = posicao.model_dump()


async def _validar_posicao_selo(
    db: AsyncSession,
    anexo_id: int,
    posicao: PosicaoSelo,
    *,
    tenant_id: int,
    tenant_slug: str,
) -> None:
    """Selo só em PDF, e numa página que existe. A faixa 0–1 de x/y o schema
    já garantiu; manter o quadrado inteiro dentro da página é do desenho."""
    try:
        anexo, _path = await anexos_svc.get_anexo_path(
            db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
        )
        conteudo = await obter_storage().get_bytes(tenant_slug, anexo.e_doc)
    except (anexos_svc.AnexoError, FileNotFoundError) as e:
        raise AssinaturaError("Arquivo do documento não encontrado") from e
    if not anexo.e_doc.lower().endswith(".pdf"):
        raise AssinaturaError("A posição da assinatura só vale para documento PDF")
    try:
        total = contar_paginas_pdf(conteudo)
    except SeloError as e:
        raise AssinaturaError("Não foi possível ler o PDF para posicionar a assinatura") from e
    if posicao.pagina > total:
        raise AssinaturaError(
            f"O documento tem {total} página(s); escolha uma delas para a assinatura"
        )


async def conferir_senha_para_assinar(
    db: AsyncSession,
    *,
    tenant_id: int,
    usuario_id: int,
    senha: str,
    chave_throttle: int,
    entidade: str,
    id_entidade: int,
    id_processo: int,
) -> None:
    """Confere a senha com as MESMAS regras de `assinar`: bloqueio temporário
    por excesso de tentativas, tentativa errada auditada (em commit próprio —
    quem chama ainda não gravou nada) e recusa de credencial só-MD5.

    `chave_throttle` separa os contadores de tentativa; no despacho (SI-62) é
    o id da minuta com sinal trocado, para nunca coincidir com um anexo."""
    if await throttle.esta_bloqueado(tenant_id, usuario_id, chave_throttle):
        raise AssinaturaThrottleError(
            "Muitas tentativas malsucedidas. Tente novamente em alguns minutos."
        )
    usuario = (
        await db.execute(
            select(Usuario).where(Usuario.id == usuario_id, Usuario.tenant_id == tenant_id)
        )
    ).scalar_one()
    ok, needs_rehash = verify_password(
        senha, bcrypt_hash=usuario.senha_bcrypt, md5_hash=usuario.senha
    )
    if not ok:
        total = await throttle.registrar_falha(tenant_id, usuario_id, chave_throttle)
        await audit_log(
            db,
            tenant_id=tenant_id,
            id_usuario=usuario_id,
            acao="assinatura.tentativa_falha",
            entidade=entidade,
            id_entidade=id_entidade,
            payload={"id_processo": id_processo, "tentativa": total},
        )
        await db.commit()
        raise AssinaturaError("Senha incorreta")
    if needs_rehash:
        raise AssinaturaCredencialLegadaError(
            "Para assinar documentos, sua senha precisa ser atualizada para o "
            "padrão atual de segurança. Saia do sistema e faça login novamente. "
            "Se o bloqueio continuar, altere sua senha no perfil ou solicite suporte."
        )
    await throttle.limpar(tenant_id, usuario_id, chave_throttle)


async def autoassinar_sem_commit(
    db: AsyncSession,
    *,
    tenant_id: int,
    tenant_slug: str,
    processo_id: int,
    anexo_id: int,
    usuario_id: int,
    id_unidade: int,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AssinaturaAnexo:
    """O autor assina o próprio documento (despacho, SI-62). A senha JÁ foi
    conferida por `conferir_senha_para_assinar`. Grava a mesma trilha de uma
    assinatura pedida — solicitação, destinatário e assinatura, todos já
    realizados — para o documento aparecer como assinado e passar na
    validação pública como qualquer outro. Sem commit."""
    now = datetime.now()
    solicitacao = SolicitacaoAssinatura(
        tenant_id=tenant_id,
        id_processo=processo_id,
        id_solicitante=usuario_id,
        id_usuario=usuario_id,
        id_unidade_solicitante=id_unidade,
        dt_inicio=now,
        dt_fim=now,
        realizada=True,
        cancelada=False,
        ativo=True,
        excluido=False,
    )
    db.add(solicitacao)
    await db.flush()
    ua = UsuarioAssinatura(
        tenant_id=tenant_id,
        id_solicitacao_assinatura=solicitacao.id,
        id_assinante=usuario_id,
        id_tipo_assinatura=None,
        id_unidade_trabalho=id_unidade,
        ordem=1,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
        realizada=True,
        status="realizada",
    )
    db.add(ua)
    await db.flush()

    documento_hash, hash_algoritmo = await anexos_svc.hash_anexo(
        db, anexo_id, tenant_id=tenant_id, tenant_slug=tenant_slug
    )
    aa = AssinaturaAnexo(
        tenant_id=tenant_id,
        id_usuario_assinatura=ua.id,
        id_anexo=anexo_id,
        id_processo=processo_id,
        id_usuario=usuario_id,
        ativo=True,
        excluido=False,
    )
    _registrar_assinatura_com_senha(
        aa,
        usuario_id=usuario_id,
        documento_hash=documento_hash,
        hash_algoritmo=hash_algoritmo,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(aa)
    await db.flush()
    aa.id_audit_log = await audit_log(
        db,
        tenant_id=tenant_id,
        id_usuario=usuario_id,
        acao="assinatura.assinada",
        entidade="assinatura_anexo",
        id_entidade=aa.id,
        payload={
            "id_processo": processo_id,
            "id_anexo": anexo_id,
            "id_usuario_assinatura": ua.id,
            "documento_hash": documento_hash,
            "hash_algoritmo": hash_algoritmo,
            "nivel": "simples",
            "metodo": "senha_bcrypt",
            "origem": "despacho",
        },
    )
    return aa


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
    posicao: PosicaoSelo | None = None,
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

    # Posição inválida volta antes da senha: não gasta tentativa do throttle.
    if posicao is not None:
        await _validar_posicao_selo(
            db, aa.id_anexo, posicao, tenant_id=tenant_id, tenant_slug=tenant_slug
        )

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
            "Para assinar documentos, sua senha precisa ser atualizada para o "
            "padrão atual de segurança. Saia do sistema e faça login novamente. "
            "Se o bloqueio continuar, altere sua senha no perfil ou solicite suporte."
        )

    # Integridade: SHA-256 do conteúdo exato do anexo neste instante.
    documento_hash, hash_algoritmo = await anexos_svc.hash_anexo(
        db, aa.id_anexo, tenant_id=tenant_id, tenant_slug=tenant_slug
    )

    _registrar_assinatura_com_senha(
        aa,
        usuario_id=usuario_id,
        documento_hash=documento_hash,
        hash_algoritmo=hash_algoritmo,
        ip=ip,
        user_agent=user_agent,
        posicao=posicao,
    )

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
            "posicao_selo": posicao.model_dump() if posicao is not None else None,
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
    usuario,
) -> ValidacaoOut:
    """Recalcula o hash do arquivo atual e compara com o registrado. Auditada
    on-demand (esta chamada É uma validação explícita). Respeita o sigilo do
    processo: levanta SigiloAcessoError (→404) se o usuário não tem acesso."""
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
    await assert_acesso_processo(
        db, tenant_id=tenant_id, processo_id=aa.id_processo, usuario=usuario
    )

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
        id_usuario=usuario.id,
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
    db: AsyncSession,
    assinatura_anexo_id: int,
    *,
    tenant_id: int,
    usuario,
    tenant_slug: str | None = None,
) -> EvidenciasOut:
    row = (
        await db.execute(
            select(
                AssinaturaAnexo,
                Usuario.nome,
                Anexo.descricao,
                Processo.numero_processo,
                Processo.nivel_sigilo,
                Processo.excluido,
            )
            .join(
                UsuarioAssinatura,
                UsuarioAssinatura.id == AssinaturaAnexo.id_usuario_assinatura,
            )
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante, isouter=True)
            .join(Anexo, Anexo.id == AssinaturaAnexo.id_anexo, isouter=True)
            .join(Processo, Processo.id == AssinaturaAnexo.id_processo, isouter=True)
            .where(
                AssinaturaAnexo.id == assinatura_anexo_id,
                AssinaturaAnexo.tenant_id == tenant_id,
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).first()
    if row is None:
        raise AssinaturaError("Assinatura não encontrada")
    aa, nome, anexo_descricao, numero_processo, nivel_sigilo, processo_excluido = row
    await assert_acesso_processo(
        db, tenant_id=tenant_id, processo_id=aa.id_processo, usuario=usuario
    )

    # Validação pública (PR2f): status pela fonte única + URL (se houver código).
    ap_desentranhado_em = (
        await db.execute(
            select(AnexoProcesso.desentranhado_em).where(
                AnexoProcesso.id_anexo == aa.id_anexo,
                AnexoProcesso.id_processo == aa.id_processo,
                AnexoProcesso.tenant_id == tenant_id,
                AnexoProcesso.excluido.is_(False),
            )
        )
    ).first()
    vp_status = status_validacao_publica(
        codigo_validacao=aa.codigo_validacao,
        documento_hash=aa.documento_hash,
        assinado=aa.assinado,
        status_assinatura=aa.status,
        validacao_publica_revogada=aa.validacao_publica_revogada,
        nivel_sigilo=(nivel_sigilo if not processo_excluido else None),
        anexo_desentranhado=(ap_desentranhado_em is None or ap_desentranhado_em[0] is not None),
        validacao_expira_em=aa.validacao_expira_em,
    )
    vp_url = (
        validacao_publica_url(tenant_slug, aa.codigo_validacao)
        if tenant_slug and aa.codigo_validacao
        else None
    )
    return EvidenciasOut(
        id_assinatura_anexo=aa.id,
        id_anexo=aa.id_anexo,
        id_processo=aa.id_processo,
        numero_processo=numero_processo,
        anexo_descricao=anexo_descricao,
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
        codigo_validacao=aa.codigo_validacao,
        validacao_publica_url=vp_url,
        validacao_publica_status=vp_status,
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
                Anexo.e_doc,
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
            anexo_pdf=bool(e_doc and e_doc.lower().endswith(".pdf")),
        )
        for aa, desc, solic, numero, nome, e_doc in rows
    ]

"""Solicitação e execução de assinaturas internas.

Modelo (espelha o PHP):
- solicitacao_assinatura: cabeçalho (processo + solicitante).
- usuario_assinatura: cada destinatário (1+) da solicitação.
- assinatura_anexo: cada par (destinatário × anexo); é onde o "assinado"
  efetivamente é registrado.

Regras:
- Validação da senha do usuário no momento de assinar (MD5, igual ao PHP).
- `usuario_assinatura.realizada` vira true quando todos os anexos daquele
  destinatário estão assinados.
- `solicitacao_assinatura.realizada` vira true quando TODOS os destinatários
  realizaram. Dispara `dt_fim`.
- Cancelar: só o solicitante OU o usuário que criou. Não permite cancelar
  solicitação já realizada.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import verify_md5
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
    PendenciaAssinatura,
    SolicitacaoOut,
    SolicitarAssinaturaRequest,
)


class AssinaturaError(Exception):
    pass


async def _carregar_processo(db: AsyncSession, processo_id: int) -> Processo:
    p = (
        await db.execute(
            select(Processo).where(
                Processo.id == processo_id, Processo.excluido.is_(False)
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
    usuario_id: int,
    unidade_solicitante_id: int | None,
) -> SolicitacaoAssinatura:
    processo = await _carregar_processo(db, processo_id)

    # Valida assinantes existem.
    assinantes = (
        await db.execute(
            select(Usuario).where(
                Usuario.id.in_(payload.id_assinantes),
                Usuario.excluido.is_(False),
                Usuario.ativo.is_(True),
            )
        )
    ).scalars().all()
    if len(assinantes) != len(set(payload.id_assinantes)):
        raise AssinaturaError("Algum assinante não foi encontrado ou está inativo")

    # Valida anexos pertencem ao processo e estão ativos.
    vinculo_rows = (
        await db.execute(
            select(AnexoProcesso, Anexo)
            .join(Anexo, Anexo.id == AnexoProcesso.id_anexo)
            .where(
                AnexoProcesso.id_processo == processo_id,
                AnexoProcesso.id_anexo.in_(payload.id_anexos),
                AnexoProcesso.excluido.is_(False),
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

    # Cria 1 usuario_assinatura por assinante; ordem por posição no array recebido.
    for ordem, id_assin in enumerate(payload.id_assinantes, start=1):
        assinante = next(a for a in assinantes if a.id == id_assin)
        ua = UsuarioAssinatura(
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
        # E 1 assinatura_anexo por anexo, pendente.
        for id_anexo in payload.id_anexos:
            db.add(
                AssinaturaAnexo(
                    id_usuario_assinatura=ua.id,
                    id_anexo=id_anexo,
                    assinado=False,
                    id_usuario=usuario_id,
                    id_processo=processo_id,
                    ativo=True,
                    excluido=False,
                )
            )

    await db.commit()
    await db.refresh(solicitacao)
    return solicitacao


async def assinar(
    db: AsyncSession,
    assinatura_anexo_id: int,
    *,
    usuario_id: int,
    senha: str,
) -> AssinaturaAnexo:
    aa = (
        await db.execute(
            select(AssinaturaAnexo).where(
                AssinaturaAnexo.id == assinatura_anexo_id,
                AssinaturaAnexo.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if aa is None:
        raise AssinaturaError("Assinatura não encontrada")
    if aa.assinado:
        raise AssinaturaError("Anexo já foi assinado")

    ua = (
        await db.execute(
            select(UsuarioAssinatura).where(UsuarioAssinatura.id == aa.id_usuario_assinatura)
        )
    ).scalar_one()
    if ua.id_assinante != usuario_id:
        raise AssinaturaError("Você não é o destinatário desta solicitação")

    # Valida a senha (MD5) do usuário corrente.
    usuario = (
        await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    ).scalar_one()
    if not verify_md5(senha, usuario.senha):
        raise AssinaturaError("Senha incorreta")

    aa.assinado = True
    aa.dt_assinatura = datetime.now()
    aa.id_usuario = usuario_id

    # Marca usuario_assinatura como realizada se todos anexos dele estão assinados.
    pendentes_user = (
        await db.execute(
            select(AssinaturaAnexo).where(
                AssinaturaAnexo.id_usuario_assinatura == ua.id,
                AssinaturaAnexo.excluido.is_(False),
                and_(
                    AssinaturaAnexo.id != aa.id,  # esse aqui acabou de assinar
                    AssinaturaAnexo.assinado.is_not(True),
                ),
            )
        )
    ).scalars().all()
    if not pendentes_user:
        ua.realizada = True

        # Promove solicitação se todos os destinatários realizaram.
        solic = (
            await db.execute(
                select(SolicitacaoAssinatura).where(
                    SolicitacaoAssinatura.id == ua.id_solicitacao_assinatura
                )
            )
        ).scalar_one()
        pendentes_solic = (
            await db.execute(
                select(UsuarioAssinatura).where(
                    UsuarioAssinatura.id_solicitacao_assinatura == solic.id,
                    UsuarioAssinatura.excluido.is_(False),
                    UsuarioAssinatura.realizada.is_(False),
                    UsuarioAssinatura.id != ua.id,
                )
            )
        ).scalars().all()
        if not pendentes_solic:
            solic.realizada = True
            solic.dt_fim = datetime.now()

    await db.commit()
    await db.refresh(aa)
    return aa


async def cancelar_solicitacao(
    db: AsyncSession,
    solicitacao_id: int,
    *,
    usuario_id: int,
) -> SolicitacaoAssinatura:
    solic = (
        await db.execute(
            select(SolicitacaoAssinatura).where(
                SolicitacaoAssinatura.id == solicitacao_id,
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
    await db.commit()
    await db.refresh(solic)
    return solic


# ---------- Queries ----------

async def _hidratar_solicitacao(
    db: AsyncSession, solic: SolicitacaoAssinatura
) -> SolicitacaoOut:
    # Solicitante + processo
    solicitante_nome = (
        await db.execute(
            select(Usuario.nome).where(Usuario.id == solic.id_solicitante)
        )
    ).scalar_one_or_none()
    numero_processo = (
        await db.execute(
            select(Processo.numero_processo).where(Processo.id == solic.id_processo)
        )
    ).scalar_one_or_none()

    # Assinantes + anexos
    uas = (
        await db.execute(
            select(UsuarioAssinatura, Usuario.nome)
            .join(Usuario, Usuario.id == UsuarioAssinatura.id_assinante, isouter=True)
            .where(
                UsuarioAssinatura.id_solicitacao_assinatura == solic.id,
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
    db: AsyncSession, processo_id: int
) -> list[SolicitacaoOut]:
    rows = (
        await db.execute(
            select(SolicitacaoAssinatura)
            .where(
                SolicitacaoAssinatura.id_processo == processo_id,
                SolicitacaoAssinatura.excluido.is_(False),
            )
            .order_by(SolicitacaoAssinatura.id.desc())
        )
    ).scalars().all()
    return [await _hidratar_solicitacao(db, s) for s in rows]


async def listar_minhas_pendentes(
    db: AsyncSession, usuario_id: int
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

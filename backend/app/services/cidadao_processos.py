"""Operações de processo do cidadão (usuário externo).

- listar: processos cujo manifestante tem o mesmo CPF/CNPJ do cidadão logado,
  dentro do tenant.
- detalhe: idem.
- abrir: cria/reusa Manifestante por CPF/CNPJ DENTRO do tenant; abre processo
  com `externo=true, publico=true`, sem `id_usuario`.

A unidade proprietária default vem da primeira unidade ativa do tenant — em
produção isso seria parametrizável (tabela `configuracoes`).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Acao,
    Assunto,
    Manifestante,
    Movimentacao,
    Processo,
    TipoManifestante,
    TipoProcesso,
    UnidadeTrabalho,
    UsuarioExterno,
)
from ..schemas.cidadao import (
    AbrirProcessoCidadaoRequest,
    MovimentacaoCidadaoItem,
    ProcessoCidadaoDetail,
    ProcessoCidadaoListItem,
)


class CidadaoProcessoError(Exception):
    pass


def _base_select(tenant_id: int):
    LocalAtual = aliased(UnidadeTrabalho, name="la")
    return (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_nome"),
            LocalAtual.unidade_trabalho.label("local_nome"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
        .where(Processo.excluido.is_(False), Processo.tenant_id == tenant_id)
    )


async def listar_meus(
    db: AsyncSession, cidadao: UsuarioExterno, *, tenant_id: int
) -> list[ProcessoCidadaoListItem]:
    if not cidadao.cpf_cnpj:
        return []
    stmt = (
        _base_select(tenant_id)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .where(
            Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
            Manifestante.tenant_id == tenant_id,
        )
        .order_by(Processo.data_hora_abertura.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_row_to_list(r) for r in rows]


def _row_to_list(r) -> ProcessoCidadaoListItem:
    p: Processo = r[0]
    return ProcessoCidadaoListItem(
        id=p.id,
        numero_processo=p.numero_processo,
        data_hora_abertura=p.data_hora_abertura,
        assunto=r.assunto_nome,
        tipo_processo=r.tipo_nome,
        local_atual=r.local_nome,
        ativo=p.ativo,
        publico=p.publico,
    )


async def get_meu_detail(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    processo_id: int,
    *,
    tenant_id: int,
) -> ProcessoCidadaoDetail | None:
    if not cidadao.cpf_cnpj:
        return None
    stmt = (
        _base_select(tenant_id)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .where(
            Processo.id == processo_id,
            Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
            Manifestante.tenant_id == tenant_id,
        )
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    p: Processo = row[0]
    base = _row_to_list(row)

    movs_stmt = (
        select(Movimentacao, Acao, UnidadeTrabalho)
        .join(Acao, Acao.id == Movimentacao.id_acao)
        .join(
            UnidadeTrabalho,
            UnidadeTrabalho.id == Movimentacao.id_unidade_responsavel,
            isouter=True,
        )
        .where(
            Movimentacao.id_processo == processo_id,
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.excluido.is_(False),
        )
        .order_by(Movimentacao.data_hora_movimentacao.desc())
    )
    movs = (await db.execute(movs_stmt)).all()
    movimentacoes = [
        MovimentacaoCidadaoItem(
            id=mov.id,
            data_hora_movimentacao=mov.data_hora_movimentacao,
            acao=acao.acao,
            unidade_responsavel=ut.unidade_trabalho if ut else None,
            despacho_publico=None,
        )
        for mov, acao, ut in movs
    ]
    return ProcessoCidadaoDetail(
        **base.model_dump(),
        observacao=p.observacao,
        corpo=p.corpo,
        movimentacoes=movimentacoes,
    )


async def abrir_processo_cidadao(
    db: AsyncSession,
    cidadao: UsuarioExterno,
    payload: AbrirProcessoCidadaoRequest,
    *,
    tenant_id: int,
) -> Processo:
    if not cidadao.cpf_cnpj or not cidadao.nome:
        raise CidadaoProcessoError("Cadastro do cidadão incompleto (CPF/nome)")

    assunto = (
        await db.execute(
            select(Assunto).where(
                Assunto.id == payload.id_assunto,
                Assunto.tenant_id == tenant_id,
                Assunto.ativo.is_(True),
            )
        )
    ).scalar_one_or_none()
    if assunto is None:
        raise CidadaoProcessoError("Assunto inválido")

    unidade = (
        await db.execute(
            select(UnidadeTrabalho)
            .where(
                UnidadeTrabalho.tenant_id == tenant_id,
                UnidadeTrabalho.excluido.is_(False),
            )
            .order_by(UnidadeTrabalho.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if unidade is None:
        raise CidadaoProcessoError("Nenhuma unidade configurada")

    manifestante = (
        await db.execute(
            select(Manifestante).where(
                Manifestante.cpf_cnpj == cidadao.cpf_cnpj,
                Manifestante.tenant_id == tenant_id,
                Manifestante.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()

    if manifestante is None:
        tipo_pf = (
            await db.execute(
                select(TipoManifestante)
                .where(
                    TipoManifestante.tenant_id == tenant_id,
                    TipoManifestante.ativo.is_(True),
                )
                .order_by(TipoManifestante.id)
                .limit(1)
            )
        ).scalar_one_or_none()
        if tipo_pf is None:
            raise CidadaoProcessoError("Nenhum tipo de manifestante cadastrado")
        manifestante = Manifestante(
            tenant_id=tenant_id,
            id_tipo_manifestante=tipo_pf.id,
            cpf_cnpj=cidadao.cpf_cnpj,
            nome=cidadao.nome,
            email=cidadao.email,
            telefone_celular=cidadao.telefone,
            ativo=True,
            excluido=False,
        )
        db.add(manifestante)
        await db.flush()

    numero = (
        await db.execute(text("SELECT protocolos.gerar_numero_processo_string() AS n"))
    ).first()
    if numero is None or not numero.n:
        raise CidadaoProcessoError("Falha ao gerar número de processo")
    numero_processo = numero.n

    # Acao é catálogo global — sem tenant_id.
    acao_abertura = (
        await db.execute(
            select(Acao).where(
                Acao.flag == "ABERTURA",
                Acao.ativo.is_(True),
                Acao.excluido.is_(False),
            )
        )
    ).scalar_one_or_none()
    if acao_abertura is None:
        raise CidadaoProcessoError("Ação ABERTURA não cadastrada")

    now = datetime.now()
    processo = Processo(
        tenant_id=tenant_id,
        id_assunto=payload.id_assunto,
        id_manifestante=manifestante.id,
        id_unidade_proprietaria=unidade.id,
        observacao=payload.observacao,
        corpo=payload.corpo,
        numero_processo=numero_processo,
        publico=True,
        externo=True,
        virtual=True,
        data_hora_abertura=now,
        id_local_atual=unidade.id,
        id_usuario=None,
        ativo=True,
        excluido=False,
        migrado=False,
    )
    db.add(processo)
    await db.flush()

    movimentacao = Movimentacao(
        tenant_id=tenant_id,
        id_processo=processo.id,
        id_unidade_responsavel=unidade.id,
        id_acao=acao_abertura.id,
        id_usuario=None,
        data_hora_movimentacao=now,
        ativo=True,
        excluido=False,
    )
    db.add(movimentacao)
    await db.flush()
    processo.id_ultima_movimentacao = movimentacao.id

    await db.commit()
    await db.refresh(processo)
    return processo

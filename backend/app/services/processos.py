"""Queries de processo com joins explícitos.

Trazer nomes (manifestante, assunto, unidade) numa única query evita o problema
de N+1 ao listar. Para a timeline usamos selects separados que rodam após o
detalhe — é mais simples e suficientemente rápido em escala normal de UI.

Fase 13a: todas as funções recebem `tenant_id` e filtram pelo escopo.
"""
from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..database import tenant_filter
from ..models import (
    Acao,
    Anexo,
    AnexoProcesso,
    Assunto,
    Despacho,
    Encaminhamento,
    Manifestante,
    Movimentacao,
    Prioridade,
    Processo,
    TipoAnexo,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from ..schemas.processo import (
    AnexoNoProcesso,
    DespachoOut,
    EncaminhamentoOut,
    MovimentacaoItem,
    ProcessoDetail,
    ProcessoListItem,
)


def _base_select(tenant_id: int):
    LocalAtual = aliased(UnidadeTrabalho, name="local_atual")
    stmt = (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_processo_nome"),
            Manifestante.nome.label("manifestante_nome"),
            Manifestante.cpf_cnpj.label("manifestante_cpf"),
            UnidadeTrabalho.unidade_trabalho.label("unidade_propr"),
            LocalAtual.unidade_trabalho.label("local_atual_nome"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
        .join(Manifestante, Manifestante.id == Processo.id_manifestante)
        .join(
            UnidadeTrabalho,
            UnidadeTrabalho.id == Processo.id_unidade_proprietaria,
            isouter=True,
        )
        .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
        .where(Processo.excluido.is_(False))
    )
    return tenant_filter(stmt, Processo, tenant_id)


async def list_processos(
    db: AsyncSession,
    *,
    tenant_id: int,
    page: int,
    page_size: int,
    q: str | None = None,
    id_assunto: int | None = None,
    id_manifestante: int | None = None,
    id_unidade: int | None = None,
    apenas_ativos: bool = False,
    desde: datetime | None = None,
    ate: datetime | None = None,
) -> tuple[list[ProcessoListItem], int]:
    base = _base_select(tenant_id)

    if q:
        like = f"%{q.lower()}%"
        base = base.where(
            or_(
                func.lower(Processo.numero_processo).like(like),
                func.lower(Processo.numero_origem).like(like),
                func.lower(Manifestante.nome).like(like),
                func.lower(Manifestante.cpf_cnpj).like(like),
                func.lower(Assunto.assunto).like(like),
            )
        )
    if id_assunto:
        base = base.where(Processo.id_assunto == id_assunto)
    if id_manifestante:
        base = base.where(Processo.id_manifestante == id_manifestante)
    if id_unidade:
        base = base.where(
            or_(
                Processo.id_unidade_proprietaria == id_unidade,
                Processo.id_local_atual == id_unidade,
            )
        )
    if apenas_ativos:
        base = base.where(Processo.ativo.is_(True))
    if desde:
        base = base.where(Processo.data_hora_abertura >= desde)
    if ate:
        base = base.where(Processo.data_hora_abertura <= ate)

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    rows = (
        await db.execute(
            base.order_by(Processo.data_hora_abertura.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = [_row_to_list(r) for r in rows]
    return items, total


def _row_to_list(r) -> ProcessoListItem:
    p: Processo = r[0]
    return ProcessoListItem(
        id=p.id,
        numero_processo=p.numero_processo,
        nup=p.nup,
        numero_origem=p.numero_origem,
        data_hora_abertura=p.data_hora_abertura,
        ativo=p.ativo,
        publico=p.publico,
        externo=p.externo,
        assunto=r.assunto_nome,
        tipo_processo=r.tipo_processo_nome,
        manifestante=r.manifestante_nome,
        manifestante_cpf_cnpj=r.manifestante_cpf,
        unidade_proprietaria=r.unidade_propr,
        local_atual=r.local_atual_nome,
    )


async def get_processo_detail(
    db: AsyncSession, processo_id: int, *, tenant_id: int
) -> ProcessoDetail | None:
    row = (
        await db.execute(_base_select(tenant_id).where(Processo.id == processo_id))
    ).first()
    if row is None:
        return None
    p: Processo = row[0]
    base_item = _row_to_list(row)
    movimentacoes = await _load_movimentacoes(db, processo_id, tenant_id)
    anexos = await _load_anexos(db, processo_id, tenant_id)

    return ProcessoDetail(
        **base_item.model_dump(),
        observacao=p.observacao,
        corpo=p.corpo,
        virtual=p.virtual,
        migrado=p.migrado,
        id_processo_pai=p.id_processo_pai,
        movimentacoes=movimentacoes,
        anexos=anexos,
    )


async def _load_movimentacoes(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> list[MovimentacaoItem]:
    UnidadeResp = aliased(UnidadeTrabalho, name="u_resp")
    stmt = (
        select(Movimentacao, Acao, UnidadeResp, Usuario)
        .join(Acao, Acao.id == Movimentacao.id_acao)
        .join(UnidadeResp, UnidadeResp.id == Movimentacao.id_unidade_responsavel, isouter=True)
        .join(Usuario, Usuario.id == Movimentacao.id_usuario, isouter=True)
        .where(
            Movimentacao.id_processo == processo_id,
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.excluido.is_(False),
        )
        .order_by(Movimentacao.data_hora_movimentacao.desc())
    )
    rows = (await db.execute(stmt)).all()
    mov_ids = [m.id for m, _, _, _ in rows]

    despachos: dict[int, Despacho] = {}
    if mov_ids:
        desp_rows = (
            await db.execute(
                select(Despacho).where(
                    Despacho.id_movimentacao.in_(mov_ids),
                    Despacho.tenant_id == tenant_id,
                    Despacho.excluido.is_(False),
                )
            )
        ).scalars().all()
        for d in desp_rows:
            despachos[d.id_movimentacao] = d

    encs: dict[int, tuple[Encaminhamento, UnidadeTrabalho | None, UnidadeTrabalho, Prioridade | None]] = {}
    if mov_ids:
        UOrig = aliased(UnidadeTrabalho, name="u_orig")
        UDest = aliased(UnidadeTrabalho, name="u_dest")
        enc_rows = (
            await db.execute(
                select(Encaminhamento, UOrig, UDest, Prioridade)
                .join(UOrig, UOrig.id == Encaminhamento.id_unidade_origem, isouter=True)
                .join(UDest, UDest.id == Encaminhamento.id_unidade_destino)
                .join(Prioridade, Prioridade.id == Encaminhamento.id_prioridade, isouter=True)
                .where(
                    Encaminhamento.id_movimentacao.in_(mov_ids),
                    Encaminhamento.tenant_id == tenant_id,
                    Encaminhamento.excluido.is_(False),
                )
            )
        ).all()
        for e, uo, ud, prio in enc_rows:
            encs[e.id_movimentacao] = (e, uo, ud, prio)

    desp_user_ids = {d.id_usuario for d in despachos.values()}
    users_by_id: dict[int, str] = {}
    if desp_user_ids:
        urows = (
            await db.execute(
                select(Usuario.id, Usuario.nome).where(
                    Usuario.id.in_(desp_user_ids),
                    Usuario.tenant_id == tenant_id,
                )
            )
        ).all()
        users_by_id = {uid: nome for uid, nome in urows}

    items: list[MovimentacaoItem] = []
    for mov, acao, unidade, user in rows:
        desp_out: DespachoOut | None = None
        d = despachos.get(mov.id)
        if d:
            desp_out = DespachoOut(
                id=d.id,
                despacho=d.despacho,
                usuario=users_by_id.get(d.id_usuario),
            )

        enc_out: EncaminhamentoOut | None = None
        e_tuple = encs.get(mov.id)
        if e_tuple:
            e, uo, ud, prio = e_tuple
            enc_out = EncaminhamentoOut(
                id=e.id,
                unidade_origem=uo.unidade_trabalho if uo else None,
                unidade_destino=ud.unidade_trabalho,
                prioridade=prio.prioridade if prio else None,
                quantidade_folhas=e.quantidade_folhas,
                data_prazo=e.data_prazo,
                recebido=e.recebido,
                data_hora_recebimento=e.data_hora_recebimento,
                cancelado=e.cancelado,
            )

        items.append(
            MovimentacaoItem(
                id=mov.id,
                data_hora_movimentacao=mov.data_hora_movimentacao,
                acao_flag=acao.flag,
                acao=acao.acao,
                status_acao=acao.status_acao,
                status_movimentacao=acao.status_movimentacao,
                unidade_responsavel=unidade.unidade_trabalho if unidade else None,
                usuario=user.nome if user else None,
                despacho=desp_out,
                encaminhamento=enc_out,
            )
        )
    return items


async def _load_anexos(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> list[AnexoNoProcesso]:
    stmt = (
        select(Anexo, AnexoProcesso, TipoAnexo.tipo_anexo)
        .join(AnexoProcesso, AnexoProcesso.id_anexo == Anexo.id)
        .join(TipoAnexo, TipoAnexo.id == Anexo.id_tipo_anexo, isouter=True)
        .where(
            AnexoProcesso.id_processo == processo_id,
            AnexoProcesso.tenant_id == tenant_id,
            AnexoProcesso.excluido.is_(False),
            # Fase P6 — esconde anexos desentranhados da listagem do processo
            AnexoProcesso.desentranhado_em.is_(None),
            and_(Anexo.excluido.is_(False), Anexo.ativo.is_(True)),
        )
        .order_by(AnexoProcesso.ordem.nulls_last(), Anexo.id)
    )
    rows = (await db.execute(stmt)).all()
    return [
        AnexoNoProcesso(
            id=a.id,
            id_anexo_processo=ap.id,
            descricao=a.descricao,
            publico=a.publico,
            qtd_paginas=a.qtd_paginas,
            e_doc=a.e_doc,
            tipo_anexo=tipo_anexo_nome,
            ordem=ap.ordem,
        )
        for a, ap, tipo_anexo_nome in rows
    ]

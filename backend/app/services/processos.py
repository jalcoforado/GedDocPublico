"""Queries de processo com joins explícitos.

Trazer nomes (manifestante, assunto, unidade) numa única query evita o problema
de N+1 ao listar. Para a timeline usamos selects separados que rodam após o
detalhe — é mais simples e suficientemente rápido em escala normal de UI.

Fase 13a: todas as funções recebem `tenant_id` e filtram pelo escopo.
"""
from datetime import datetime

from sqlalchemy import and_, false, func, or_, select
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
    EscopoProcesso,
    EncaminhamentoOut,
    MovimentacaoItem,
    PermanenciaNo,
    PermanenciaProcesso,
    PrazoInfo,
    ProcessoDetail,
    ProcessoListItem,
)
from .permanencia import No as NoDaLinha
from .permanencia import calcular as calcular_permanencia
from .prazos import calcular_prazo


def _base_select(tenant_id: int):
    LocalAtual = aliased(UnidadeTrabalho, name="local_atual")
    # F2 — alias próprio para o responsável: `Usuario` entra noutras junções
    # deste módulo, e reusar a entidade crua faria o SQLAlchemy colapsar as duas.
    Responsavel = aliased(Usuario, name="usuario_responsavel")
    stmt = (
        select(
            Processo,
            Assunto.assunto.label("assunto_nome"),
            TipoProcesso.tipo_processo.label("tipo_processo_nome"),
            Manifestante.nome.label("manifestante_nome"),
            Manifestante.cpf_cnpj.label("manifestante_cpf"),
            UnidadeTrabalho.unidade_trabalho.label("unidade_propr"),
            LocalAtual.unidade_trabalho.label("local_atual_nome"),
            Responsavel.nome.label("responsavel_nome"),
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
        .join(
            Responsavel,
            Responsavel.id == Processo.id_usuario_responsavel,
            isouter=True,
        )
        .where(Processo.excluido.is_(False))
    )
    return tenant_filter(stmt, Processo, tenant_id)


def _ids_unidade_e_subordinadas(tenant_id: int, raiz: int):
    """Subselect com a unidade `raiz` e toda a sua descendência.

    `UNION`, e não `UNION ALL`, de propósito. `routers/unidades.py` impede criar
    ciclo novo ao reparentar, mas TOLERA ciclo pré-existente por decisão
    explícita ("Estrutura já tinha ciclo — aborta walk e aceita"). Com
    `UNION ALL`, uma unidade que seja ancestral de si mesma faria esta recursiva
    girar até estourar memória — derrubando a listagem inteira, não só o filtro.
    `UNION` deduplica a cada passo e por isso termina mesmo com ciclo.
    """
    raiz_cte = (
        select(UnidadeTrabalho.id)
        .where(
            UnidadeTrabalho.id == raiz,
            UnidadeTrabalho.tenant_id == tenant_id,
            UnidadeTrabalho.excluido.is_(False),
        )
        .cte(name="unidades_do_escopo", recursive=True)
    )
    filho = aliased(UnidadeTrabalho, name="unidade_filha")
    raiz_cte = raiz_cte.union(
        select(filho.id).where(
            filho.id_unidade_pai == raiz_cte.c.id,
            filho.tenant_id == tenant_id,
            filho.excluido.is_(False),
        )
    )
    return select(raiz_cte.c.id)


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
    niveis_permitidos: list[str] | None = None,
    escopo: EscopoProcesso | None = None,
    id_usuario_contexto: int | None = None,
    id_unidade_contexto: int | None = None,
) -> tuple[list[ProcessoListItem], int]:
    base = _base_select(tenant_id)

    # Sigilo gradual — None = sem restrição (super-usuário); senão filtra pelos
    # níveis que a credencial do servidor alcança.
    if niveis_permitidos is not None:
        base = base.where(Processo.nivel_sigilo.in_(niveis_permitidos))

    # F2 — recorte por responsabilidade. Some-se ao filtro de sigilo, nunca o
    # substitui: escopo diz "o que é meu", sigilo diz "o que posso ver", e um
    # não afrouxa o outro.
    if escopo is not None:
        # Contexto ausente devolve NADA, nunca "tudo" nem "os com campo nulo".
        #
        # Não é zelo excessivo: `coluna == None` no SQLAlchemy compila para
        # `IS NULL`. Escrito ingenuamente, um usuário sem lotação pedindo
        # "minha unidade" receberia todos os processos SEM local, e pedindo
        # "meus" receberia todos os SEM responsável — em ambos os casos uma
        # lista cheia sob um rótulo que promete o contrário. Lista vazia é
        # errada de um jeito que a pessoa percebe na hora.
        if escopo is EscopoProcesso.meus:
            base = (
                base.where(Processo.id_usuario_responsavel == id_usuario_contexto)
                if id_usuario_contexto is not None
                else base.where(false())
            )
        elif escopo is EscopoProcesso.unidade:
            # INCLUI os sem responsável: são justamente os que precisam de alguém.
            base = (
                base.where(Processo.id_local_atual == id_unidade_contexto)
                if id_unidade_contexto is not None
                else base.where(false())
            )
        elif escopo is EscopoProcesso.unidade_e_subordinadas:
            base = (
                base.where(
                    Processo.id_local_atual.in_(
                        _ids_unidade_e_subordinadas(tenant_id, id_unidade_contexto)
                    )
                )
                if id_unidade_contexto is not None
                else base.where(false())
            )

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
        nivel_sigilo=p.nivel_sigilo,
        externo=p.externo,
        canal_entrada=p.canal_entrada,
        assunto=r.assunto_nome,
        tipo_processo=r.tipo_processo_nome,
        manifestante=r.manifestante_nome,
        manifestante_cpf_cnpj=r.manifestante_cpf,
        unidade_proprietaria=r.unidade_propr,
        local_atual=r.local_atual_nome,
        id_usuario_responsavel=p.id_usuario_responsavel,
        responsavel=r.responsavel_nome,
    )


async def get_processo_detail(
    db: AsyncSession,
    processo_id: int,
    *,
    tenant_id: int,
    niveis_permitidos: list[str] | None = None,
) -> ProcessoDetail | None:
    stmt = _base_select(tenant_id).where(Processo.id == processo_id)
    # Sigilo gradual — fora dos níveis acessíveis retorna None (404), sem
    # vazar a existência do processo sigiloso.
    if niveis_permitidos is not None:
        stmt = stmt.where(Processo.nivel_sigilo.in_(niveis_permitidos))
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    p: Processo = row[0]
    base_item = _row_to_list(row)
    movimentacoes, permanencia = await _load_movimentacoes(db, processo_id, tenant_id)
    anexos = await _load_anexos(db, processo_id, tenant_id)

    # PR 5b — bloco prazo end-to-end. `data_conclusao` = data da última
    # Movimentacao ativa com id_arquivamento NOT NULL.
    data_conclusao = (
        await db.execute(
            select(Movimentacao.data_hora_movimentacao)
            .where(
                Movimentacao.id_processo == processo_id,
                Movimentacao.tenant_id == tenant_id,
                Movimentacao.excluido.is_(False),
                Movimentacao.ativo.is_(True),
                Movimentacao.id_arquivamento.is_not(None),
            )
            .order_by(Movimentacao.data_hora_movimentacao.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    calc = calcular_prazo(
        data_abertura=p.data_hora_abertura,
        prazo_snapshot_dias=p.prazo_servico_dias_snapshot,
        data_conclusao=data_conclusao,
        now=datetime.now(),
    )
    prazo = PrazoInfo(
        status=calc.status,
        prazo_servico_dias_snapshot=calc.prazo_servico_dias_snapshot,
        prazo_previsto_em=calc.prazo_previsto_em,
        dias_restantes=calc.dias_restantes,
        dias_atraso=calc.dias_atraso,
        concluido_em=calc.concluido_em,
        origem="servico" if calc.prazo_servico_dias_snapshot is not None else None,
    )

    return ProcessoDetail(
        **base_item.model_dump(),
        observacao=p.observacao,
        corpo=p.corpo,
        virtual=p.virtual,
        migrado=p.migrado,
        id_processo_pai=p.id_processo_pai,
        sigilo_fundamento_legal=p.sigilo_fundamento_legal,
        sigilo_autoridade=p.sigilo_autoridade,
        sigilo_prazo_anos=p.sigilo_prazo_anos,
        sigilo_data_classificacao=p.sigilo_data_classificacao,
        sigilo_data_desclassificacao=p.sigilo_data_desclassificacao,
        movimentacoes=movimentacoes,
        anexos=anexos,
        prazo=prazo,
        permanencia=permanencia,
    )


async def _load_movimentacoes(
    db: AsyncSession, processo_id: int, tenant_id: int
) -> tuple[list[MovimentacaoItem], PermanenciaProcesso]:
    """Timeline do processo e a permanência agregada.

    Devolve as duas juntas porque saem da MESMA consulta: a permanência de um
    nó é a distância até o nó seguinte, então calculá-la exige a lista inteira.
    Uma segunda função que recarregasse as movimentações para somar tempos
    pagaria a consulta duas vezes e poderia divergir da timeline exibida.
    """
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

    # `datetime.now()` para casar com o resto deste arquivo (ver `calcular_prazo`
    # logo acima) e com `acoes_processo`, que carimba as movimentações. O
    # container roda em UTC, então hoje `now()` e `utcnow()` coincidem — o
    # comentário existe para o dia em que alguém definir `TZ`.
    permanencias, resumo = calcular_permanencia(
        [
            NoDaLinha(
                id=mov.id,
                momento=mov.data_hora_movimentacao,
                status_movimentacao=acao.status_movimentacao,
            )
            for mov, acao, _, _ in rows
        ],
        agora=datetime.now(),
    )

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
                permanencia=PermanenciaNo(
                    segundos=permanencias[mov.id].segundos,
                    natureza=permanencias[mov.id].natureza,
                    aberto=permanencias[mov.id].aberto,
                ),
            )
        )
    return items, PermanenciaProcesso(
        total_ativo_segundos=resumo.total_ativo_segundos,
        espera_segundos=resumo.espera_segundos,
        analise_segundos=resumo.analise_segundos,
        tramitacoes=resumo.tramitacoes,
        em_curso=resumo.em_curso,
    )


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

    # F8 — numeração cumulativa. `PAGINAS_CAPA` é a página fixa que
    # `pdf_capa.py` sempre gera (um `showPage()` só). Mesmo filtro de
    # "conta no PDF consolidado" que `pdf_montagem.py` usa (extensão .pdf);
    # anexo PDF sem `qtd_paginas` conhecido (upload que falhou o cálculo) não
    # avança o total — a estimativa fica pra trás do real nesse caso raro,
    # em vez de inventar um número.
    PAGINAS_CAPA = 1
    pagina_atual = PAGINAS_CAPA
    resultado: list[AnexoNoProcesso] = []
    for idx, (a, ap, tipo_anexo_nome) in enumerate(rows, start=1):
        pagina_processo = None
        eh_pdf = bool(a.e_doc) and a.e_doc.lower().endswith(".pdf")
        if eh_pdf and a.qtd_paginas:
            pagina_atual += a.qtd_paginas
            pagina_processo = pagina_atual
        resultado.append(
            AnexoNoProcesso(
                id=a.id,
                id_anexo_processo=ap.id,
                descricao=a.descricao,
                publico=a.publico,
                qtd_paginas=a.qtd_paginas,
                e_doc=a.e_doc,
                tipo_anexo=tipo_anexo_nome,
                ordem=ap.ordem,
                documento_numero=idx,
                pagina_processo=pagina_processo,
            )
        )
    return resultado

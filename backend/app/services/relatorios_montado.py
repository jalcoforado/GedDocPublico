"""Relatório montado pela própria pessoa (SI-35).

Uma linha por processo, com as colunas e os filtros que a pessoa escolheu
(`schemas/relatorio_montado.py`). Não há consulta nova de sigilo aqui, de
propósito: o recorte nasce de `relatorios._base`, o MESMO da lista de
processos, que aplica prefeitura, excluído, rascunho, sigilo de quem consulta,
unidade, assunto, tipo, serviço, período e os filtros da lista. Tudo o que
vem depois só ESTREITA esse conjunto (documentação, complementação,
assinatura pendente, atraso) ou DESCREVE os processos dele (as colunas).

Os resumos de tramitação vêm de `relatorios_tramitacao.resumir_tramitacao` —
a mesma regra da tela de Tramitação; o "tem etapa atrasada" daqui é o "só com
atraso" de lá. Como lá, esse filtro é calculado em Python e analisa o recorte
inteiro até `TETO_FILTRO_ATRASO`.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Assunto,
    ComplementacaoDocumental,
    Manifestante,
    Processo,
    Servico,
    SolicitacaoAssinatura,
    TipoProcesso,
    UnidadeTrabalho,
    Usuario,
)
from ..schemas.relatorio import RelatorioBreakdownItem, RelatorioFiltro
from ..schemas.relatorio_montado import (
    MAX_COLUNAS,
    CatalogoMontado,
    ColunaInfo,
    DefinicaoMontado,
    LinhaMontado,
    PeriodoMontado,
    ResultadoMontado,
    TotaisMontado,
)
from ..utils.relogio import agora_utc
from .relatorios import _base as recorte_da_lista
from .relatorios import _pct
from .relatorios_comum import (
    ROTULO_SITUACAO,
    descrever_filtros,
    hora_local,
    situacao_prazo,
)
from .relatorios_documentacao import (
    ROTULO_COMPLEMENTACAO,
    ROTULO_STATUS_DOC,
    _contagens_do_checklist,
    _status,
    _tem_complementacao,
)
from .relatorios_gerencial import ROTULO_CANAL
from .relatorios_tramitacao import (
    TETO_FILTRO_ATRASO,
    RecorteGrandeDemais,
    resumir_tramitacao,
)
from .sigilo import NIVEL_LABEL

Compl = ComplementacaoDocumental
Solic = SolicitacaoAssinatura

# chave → (rótulo, grupo, tipo). A ordem aqui é a da tela.
CATALOGO: dict[str, tuple[str, str, str]] = {
    "nup": ("NUP", "Processo", "texto"),
    "aberto_em": ("Aberto em", "Processo", "data_hora"),
    "arquivado_em": ("Arquivado em", "Processo", "data_hora"),
    "situacao": ("Situação", "Processo", "texto"),
    "tipo": ("Tipo de processo", "Processo", "texto"),
    "assunto": ("Assunto", "Processo", "texto"),
    "servico": ("Serviço", "Processo", "texto"),
    "unidade_dona": ("Unidade dona", "Processo", "texto"),
    "local_atual": ("Onde está", "Processo", "texto"),
    "responsavel": ("Responsável", "Processo", "texto"),
    "manifestante": ("Manifestante", "Processo", "texto"),
    "sigilo": ("Sigilo", "Processo", "texto"),
    "origem": ("Origem", "Processo", "texto"),
    "canal": ("Canal de entrada", "Processo", "texto"),
    "ultima_movimentacao": ("Última movimentação", "Andamento e prazo", "data_hora"),
    "dias_parado": ("Dias sem movimentação", "Andamento e prazo", "numero"),
    "prazo_situacao": ("Prazo do serviço", "Andamento e prazo", "texto"),
    "prazo_previsto": ("Prazo previsto", "Andamento e prazo", "data"),
    "doc_situacao": ("Documentos", "Documentação", "texto"),
    "doc_obrigatorios": ("Obrigatórios enviados", "Documentação", "texto"),
    "complementacao": ("Complementação", "Documentação", "texto"),
    "tram_envios": ("Envios", "Tramitação", "numero"),
    "tram_unidades": ("Unidades por onde passou", "Tramitação", "numero"),
    "tram_atrasos": ("Etapas atrasadas", "Tramitação", "numero"),
    "tram_ultimo_envio": ("Último envio", "Tramitação", "data_hora"),
    "tram_unidade_mais_tempo": ("Unidade onde ficou mais tempo", "Tramitação", "texto"),
    "ass_pedidas": ("Assinaturas pedidas", "Assinaturas", "numero"),
    "ass_concluidas": ("Assinaturas concluídas", "Assinaturas", "numero"),
    "ass_pendentes": ("Assinaturas pendentes", "Assinaturas", "numero"),
    "ass_ultima_conclusao": ("Última assinatura concluída", "Assinaturas", "data_hora"),
}
COLUNAS_PADRAO = ["aberto_em", "situacao", "assunto", "unidade_dona", "local_atual"]
ROTULO_ORDEM: dict[str, str] = {
    "numero": "Número",
    "aberto_em": "Aberto em",
    "arquivado_em": "Arquivado em",
    "ultima_movimentacao": "Última movimentação",
    "assunto": "Assunto",
    "servico": "Serviço",
    "unidade_dona": "Unidade dona",
    "local_atual": "Onde está",
}
ROTULO_AGRUPAR: dict[str, str] = {
    "situacao": "Situação",
    "tipo": "Tipo de processo",
    "unidade_dona": "Unidade dona",
    "local_atual": "Onde está",
    "assunto": "Assunto",
    "servico": "Serviço",
}
# Rótulo curto do prazo, igual ao da tela (`frontend/lib/relatorios.ts`).
ROTULO_PRAZO_CURTO: dict[str, str] = {
    "sem_prazo": "Sem prazo de serviço",
    "dentro_do_prazo": "Dentro do prazo",
    "vencendo": "Vencendo",
    "atrasado": "Prazo vencido",
    "concluido_no_prazo": "Arquivado no prazo",
    "concluido_atrasado": "Arquivado com atraso",
}
ROTULO_PERIODO_RELATIVO: dict[str, str] = {
    "mes_atual": "este mês",
    "mes_anterior": "mês passado",
    "ano_atual": "este ano",
}
# Lote das consultas por lista de ids: o asyncpg aceita até 32767 parâmetros.
LOTE = 5000


def catalogo() -> CatalogoMontado:
    return CatalogoMontado(
        colunas=[ColunaInfo(chave=k, rotulo=r, grupo=g, tipo=t) for k, (r, g, t) in CATALOGO.items()],
        colunas_padrao=COLUNAS_PADRAO,
        ordens=ROTULO_ORDEM,
        agrupamentos=ROTULO_AGRUPAR,
        max_colunas=MAX_COLUNAS,
    )


def hoje_local() -> date:
    return hora_local(agora_utc()).date()


def resolver_periodo(p: PeriodoMontado, hoje: date) -> tuple[date | None, date | None]:
    """O período em dias locais. O relativo é resolvido no dia em que roda."""
    if p.tipo == "fixo":
        return p.desde, p.ate
    if p.tipo == "ultimos_dias":
        return hoje - timedelta(days=(p.dias or 1) - 1), hoje
    if p.tipo == "mes_atual":
        return hoje.replace(day=1), hoje
    if p.tipo == "mes_anterior":
        fim = hoje.replace(day=1) - timedelta(days=1)
        return fim.replace(day=1), fim
    if p.tipo == "ano_atual":
        return date(hoje.year, 1, 1), hoje
    return None, None


def rotulo_periodo_relativo(p: PeriodoMontado) -> str | None:
    if p.tipo == "ultimos_dias":
        return f"últimos {p.dias} dias" if p.dias != 1 else "hoje"
    return ROTULO_PERIODO_RELATIVO.get(p.tipo)


def normalizar_definicao(bruta: object) -> tuple[DefinicaoMontado | None, list[str]]:
    """Lê a definição salva sem quebrar se o catálogo mudou desde que ela foi
    salva: coluna, ordem ou agrupamento que saiu é tirado e dito em `avisos`.
    O resto (filtro com valor que não existe mais) volta None e a pessoa
    remonta — melhor que adivinhar."""
    avisos: list[str] = []
    if not isinstance(bruta, dict):
        return None, ["A definição salva não pôde ser lida."]
    d = dict(bruta)
    colunas = [c for c in d.get("colunas") or [] if isinstance(c, str)]
    validas = [c for c in colunas if c in CATALOGO]
    if len(validas) < len(colunas):
        fora = ", ".join(c for c in colunas if c not in CATALOGO)
        avisos.append(f"Colunas que não existem mais foram tiradas: {fora}.")
    d["colunas"] = validas or COLUNAS_PADRAO
    if d.get("ordem") is not None and d["ordem"] not in ROTULO_ORDEM:
        avisos.append("A ordenação salva não existe mais; voltou para a padrão.")
        d["ordem"] = None
    if d.get("agrupar_por") is not None and d["agrupar_por"] not in ROTULO_AGRUPAR:
        avisos.append("O agrupamento salvo não existe mais e foi tirado.")
        d["agrupar_por"] = None
    try:
        return DefinicaoMontado.model_validate(d), avisos
    except ValueError:
        return None, [*avisos, "A definição salva não pôde ser lida; monte o relatório de novo."]


def _filtro(d: DefinicaoMontado, desde: date | None, ate: date | None) -> RelatorioFiltro:
    fm = d.filtros
    return RelatorioFiltro(
        id_unidade=fm.id_unidade,
        modo_unidade=fm.modo_unidade,
        id_assunto=fm.id_assunto,
        id_tipo_processo=fm.id_tipo_processo,
        id_servico=fm.id_servico,
        desde=desde,
        ate=ate,
        data_base=fm.data_base,
        situacao=fm.situacao,
        parado_ha_dias=fm.parado_ha_dias,
        prazo=fm.prazo,
        sigilo=fm.sigilo,
        origem=fm.origem,
        com_atraso=fm.com_atraso,
    )


def _conta_solic(tenant_id: int, *cond):
    return (
        select(func.count())
        .select_from(Solic)
        .where(Solic.id_processo == Processo.id, Solic.tenant_id == tenant_id, Solic.excluido.is_(False), *cond)
        .correlate(Processo)
        .scalar_subquery()
    )


# As mesmas regras de `relatorios_assinaturas._status`.
_CONCLUIDA = (Solic.cancelada.is_(False), Solic.realizada.is_(True), Solic.dt_fim.is_not(None))
_PENDENTE = (Solic.cancelada.is_(False), or_(Solic.realizada.is_(False), Solic.dt_fim.is_(None)))


def _lotes(ids: list[int]):
    for i in range(0, len(ids), LOTE):
        yield ids[i : i + LOTE]


def _iso(v: datetime | date | None) -> str | None:
    return v.isoformat() if v is not None else None


async def executar_montado(
    db: AsyncSession,
    d: DefinicaoMontado,
    *,
    tenant_id: int,
    # Sem default: ver `relatorios.gerar_relatorio`.
    niveis_permitidos: list[str] | None,
    max_rows: int = 200,
    hoje: date | None = None,
    avisos: list[str] | None = None,
) -> ResultadoMontado:
    agora = agora_utc()
    desde, ate = resolver_periodo(d.periodo, hoje or hoje_local())
    f = _filtro(d, desde, ate)
    fm = d.filtros

    # 1. O recorte da lista de processos (sigilo incluído) + o que só o
    #    montador filtra.
    base = recorte_da_lista(f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos)
    stmt = (
        select(base.c.id, base.c.situacao, base.c.arquivado_em, base.c.ultima_mov)
        .select_from(base)
        .join(Processo, Processo.id == base.c.id)
    )
    if fm.documentacao:
        stmt = stmt.where(_status(*_contagens_do_checklist(tenant_id)) == fm.documentacao)
    if fm.complementacao_aberta:
        stmt = stmt.where(_tem_complementacao(tenant_id, Compl.status == "aberta"))
    if fm.assinatura_pendente:
        stmt = stmt.where(_conta_solic(tenant_id, *_PENDENTE) > 0)
    if fm.com_atraso:
        # Atraso sai das etapas, calculadas em Python — analisa o recorte
        # inteiro (até o teto) ANTES de cortar a lista, como a Tramitação.
        ids_atraso = await _ids_com_atraso(db, stmt, tenant_id=tenant_id, agora=agora)
        stmt = stmt.where(Processo.id.in_(ids_atraso) if ids_atraso else false())
    rec = stmt.subquery("montado")

    # 2. Totais — o recorte inteiro, sem o teto da lista.
    t = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(rec.c.situacao == "em_andamento"),
                func.count().filter(rec.c.situacao == "em_transito"),
                func.count().filter(rec.c.situacao == "arquivado"),
            ).select_from(rec)
        )
    ).one()
    totais = TotaisMontado(
        total=int(t[0]), em_andamento=int(t[1]), em_transito=int(t[2]), arquivados=int(t[3])
    )

    # 3. Agrupamento (o "Agrupar por" da lista de processos).
    agrupamento = None
    if d.agrupar_por:
        agrupamento = await _agrupar(db, rec, d.agrupar_por, totais.total, tenant_id=tenant_id)

    # 4. A lista, com teto.
    Dona = aliased(UnidadeTrabalho, name="dona")
    Local = aliased(UnidadeTrabalho, name="local")
    Resp = aliased(Usuario, name="resp")
    cols = set(d.colunas)
    extras = []
    if cols & {"doc_situacao", "doc_obrigatorios"}:
        itens, obrig, envs = _contagens_do_checklist(tenant_id)
        extras += [itens.label("doc_itens"), obrig.label("doc_obrig"), envs.label("doc_envs")]
    if "prazo_situacao" in cols:
        extras.append(situacao_prazo(tenant_id, agora).label("prazo_sit"))
    if "ass_pedidas" in cols:
        extras.append(_conta_solic(tenant_id).label("ass_pedidas"))
    if "ass_concluidas" in cols:
        extras.append(_conta_solic(tenant_id, *_CONCLUIDA).label("ass_concluidas"))
    if "ass_pendentes" in cols:
        extras.append(_conta_solic(tenant_id, *_PENDENTE).label("ass_pendentes"))
    if "ass_ultima_conclusao" in cols:
        extras.append(
            select(func.max(Solic.dt_fim))
            .where(Solic.id_processo == Processo.id, Solic.tenant_id == tenant_id,
                   Solic.excluido.is_(False), *_CONCLUIDA)
            .correlate(Processo)
            .scalar_subquery()
            .label("ass_ultima")
        )

    ordem_col = {
        "numero": Processo.numero_processo,
        "aberto_em": Processo.data_hora_abertura,
        "arquivado_em": rec.c.arquivado_em,
        "ultima_movimentacao": rec.c.ultima_mov,
        "assunto": Assunto.assunto,
        "servico": Servico.nome,
        "unidade_dona": Dona.unidade_trabalho,
        "local_atual": Local.unidade_trabalho,
    }
    if d.ordem:
        c = ordem_col[d.ordem]
        ordem = [(c.desc() if d.ordem_desc else c.asc()).nulls_last()]
    else:
        # Padrão da lista de processos: mais recente primeiro pela data base.
        ordem = [
            rec.c.arquivado_em.desc().nulls_last()
            if fm.data_base == "arquivamento"
            else Processo.data_hora_abertura.desc()
        ]

    lista = (
        await db.execute(
            select(
                Processo,
                rec.c.situacao,
                rec.c.arquivado_em,
                rec.c.ultima_mov,
                Assunto.assunto.label("assunto"),
                TipoProcesso.tipo_processo.label("tipo"),
                Servico.nome.label("servico"),
                Dona.unidade_trabalho.label("dona"),
                Local.unidade_trabalho.label("local"),
                Resp.nome.label("resp"),
                Manifestante.nome.label("manif"),
                *extras,
            )
            .select_from(rec)
            .join(Processo, Processo.id == rec.c.id)
            .join(Assunto, Assunto.id == Processo.id_assunto)
            .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo, isouter=True)
            .join(Servico, and_(Servico.id == Processo.id_servico, Servico.tenant_id == tenant_id), isouter=True)
            .join(Dona, Dona.id == Processo.id_unidade_proprietaria, isouter=True)
            .join(Local, Local.id == Processo.id_local_atual, isouter=True)
            .join(Resp, Resp.id == Processo.id_usuario_responsavel, isouter=True)
            .join(Manifestante, Manifestante.id == Processo.id_manifestante, isouter=True)
            .order_by(*ordem, Processo.id.desc())
            .limit(max_rows)
        )
    ).all()

    # 5. O que se calcula fora do SQL, só para os processos listados.
    ids = [r[0].id for r in lista]
    resumos = {}
    if cols & {"tram_envios", "tram_unidades", "tram_atrasos", "tram_ultimo_envio", "tram_unidade_mais_tempo"}:
        for lote in _lotes_de(lista):
            resumos.update(
                await resumir_tramitacao(
                    db,
                    [(r[0].id, r[0].data_hora_abertura, r[0].id_unidade_proprietaria, r.dona) for r in lote],
                    tenant_id=tenant_id,
                    agora=agora,
                )
            )
    ultima_compl: dict[int, ComplementacaoDocumental] = {}
    if "complementacao" in cols and ids:
        for lote in _lotes(ids):
            pedidos = (
                await db.execute(
                    select(Compl)
                    .where(Compl.id_processo.in_(lote), Compl.tenant_id == tenant_id, Compl.excluido.is_(False))
                    .order_by(Compl.criado_em.asc(), Compl.id.asc())
                )
            ).scalars().all()
            for c in pedidos:
                ultima_compl[c.id_processo] = c  # o último da ordem é o mais recente

    linhas = [
        LinhaMontado(
            id=r[0].id,
            numero_processo=r[0].numero_processo,
            nivel_sigilo=r[0].nivel_sigilo,
            valores={c: _valor(c, r, resumos.get(r[0].id), ultima_compl.get(r[0].id), agora) for c in d.colunas},
        )
        for r in lista
    ]

    descricao = await descrever_filtros(db, f, tenant_id=tenant_id)
    relativo = rotulo_periodo_relativo(d.periodo)
    if relativo:
        descricao.insert(1, f"Período relativo: {relativo} — recalculado a cada vez que o relatório abre")
    extras_desc = []
    if fm.documentacao:
        extras_desc.append(f"Documentos: {ROTULO_STATUS_DOC[fm.documentacao].lower()}")
    if fm.complementacao_aberta:
        extras_desc.append("Só com complementação aguardando o cidadão")
    if fm.assinatura_pendente:
        extras_desc.append("Só com assinatura pendente")
    descricao[-1:-1] = extras_desc
    return ResultadoMontado(
        definicao=d,
        colunas=[ColunaInfo(chave=c, rotulo=CATALOGO[c][0], grupo=CATALOGO[c][1], tipo=CATALOGO[c][2])
                 for c in d.colunas],
        descricao_filtros=descricao,
        desde=desde,
        ate=ate,
        totais=totais,
        rotulo_agrupamento=ROTULO_AGRUPAR[d.agrupar_por] if d.agrupar_por else None,
        agrupamento=agrupamento,
        linhas=linhas,
        cortado=len(linhas) < totais.total,
        avisos=list(avisos or []),
    )


def _lotes_de(lista):
    for i in range(0, len(lista), LOTE):
        yield lista[i : i + LOTE]


async def _ids_com_atraso(db: AsyncSession, stmt, *, tenant_id: int, agora: datetime) -> list[int]:
    pre = stmt.subquery("pre")
    total = (await db.execute(select(func.count()).select_from(pre))).scalar_one()
    if total > TETO_FILTRO_ATRASO:
        raise RecorteGrandeDemais(
            f"O recorte tem {total} processos; o filtro de atraso analisa até "
            f"{TETO_FILTRO_ATRASO}. Diminua o período ou filtre por unidade, tipo, "
            "assunto ou serviço."
        )
    rows = (
        await db.execute(
            select(Processo.id, Processo.data_hora_abertura, Processo.id_unidade_proprietaria)
            .select_from(pre)
            .join(Processo, Processo.id == pre.c.id)
        )
    ).all()
    com_atraso: list[int] = []
    for i in range(0, len(rows), LOTE):
        lote = rows[i : i + LOTE]
        resumos = await resumir_tramitacao(
            db, [(r.id, r.data_hora_abertura, r.id_unidade_proprietaria, None) for r in lote],
            tenant_id=tenant_id, agora=agora,
        )
        com_atraso += [pid for pid, s in resumos.items() if s.teve_atraso]
    return com_atraso


async def _agrupar(db: AsyncSession, rec, chave: str, total: int, *, tenant_id: int):
    if chave == "situacao":
        rows = (
            await db.execute(
                select(rec.c.situacao, func.count())
                .group_by(rec.c.situacao)
                .order_by(func.count().desc(), rec.c.situacao)
            )
        ).all()
        return [
            RelatorioBreakdownItem(label=ROTULO_SITUACAO.get(s, s), count=int(n), pct=_pct(int(n), total))
            for s, n in rows
        ]
    U = aliased(UnidadeTrabalho, name="ug")
    coluna, joins = {
        "tipo": (
            TipoProcesso.tipo_processo,
            [(Assunto, Assunto.id == Processo.id_assunto),
             (TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo)],
        ),
        "unidade_dona": (U.unidade_trabalho, [(U, U.id == Processo.id_unidade_proprietaria)]),
        "local_atual": (U.unidade_trabalho, [(U, U.id == Processo.id_local_atual)]),
        "assunto": (Assunto.assunto, [(Assunto, Assunto.id == Processo.id_assunto)]),
        "servico": (
            Servico.nome,
            [(Servico, and_(Servico.id == Processo.id_servico, Servico.tenant_id == tenant_id))],
        ),
    }[chave]
    stmt = select(coluna.label("label"), func.count().label("n")).select_from(rec).join(
        Processo, Processo.id == rec.c.id
    )
    for alvo, cond in joins:
        stmt = stmt.join(alvo, cond, isouter=True)
    stmt = stmt.group_by(coluna).order_by(func.count().desc(), coluna)
    return [
        RelatorioBreakdownItem(label=r.label or "—", count=int(r.n), pct=_pct(int(r.n), total))
        for r in (await db.execute(stmt)).all()
    ]


def _valor(chave: str, r, resumo, compl, agora: datetime) -> str | int | None:
    p: Processo = r[0]
    if chave == "nup":
        return p.nup
    if chave == "aberto_em":
        return _iso(hora_local(p.data_hora_abertura))
    if chave == "arquivado_em":
        return _iso(hora_local(r.arquivado_em))
    if chave == "situacao":
        return ROTULO_SITUACAO[r.situacao]
    if chave == "tipo":
        return r.tipo
    if chave == "assunto":
        return r.assunto
    if chave == "servico":
        return r.servico
    if chave == "unidade_dona":
        return r.dona
    if chave == "local_atual":
        return r.local
    if chave == "responsavel":
        return r.resp
    if chave == "manifestante":
        return r.manif
    if chave == "sigilo":
        return NIVEL_LABEL.get(p.nivel_sigilo, p.nivel_sigilo)
    if chave == "origem":
        return "Externa" if p.externo else "Interna"
    if chave == "canal":
        return ROTULO_CANAL.get(p.canal_entrada, p.canal_entrada or "Não informado")
    if chave == "ultima_movimentacao":
        return _iso(hora_local(r.ultima_mov))
    if chave == "dias_parado":
        if r.situacao == "arquivado" or r.ultima_mov is None:
            return None
        return max(0, (agora - r.ultima_mov).days)
    if chave == "prazo_situacao":
        return ROTULO_PRAZO_CURTO.get(r.prazo_sit, r.prazo_sit)
    if chave == "prazo_previsto":
        if p.prazo_servico_dias_snapshot is None:
            return None
        return _iso(hora_local(p.data_hora_abertura + timedelta(days=p.prazo_servico_dias_snapshot)).date())
    if chave == "doc_situacao":
        return ROTULO_STATUS_DOC[_status_py(r.doc_itens, r.doc_obrig, r.doc_envs)]
    if chave == "doc_obrigatorios":
        return f"{int(r.doc_envs or 0)} de {int(r.doc_obrig or 0)}" if r.doc_obrig else None
    if chave == "complementacao":
        return ROTULO_COMPLEMENTACAO.get(compl.status, compl.status) if compl else None
    if chave.startswith("tram_"):
        if resumo is None:
            return None
        if chave == "tram_envios":
            return resumo.qtd_encaminhamentos
        if chave == "tram_unidades":
            return resumo.qtd_unidades_visitadas
        if chave == "tram_atrasos":
            return resumo.qtd_atrasos
        if chave == "tram_ultimo_envio":
            return _iso(hora_local(resumo.ultimo_envio))
        return _unidade_mais_tempo(resumo, agora)
    if chave == "ass_pedidas":
        return int(r.ass_pedidas or 0)
    if chave == "ass_concluidas":
        return int(r.ass_concluidas or 0)
    if chave == "ass_pendentes":
        return int(r.ass_pendentes or 0)
    if chave == "ass_ultima_conclusao":
        return _iso(hora_local(r.ass_ultima))
    raise KeyError(chave)  # catálogo e `_valor` andam juntos; o teste cobre todas


def _status_py(itens, obrig, envs) -> str:
    """O `_status` SQL da documentação, sobre os números já contados."""
    itens, obrig, envs = int(itens or 0), int(obrig or 0), int(envs or 0)
    if itens == 0:
        return "sem_documentos_exigidos"
    if obrig == 0:
        return "completo"
    if envs == 0:
        return "pendente"
    if envs < obrig:
        return "parcial"
    return "completo"


def _unidade_mais_tempo(resumo, agora: datetime) -> str | None:
    minutos: dict[str, int] = defaultdict(int)
    for e in resumo.etapas:
        if e.chegou_em is None or e.unidade is None:
            continue  # em trânsito: não esteve em unidade nenhuma
        fim = e.saiu_em or agora
        minutos[e.unidade] += int((fim - e.chegou_em).total_seconds() // 60)
    if not minutos:
        return None
    return max(minutos.items(), key=lambda kv: kv[1])[0]

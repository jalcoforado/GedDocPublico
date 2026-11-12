"""Página gerencial de relatórios (SI-34).

Cada número da página é o total da lista que o "ver lista" da seção abre —
mesmo recorte (`relatorios_comum`), mesma regra de situação, de parado e de
atraso. Por isso as seções reaproveitam os relatórios em vez de contar de novo:

- Entrada  → `processos` pela abertura (+ quebra por canal);
- Andamento→ `processos` sem período, por situação de hoje e parados;
- Saída    → `processos` pelo arquivamento;
- Gargalos → `tramitação` pela chegada, etapas que CHEGARAM no período;
- Assinaturas → `assinaturas` pelo pedido;
- Documentação → `documentacao`, uma visão por número.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Assunto, Processo
from ..schemas.relatorio import RelatorioFiltro
from ..schemas.relatorio_assinaturas import AssinaturasFiltro
from ..schemas.relatorio_gerencial import (
    CanalContagem,
    GargaloUnidade,
    GerencialResposta,
    SecaoAndamento,
    SecaoDocumentacao,
    SecaoEntrada,
    SecaoGargalos,
    SecaoPrazos,
    SecaoSaida,
    SecaoTendencia,
    PontoTendencia,
)
from ..utils.relogio import agora_utc
from .relatorios_assinaturas import gerar_assinaturas
from .processos import condicao_arquivado
from .relatorios_comum import (
    FUSO_RELATORIO,
    aplicar_filtros_processo,
    condicao_parado,
    data_arquivamento,
    descrever_filtros,
    hora_local,
    semana_local,
    situacao,
    situacao_prazo,
)
from .relatorios_documentacao import contar_visao, dias_medio_resposta
from .relatorios_tramitacao import gerar_tramitacao

ROTULO_CANAL: dict[str | None, str] = {
    "balcao": "Balcão",
    "portal": "Portal do cidadão",
    "email": "E-mail",
    "api": "Integração (API)",
    "interno": "Registro interno",
    None: "Não informado",
}

# Teto de processos que a seção de gargalos analisa (via tramitação).
MAX_PROCESSOS_GARGALOS = 5000


def _no_periodo(dia: date | None, f: RelatorioFiltro) -> bool:
    if dia is None:
        return False
    return (f.desde is None or dia >= f.desde) and (f.ate is None or dia <= f.ate)


async def gerar_gerencial(
    db: AsyncSession,
    f: RelatorioFiltro,
    *,
    tenant_id: int,
    # Sem default: ver `relatorios.gerar_relatorio`.
    niveis_permitidos: list[str] | None,
    dias_parado: int = 15,
) -> GerencialResposta:
    def _recorte(stmt, filtro: RelatorioFiltro, coluna_data):
        return aplicar_filtros_processo(
            stmt.join(Assunto, Assunto.id == Processo.id_assunto),
            filtro,
            tenant_id=tenant_id,
            niveis_permitidos=niveis_permitidos,
            coluna_data=coluna_data,
        )

    # Entrada — abertos no período, por canal.
    canal = Processo.canal_entrada
    linhas = (
        await db.execute(
            _recorte(
                select(canal, func.count()).select_from(Processo),
                f,
                Processo.data_hora_abertura,
            ).group_by(canal)
        )
    ).all()
    por_canal = sorted(
        (CanalContagem(canal=c, rotulo=ROTULO_CANAL.get(c, c or "Não informado"), count=int(n))
         for c, n in linhas),
        key=lambda x: (-x.count, x.rotulo),
    )
    entrada = SecaoEntrada(abertos=sum(x.count for x in por_canal), por_canal=por_canal)

    # Andamento — hoje, sem período.
    hoje = f.model_copy(update={"desde": None, "ate": None})
    sit = situacao(tenant_id)
    andamento_row = (
        await db.execute(
            _recorte(
                select(
                    func.count().filter(sit == "em_andamento"),
                    func.count().filter(sit == "em_transito"),
                    func.count().filter(condicao_parado(tenant_id, dias_parado, agora_utc())),
                ).select_from(Processo),
                hoje,
                Processo.data_hora_abertura,
            )
        )
    ).one()
    andamento = SecaoAndamento(
        em_andamento=int(andamento_row[0]),
        em_transito=int(andamento_row[1]),
        parados=int(andamento_row[2]),
        dias_parado=dias_parado,
    )

    # Saída — arquivados no período e tempo até arquivar.
    arq = data_arquivamento(tenant_id)
    saida_row = (
        await db.execute(
            _recorte(
                select(
                    func.count(),
                    func.avg(func.extract("epoch", arq - Processo.data_hora_abertura) / 86400.0),
                ).select_from(Processo),
                f,
                arq,
            )
        )
    ).one()
    saida = SecaoSaida(
        arquivados=int(saida_row[0]),
        dias_medio_ate_arquivar=round(float(saida_row[1]), 1) if saida_row[1] is not None else None,
    )

    # Gargalos — estadias que CHEGARAM a uma unidade no período.
    tram = await gerar_tramitacao(
        db,
        f.model_copy(update={"data_base": "chegada"}),
        tenant_id=tenant_id,
        niveis_permitidos=niveis_permitidos,
        max_processos=MAX_PROCESSOS_GARGALOS,
    )
    acc: dict[tuple[int | None, str | None], dict] = defaultdict(
        lambda: {"chegadas": 0, "com_prazo": 0, "atrasos": 0, "min": 0, "encerradas": 0}
    )
    for p in tram.processos:
        for e in p.etapas:
            # etapa "em trânsito" não tem chegada: não é estadia em unidade
            if e.chegou_em is None or not _no_periodo(e.chegou_em.date(), f):
                continue
            if f.id_unidade and e.id_unidade != f.id_unidade:
                continue
            a = acc[(e.id_unidade, e.unidade)]
            a["chegadas"] += 1
            if e.prazo_estipulado is not None:
                a["com_prazo"] += 1
                a["atrasos"] += int(e.atrasou)
            if e.minutos_no_local is not None:
                a["min"] += e.minutos_no_local
                a["encerradas"] += 1
    unidades = sorted(
        (
            GargaloUnidade(
                id_unidade=k[0],
                unidade=k[1],
                chegadas=v["chegadas"],
                com_prazo=v["com_prazo"],
                atrasos=v["atrasos"],
                dias_medio=round(v["min"] / v["encerradas"] / 1440, 1) if v["encerradas"] else None,
            )
            for k, v in acc.items()
        ),
        key=lambda u: (-u.atrasos, -(u.dias_medio or 0), u.unidade or ""),
    )
    gargalos = SecaoGargalos(unidades=unidades, cortado=tram.cortado)

    # Assinaturas — pedidas no período.
    ass = await gerar_assinaturas(
        db,
        AssinaturasFiltro(
            **f.model_dump(include={"id_unidade", "modo_unidade", "id_assunto",
                                    "id_tipo_processo", "id_servico", "desde", "ate"}),
            data_base="pedido",
        ),
        tenant_id=tenant_id,
        niveis_permitidos=niveis_permitidos,
        max_rows=0,
    )

    # Prazos do serviço — arquivados no período, e os em aberto hoje.
    agora = agora_utc()
    prazo = situacao_prazo(tenant_id, agora)
    concluidos = dict(
        (await db.execute(
            _recorte(select(prazo, func.count()).select_from(Processo), f, arq).group_by(prazo)
        )).all()
    )
    em_aberto = dict(
        (await db.execute(
            _recorte(select(prazo, func.count()).select_from(Processo), hoje, Processo.data_hora_abertura)
            .where(~condicao_arquivado(tenant_id))
            .group_by(prazo)
        )).all()
    )
    prazos = SecaoPrazos(
        concluidos_no_prazo=int(concluidos.get("concluido_no_prazo", 0)),
        concluidos_atrasados=int(concluidos.get("concluido_atrasado", 0)),
        concluidos_sem_prazo=int(concluidos.get("sem_prazo", 0)),
        dentro_do_prazo=int(em_aberto.get("dentro_do_prazo", 0)),
        vencendo=int(em_aberto.get("vencendo", 0)),
        atrasados=int(em_aberto.get("atrasado", 0)),
        em_aberto_sem_prazo=int(em_aberto.get("sem_prazo", 0)),
    )

    tendencia = await _tendencia(db, f, _recorte, tenant_id, agora)

    # Documentação — cada número é o total de uma visão da lista.
    async def doc(visao) -> int:
        return await contar_visao(db, f, visao, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos)

    abertos_com_servico = await doc("documentos")
    pendentes, parciais = await doc("doc_pendente"), await doc("doc_parcial")
    documentacao = SecaoDocumentacao(
        pendentes=pendentes,
        parciais=parciais,
        completos=await doc("doc_completo"),
        sem_documentos_exigidos=entrada.abertos - abertos_com_servico,
        complementacao_pedida=await doc("compl_pedida"),
        aguardando_cidadao=await doc("compl_aberta"),
        complementacao_respondida=await doc("compl_respondida"),
        dias_medio_resposta=await dias_medio_resposta(
            db, f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos
        ),
    )

    return GerencialResposta(
        descricao_filtros=await descrever_filtros(db, f, tenant_id=tenant_id, por_secao=True),
        entrada=entrada,
        andamento=andamento,
        saida=saida,
        prazos=prazos,
        tendencia=tendencia,
        gargalos=gargalos,
        assinaturas=ass.totais,
        documentacao=documentacao,
    )


# Até ~6 meses o gráfico é por semana; acima, por mês (53 barras de semana
# num ano viram ruído).
MAX_DIAS_POR_SEMANA = 183
SEMANAS_SEM_FILTRO = 12


async def _tendencia(db, f: RelatorioFiltro, _recorte, tenant_id: int, agora) -> SecaoTendencia:
    """Abertos e arquivados por semana (ou mês) do período — mesmo recorte.

    Sem período no filtro, as últimas 12 semanas: um gráfico de todo o
    histórico não mostra tendência nenhuma."""
    hoje_local = hora_local(agora).date()
    ate = f.ate or hoje_local
    desde = f.desde or (ate - timedelta(weeks=SEMANAS_SEM_FILTRO) + timedelta(days=1))
    por_mes = (ate - desde).days > MAX_DIAS_POR_SEMANA
    janela = f.model_copy(update={"desde": desde, "ate": ate})

    def balde(coluna):
        if por_mes:
            local = func.timezone(FUSO_RELATORIO.key, func.timezone("UTC", coluna))
            return func.date(func.date_trunc("month", local))
        return semana_local(coluna)

    async def serie(coluna) -> dict[date, int]:
        b = balde(coluna)
        linhas = await db.execute(
            _recorte(select(b, func.count()).select_from(Processo), janela, coluna).group_by(b)
        )
        return {d: int(n) for d, n in linhas.all()}

    abertos = await serie(Processo.data_hora_abertura)
    arquivados = await serie(data_arquivamento(tenant_id))

    # Todos os baldes do período, inclusive os vazios — um gráfico que pula a
    # semana sem processo esconde justamente a parada.
    if por_mes:
        cursor = desde.replace(day=1)
    else:
        cursor = desde - timedelta(days=desde.weekday())
    pontos: list[PontoTendencia] = []
    while cursor <= ate:
        pontos.append(
            PontoTendencia(inicio=cursor, abertos=abertos.get(cursor, 0), arquivados=arquivados.get(cursor, 0))
        )
        if por_mes:
            cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        else:
            cursor += timedelta(weeks=1)
    return SecaoTendencia(
        granularidade="mes" if por_mes else "semana", desde=desde, ate=ate, pontos=pontos
    )

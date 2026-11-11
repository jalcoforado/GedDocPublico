"""Página gerencial de relatórios (SI-34).

Cada número da página é o total da lista que o "ver lista" da seção abre —
mesmo recorte (`relatorios_comum`), mesma regra de situação, de parado e de
atraso. Por isso as seções reaproveitam os relatórios em vez de contar de novo:

- Entrada  → `processos` pela abertura (+ quebra por canal);
- Andamento→ `processos` sem período, por situação de hoje e parados;
- Saída    → `processos` pelo arquivamento;
- Gargalos → `tramitação` pela chegada, etapas que CHEGARAM no período;
- Assinaturas → `assinaturas` pelo pedido.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

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
    SecaoEntrada,
    SecaoGargalos,
    SecaoSaida,
)
from ..utils.relogio import agora_utc
from .relatorios_assinaturas import gerar_assinaturas
from .relatorios_comum import (
    aplicar_filtros_processo,
    condicao_parado,
    data_arquivamento,
    descrever_filtros,
    situacao,
)
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
                                    "id_tipo_processo", "desde", "ate"}),
            data_base="pedido",
        ),
        tenant_id=tenant_id,
        niveis_permitidos=niveis_permitidos,
        max_rows=0,
    )

    return GerencialResposta(
        descricao_filtros=await descrever_filtros(db, f, tenant_id=tenant_id, por_secao=True),
        entrada=entrada,
        andamento=andamento,
        saida=saida,
        gargalos=gargalos,
        assinaturas=ass.totais,
    )

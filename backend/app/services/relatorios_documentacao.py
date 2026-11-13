"""Relatório de documentação (SI-34): documentos exigidos e complementações.

Uma linha por processo. Os números do grupo Documentação da página gerencial
são os totais destas listas (`contar_documentacao` conta a MESMA consulta de
cada visão), como nos outros grupos.

Situação dos documentos em SQL, espelhando `checklist_documentos._calcular_status`
(a tela do processo) — `test_status_documental_em_sql_igual_ao_checklist`
compara os dois:

- sem serviço, serviço de outra prefeitura/excluído, ou nenhum item com
  `key` → `sem_documentos_exigidos`;
- itens, mas nenhum obrigatório → `completo`;
- obrigatórios: nenhum enviado → `pendente`; parte → `parcial`; todos → `completo`.

"Enviado" = há anexo ativo, não excluído, ligado ao processo, com aquela
`documento_exigido_key`. O painel executivo (`dashboard._documental_periodo`)
diverge num caso: serviço só com itens opcionais lá é "sem documentos
exigidos". Aqui vale a tela do processo, que é o que o servidor vê.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import Boolean, and_, case, cast, func, literal, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from ..models import (
    Anexo,
    AnexoProcesso,
    Assunto,
    ComplementacaoDocumental,
    Processo,
    Servico,
    UnidadeTrabalho,
)
from ..schemas.relatorio import RelatorioFiltro
from ..schemas.relatorio_documentacao import (
    DocumentacaoProcessoRow,
    DocumentacaoTotais,
    RelatorioDocumentacaoResposta,
    VisaoDocumentacao,
)
from .relatorios_comum import (
    aplicar_filtros_processo,
    descrever_filtros,
    hora_local,
    no_intervalo,
)

Compl = ComplementacaoDocumental

# Por qual data o período conta em cada visão; None = situação de hoje.
DATA_DA_VISAO: dict[str, str | None] = {
    "documentos": "data de abertura",
    "doc_pendente": "data de abertura",
    "doc_parcial": "data de abertura",
    "doc_completo": "data de abertura",
    "compl_pedida": "data do pedido de complementação",
    "compl_aberta": None,
    "compl_respondida": "data da resposta do cidadão",
}
# Rótulos da situação, iguais no CSV e no PDF.
ROTULO_STATUS_DOC: dict[str, str] = {
    "sem_documentos_exigidos": "Sem documento exigido",
    "pendente": "Pendente",
    "parcial": "Parcial",
    "completo": "Completo",
}
ROTULO_COMPLEMENTACAO: dict[str, str] = {
    "aberta": "Aguardando o cidadão",
    "respondida": "Respondida",
    "cancelada": "Cancelada",
}
ROTULO_VISAO: dict[str, str] = {
    "documentos": "processos cujo serviço exige documentos",
    "doc_pendente": "documentos pendentes (nenhum obrigatório enviado)",
    "doc_parcial": "documentos parciais (parte dos obrigatórios enviada)",
    "doc_completo": "documentos completos",
    "compl_pedida": "com pedido de complementação",
    "compl_aberta": "complementação aguardando o cidadão (situação de hoje)",
    "compl_respondida": "complementação respondida pelo cidadão",
}


def _contagens_do_checklist(tenant_id: int):
    """(itens, obrigatórios, obrigatórios enviados) do processo, correlatos a
    `Processo` — três subconsultas sobre os itens do serviço dele."""
    docs = case(
        (func.jsonb_typeof(Servico.documentos_exigidos) == "array", Servico.documentos_exigidos),
        else_=cast(literal("[]"), JSONB),
    )
    item = func.jsonb_array_elements(docs).table_valued("value").lateral("item")
    chave = item.c.value.op("->>")("key")
    obrigatorio = func.coalesce(cast(item.c.value.op("->>")("obrigatorio"), Boolean), False)
    enviado = (
        select(AnexoProcesso.id)
        .join(Anexo, Anexo.id == AnexoProcesso.id_anexo)
        .where(
            AnexoProcesso.id_processo == Processo.id,
            AnexoProcesso.tenant_id == tenant_id,
            AnexoProcesso.excluido.is_(False),
            Anexo.tenant_id == tenant_id,
            Anexo.excluido.is_(False),
            Anexo.ativo.is_(True),
            Anexo.documento_exigido_key == chave,
        )
        # Fica DOIS níveis abaixo do `Processo` de fora: sem a correlação
        # explícita o SQLAlchemy põe `processo` de novo no FROM daqui, e a
        # pergunta vira "algum processo tem esse anexo?". E a explícita
        # desliga a automática — por isso o `item` também. Os dois erros
        # foram pegos por `test_status_documental_em_sql_igual_ao_checklist`.
        .correlate(Processo, item)
        .exists()
    )

    def contar(*cond):
        return (
            select(func.count())
            .select_from(Servico)
            .join(item, true())
            .where(
                Servico.id == Processo.id_servico,
                Servico.tenant_id == tenant_id,
                Servico.excluido.is_(False),
                func.coalesce(chave, "") != "",
                *cond,
            )
            .correlate(Processo)
            .scalar_subquery()
        )

    return contar(), contar(obrigatorio), contar(obrigatorio, enviado)


def _status(itens, obrig, envs):
    return case(
        (itens == 0, "sem_documentos_exigidos"),
        (obrig == 0, "completo"),
        (envs == 0, "pendente"),
        (envs < obrig, "parcial"),
        else_="completo",
    )


def _tem_complementacao(tenant_id: int, *cond):
    return (
        select(Compl.id)
        .where(
            Compl.id_processo == Processo.id,
            Compl.tenant_id == tenant_id,
            Compl.excluido.is_(False),
            *cond,
        )
        .correlate(Processo)
        .exists()
    )


def _recorte(
    f: RelatorioFiltro, visao: VisaoDocumentacao, *, tenant_id: int,
    niveis_permitidos: list[str] | None,
):
    """Ids e situação dos documentos dos processos de uma visão."""
    itens, obrig, envs = _contagens_do_checklist(tenant_id)
    base = (
        select(
            Processo.id.label("id"),
            itens.label("itens"),
            obrig.label("obrig"),
            envs.label("envs"),
        )
        .join(Assunto, Assunto.id == Processo.id_assunto)
    )
    if visao.startswith("doc_") or visao == "documentos":
        base = aplicar_filtros_processo(
            base, f, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos,
            coluna_data=Processo.data_hora_abertura,
        )
    else:
        # O período vale para a data do pedido (ou da resposta), não para a
        # abertura do processo.
        sem_periodo = f.model_copy(update={"desde": None, "ate": None})
        base = aplicar_filtros_processo(
            base, sem_periodo, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos,
            coluna_data=Processo.data_hora_abertura,
        )
        if visao == "compl_pedida":
            base = base.where(_tem_complementacao(tenant_id, *no_intervalo(Compl.criado_em, f.desde, f.ate)))
        elif visao == "compl_aberta":
            base = base.where(_tem_complementacao(tenant_id, Compl.status == "aberta"))
        else:  # compl_respondida
            base = base.where(
                _tem_complementacao(
                    tenant_id, Compl.respondido_em.is_not(None),
                    *no_intervalo(Compl.respondido_em, f.desde, f.ate),
                )
            )
    sub = base.subquery("base")
    status = _status(sub.c.itens, sub.c.obrig, sub.c.envs).label("status")
    stmt = select(sub.c.id, sub.c.obrig, sub.c.envs, status)
    if visao == "documentos":
        stmt = stmt.where(status != "sem_documentos_exigidos")
    elif visao.startswith("doc_"):
        stmt = stmt.where(status == visao.removeprefix("doc_"))
    return stmt.subquery("recorte")


async def contar_visao(
    db: AsyncSession, f: RelatorioFiltro, visao: VisaoDocumentacao, *, tenant_id: int,
    niveis_permitidos: list[str] | None,
) -> int:
    rec = _recorte(f, visao, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos)
    return int((await db.execute(select(func.count()).select_from(rec))).scalar_one())


async def dias_medio_resposta(
    db: AsyncSession, f: RelatorioFiltro, *, tenant_id: int, niveis_permitidos: list[str] | None,
) -> float | None:
    """Do pedido à resposta, dos pedidos respondidos no período (mesmo recorte
    de processo). Média por PEDIDO, não por processo."""
    sem_periodo = f.model_copy(update={"desde": None, "ate": None})
    stmt = aplicar_filtros_processo(
        select(func.avg(func.extract("epoch", Compl.respondido_em - Compl.criado_em) / 86400.0))
        .select_from(Compl)
        .join(Processo, Processo.id == Compl.id_processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .where(
            Compl.tenant_id == tenant_id,
            Compl.excluido.is_(False),
            Compl.respondido_em.is_not(None),
            *no_intervalo(Compl.respondido_em, f.desde, f.ate),
        ),
        sem_periodo, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos,
        coluna_data=Processo.data_hora_abertura,
    )
    v = (await db.execute(stmt)).scalar_one()
    return round(float(v), 1) if v is not None else None


async def gerar_documentacao(
    db: AsyncSession,
    f: RelatorioFiltro,
    visao: VisaoDocumentacao,
    *,
    tenant_id: int,
    # Sem default: ver `relatorios.gerar_relatorio`.
    niveis_permitidos: list[str] | None,
    max_rows: int = 1000,
) -> RelatorioDocumentacaoResposta:
    rec = _recorte(f, visao, tenant_id=tenant_id, niveis_permitidos=niveis_permitidos)
    aguardando = _tem_complementacao(tenant_id, Compl.status == "aberta")
    t = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(rec.c.status == "pendente"),
                func.count().filter(rec.c.status == "parcial"),
                func.count().filter(rec.c.status == "completo"),
                func.count().filter(aguardando),
            )
            .select_from(rec)
            .join(Processo, Processo.id == rec.c.id)
        )
    ).one()
    totais = DocumentacaoTotais(
        total=int(t[0]), pendentes=int(t[1]), parciais=int(t[2]), completos=int(t[3]),
        aguardando_cidadao=int(t[4]),
    )

    LocalAtual = aliased(UnidadeTrabalho, name="la")
    linhas = (
        await db.execute(
            select(Processo, rec.c.status, rec.c.obrig, rec.c.envs, Servico.nome, LocalAtual.unidade_trabalho)
            .select_from(rec)
            .join(Processo, Processo.id == rec.c.id)
            .join(Servico, and_(Servico.id == Processo.id_servico, Servico.tenant_id == tenant_id), isouter=True)
            .join(LocalAtual, LocalAtual.id == Processo.id_local_atual, isouter=True)
            .order_by(Processo.data_hora_abertura.desc(), Processo.id.desc())
            .limit(max_rows)
        )
    ).all()

    # O pedido mais recente de cada processo listado.
    ultimo: dict[int, ComplementacaoDocumental] = {}
    ids = [r[0].id for r in linhas]
    if ids:
        pedidos = (
            await db.execute(
                select(Compl)
                .where(Compl.id_processo.in_(ids), Compl.tenant_id == tenant_id, Compl.excluido.is_(False))
                .order_by(Compl.criado_em.asc(), Compl.id.asc())
            )
        ).scalars().all()
        por_proc: dict[int, list] = defaultdict(list)
        for c in pedidos:
            por_proc[c.id_processo].append(c)
        ultimo = {pid: lista[-1] for pid, lista in por_proc.items()}

    processos = []
    for p, status, obrig, envs, servico, local in linhas:
        c = ultimo.get(p.id)
        processos.append(
            DocumentacaoProcessoRow(
                id=p.id,
                numero_processo=p.numero_processo,
                data_hora_abertura=hora_local(p.data_hora_abertura),
                servico=servico,
                status_documental=status,
                obrigatorios_total=int(obrig or 0),
                obrigatorios_enviados=int(envs or 0),
                complementacao_status=c.status if c else None,
                complementacao_pedida_em=hora_local(c.criado_em) if c else None,
                complementacao_respondida_em=hora_local(c.respondido_em) if c else None,
                local_atual=local,
                nivel_sigilo=p.nivel_sigilo,
            )
        )

    descricao = await descrever_filtros(
        db, f, tenant_id=tenant_id, rotulo_data=DATA_DA_VISAO[visao] or "data de abertura"
    )
    descricao.insert(1, f"Mostrando: {ROTULO_VISAO[visao]}")
    return RelatorioDocumentacaoResposta(
        filtros_aplicados=f,
        visao=visao,
        descricao_filtros=descricao,
        totais=totais,
        processos=processos,
        cortado=len(processos) < totais.total,
    )

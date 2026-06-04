"""Agregações para o dashboard executivo — Fase 18 + PR 5a.

Fase 18 (a/b/c): visão volume/conclusão/SLA + comparativo período anterior +
breakdowns por tipo/assunto/unidade + série temporal. Filtros `periodo` e
`id_unidade`.

PR 5a: adiciona dimensão **serviço** (PR 4a) e indicadores agregados de
**checklist documental** (PR 4c) e **complementação documental** (PR 4d).

- `id_servico` (filtro): isola contadores e indicadores ao serviço escolhido;
  quando informado, **prevalece** e ignora `incluir_legado`.
- `incluir_legado` (filtro, default True): quando True, inclui processos
  legados (`id_servico IS NULL`) em todos os contadores onde fizer sentido
  e renderiza a linha "(sem serviço)" no ranking por serviço. Quando False,
  remove processos legados de todos os contadores periodais.
- `documental`: 3 contadores (pendente/parcial/completo) + 2 contadores
  auxiliares (com/sem id_servico no período). Calculados via CTE única
  com `jsonb_array_elements(servico.documentos_exigidos)` + LEFT JOIN em
  `anexo` — sem N+1, sem `calcular_checklist` por processo.
- `complementacao`: contadores de aberta/respondida/cancelada + tempo médio
  de resposta. Joins com `processo` para herdar os filtros do gestor.
- `por_servico`: top 10 serviços por nº de processos no período + linha
  "(sem serviço)" apenas quando `incluir_legado=True` e sem `id_servico`.

LGPD: nenhum CPF/nome/mensagem/motivo/filename/conteúdo no payload. Apenas
agregados, IDs e `servico.nome` (que já é público para o cidadão pelo portal).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    ComplementacaoDocumental,
    Movimentacao,
    Processo,
    TipoProcesso,
    UnidadeTrabalho,
    WorkflowInstance,
    WorkflowSlaAlerta,
)


def _aplicar_filtros_processo(stmt, *, id_unidade, id_servico, incluir_legado):
    """Aplica filtros de unidade/serviço/legado a uma query sobre `Processo`.

    Regra D-FILTROS: `id_servico` informado prevalece e ignora `incluir_legado`.
    """
    if id_unidade is not None:
        stmt = stmt.where(
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        )
    if id_servico is not None:
        stmt = stmt.where(Processo.id_servico == id_servico)
    elif not incluir_legado:
        stmt = stmt.where(Processo.id_servico.is_not(None))
    return stmt


async def _counts_intervalo(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> dict[str, Any]:
    """Computa contadores numéricos pro intervalo `[desde, ate)`.

    Usado pelo período atual E pelo anterior. NÃO inclui:
    - `ativos_hoje` (snapshot, não é janelado)
    - `sla.pendentes` (snapshot)
    - breakdowns + série temporal (só atual usa)
    """
    def _base_count():
        return select(func.count(Processo.id)).where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde,
            Processo.data_hora_abertura < ate,
        )

    abertos = (
        await db.execute(
            _aplicar_filtros_processo(
                _base_count(),
                id_unidade=id_unidade,
                id_servico=id_servico,
                incluir_legado=incluir_legado,
            )
        )
    ).scalar_one()

    externos = (
        await db.execute(
            _aplicar_filtros_processo(
                _base_count().where(Processo.externo.is_(True)),
                id_unidade=id_unidade,
                id_servico=id_servico,
                incluir_legado=incluir_legado,
            )
        )
    ).scalar_one()

    sigilosos = (
        await db.execute(
            _aplicar_filtros_processo(
                _base_count().where(Processo.publico.is_(False)),
                id_unidade=id_unidade,
                id_servico=id_servico,
                incluir_legado=incluir_legado,
            )
        )
    ).scalar_one()

    # Arquivados (via Movimentacao com id_arquivamento NOT NULL).
    # Movimentacao filtra por janela; Processo aplica filtros do gestor.
    arq_stmt = (
        select(func.count(Movimentacao.id))
        .select_from(Movimentacao)
        .join(Processo, Processo.id == Movimentacao.id_processo)
        .where(
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.id_arquivamento.is_not(None),
            Movimentacao.data_hora_movimentacao >= desde,
            Movimentacao.data_hora_movimentacao < ate,
            Processo.excluido.is_(False),
        )
    )
    arq_stmt = _aplicar_filtros_processo(
        arq_stmt,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    arquivados = (await db.execute(arq_stmt)).scalar_one()

    # Tempo médio de conclusão (mesmo set de Movimentacao).
    tm_stmt = (
        select(
            func.avg(
                func.extract(
                    "epoch",
                    Movimentacao.data_hora_movimentacao - Processo.data_hora_abertura,
                )
                / 86400.0
            )
        )
        .select_from(Movimentacao)
        .join(Processo, Processo.id == Movimentacao.id_processo)
        .where(
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.id_arquivamento.is_not(None),
            Movimentacao.data_hora_movimentacao >= desde,
            Movimentacao.data_hora_movimentacao < ate,
            Processo.excluido.is_(False),
        )
    )
    tm_stmt = _aplicar_filtros_processo(
        tm_stmt,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    tempo_medio = (await db.execute(tm_stmt)).scalar_one()
    tempo_medio = float(tempo_medio) if tempo_medio is not None else None

    # PR 5a-fix: SLA passa a respeitar filtros id_unidade/id_servico/
    # incluir_legado via JOIN WorkflowSlaAlerta → WorkflowInstance →
    # Processo. Sem JOIN, alertas de processos legados ou de outros
    # serviços apareceriam mesmo com filtro ativo.
    sla_resolv_stmt = (
        select(func.count(WorkflowSlaAlerta.id))
        .join(
            WorkflowInstance,
            WorkflowInstance.id == WorkflowSlaAlerta.id_workflow_instance,
        )
        .join(Processo, Processo.id == WorkflowInstance.id_processo)
        .where(
            WorkflowSlaAlerta.tenant_id == tenant_id,
            WorkflowSlaAlerta.resolvido_em.is_not(None),
            WorkflowSlaAlerta.resolvido_em >= desde,
            WorkflowSlaAlerta.resolvido_em < ate,
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
        )
    )
    sla_resolv_stmt = _aplicar_filtros_processo(
        sla_resolv_stmt,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    sla_resolv = (await db.execute(sla_resolv_stmt)).scalar_one()

    taxa = None
    if abertos and abertos > 0:
        taxa = round((arquivados / abertos) * 100, 1)

    return {
        "abertos": int(abertos),
        "externos": int(externos),
        "sigilosos": int(sigilosos),
        "arquivados": int(arquivados),
        "tempo_medio_dias": tempo_medio,
        "taxa_conclusao_pct": taxa,
        "sla_resolvidos": int(sla_resolv),
    }


def _processo_filtros_sql(
    *,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> tuple[str, dict[str, Any]]:
    """Gera trecho SQL extra para WHERE de `protocolos.processo p` + params."""
    where: list[str] = []
    params: dict[str, Any] = {}
    if id_unidade is not None:
        where.append("(p.id_unidade_proprietaria = :id_unidade OR p.id_local_atual = :id_unidade)")
        params["id_unidade"] = id_unidade
    if id_servico is not None:
        where.append("p.id_servico = :id_servico")
        params["id_servico"] = id_servico
    elif not incluir_legado:
        where.append("p.id_servico IS NOT NULL")
    return (" AND ".join(where), params) if where else ("", params)


async def _documental_periodo(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> dict[str, Any]:
    """Agregados de checklist documental para processos abertos no período.

    Distribui contagens em `com_id_servico_periodo` / `sem_id_servico_periodo`
    para diagnóstico do gestor (saber quanto da operação ainda é legado), e
    em `checklist_pendente / parcial / completo / sem_documentos_exigidos`
    para visão de gargalo documental.

    PR 5a-fix: a regra de status agora ESPELHA exatamente
    `services/checklist_documentos._calcular_status`:
    - obrigatorios = 0 (serviço sem documentos exigidos OU lista vazia OU
      JSONB null/não-array OU só itens opcionais) → `sem_documentos_exigidos`;
    - obrigatorios > 0 e nenhum enviado → `pendente`;
    - obrigatorios > 0 e 0 < enviados < total → `parcial`;
    - obrigatorios > 0 e enviados = total → `completo`.

    Antes, processos com obrigatorios=0 entravam em `completo` (trivial),
    misturando com casos genuinamente concluídos. Agora ficam separados.

    Processo SEM `id_servico` continua em `sem_id_servico_periodo`, fora
    de pendente/parcial/completo/sem_documentos_exigidos (esses 4 são
    todos restritos a `id_servico IS NOT NULL` pela CTE).
    """
    # Contadores básicos com/sem id_servico (respeitam id_unidade; `id_servico`
    # filtra para zero quando informado pq há filtro `IS NULL/NOT NULL`).
    base_periodo = select(func.count(Processo.id)).where(
        Processo.tenant_id == tenant_id,
        Processo.excluido.is_(False),
        Processo.data_hora_abertura >= desde,
        Processo.data_hora_abertura < ate,
    )
    if id_unidade is not None:
        base_periodo = base_periodo.where(
            (Processo.id_unidade_proprietaria == id_unidade)
            | (Processo.id_local_atual == id_unidade)
        )

    com_q = base_periodo.where(Processo.id_servico.is_not(None))
    sem_q = base_periodo.where(Processo.id_servico.is_(None))
    if id_servico is not None:
        com_q = com_q.where(Processo.id_servico == id_servico)
        sem_q = sem_q.where(literal_column("false"))  # filtro de serviço zera legado
    elif not incluir_legado:
        sem_q = sem_q.where(literal_column("false"))

    com_id_servico = int((await db.execute(com_q)).scalar_one())
    sem_id_servico = int((await db.execute(sem_q)).scalar_one())

    # CTE de checklist agregado por processo.
    extra_where, extra_params = _processo_filtros_sql(
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=True,  # CTE já filtra id_servico IS NOT NULL — redundante senão
    )
    extra_clause = f" AND {extra_where}" if extra_where else ""

    sql = text(
        f"""
        WITH docs_exigidos AS (
            SELECT s.id AS id_servico,
                   (item ->> 'key') AS doc_key,
                   (COALESCE(item ->> 'obrigatorio', 'false'))::bool AS obrigatorio
            FROM protocolos.servico s,
                 LATERAL jsonb_array_elements(
                     CASE
                         WHEN jsonb_typeof(s.documentos_exigidos) = 'array'
                         THEN s.documentos_exigidos
                         ELSE '[]'::jsonb
                     END
                 ) AS item
            WHERE s.tenant_id = :tenant_id
              AND s.excluido = false
        ),
        processos_filtrados AS (
            SELECT p.id, p.id_servico
            FROM protocolos.processo p
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              AND p.id_servico IS NOT NULL
              AND p.data_hora_abertura >= :desde
              AND p.data_hora_abertura <  :ate
              {extra_clause}
        ),
        processo_doc AS (
            -- Uma linha por par (processo, doc_exigido). EXISTS evita que
            -- múltiplos anexos do mesmo processo inflem o COUNT.
            SELECT pf.id AS processo_id,
                   d.doc_key,
                   d.obrigatorio,
                   EXISTS (
                       SELECT 1
                       FROM protocolos.anexo_processo ap
                       JOIN protocolos.anexo a
                            ON a.id = ap.id_anexo
                           AND a.excluido = false
                           AND a.ativo = true
                           AND a.documento_exigido_key = d.doc_key
                           AND a.tenant_id = :tenant_id
                       WHERE ap.id_processo = pf.id
                         AND ap.excluido = false
                         AND ap.tenant_id = :tenant_id
                   ) AS enviado
            FROM processos_filtrados pf
            LEFT JOIN docs_exigidos d ON d.id_servico = pf.id_servico
        ),
        por_processo AS (
            SELECT processo_id,
                   COUNT(doc_key) FILTER (WHERE obrigatorio) AS obrigatorios,
                   COUNT(doc_key) FILTER (
                       WHERE obrigatorio AND enviado
                   ) AS obrigatorios_enviados
            FROM processo_doc
            GROUP BY processo_id
        )
        SELECT
            COUNT(*) FILTER (
                WHERE obrigatorios > 0 AND obrigatorios_enviados = 0
            ) AS pendente,
            COUNT(*) FILTER (
                WHERE obrigatorios > 0
                  AND obrigatorios_enviados > 0
                  AND obrigatorios_enviados < obrigatorios
            ) AS parcial,
            COUNT(*) FILTER (
                WHERE obrigatorios > 0 AND obrigatorios_enviados = obrigatorios
            ) AS completo,
            COUNT(*) FILTER (
                WHERE obrigatorios = 0
            ) AS sem_documentos
        FROM por_processo;
        """
    )
    row = (
        await db.execute(
            sql,
            {
                "tenant_id": tenant_id,
                "desde": desde,
                "ate": ate,
                **extra_params,
            },
        )
    ).one()
    return {
        "com_id_servico_periodo": com_id_servico,
        "sem_id_servico_periodo": sem_id_servico,
        "checklist_pendente": int(row.pendente or 0),
        "checklist_parcial": int(row.parcial or 0),
        "checklist_completo": int(row.completo or 0),
        "sem_documentos_exigidos": int(row.sem_documentos or 0),
    }


async def _complementacao_periodo(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> dict[str, Any]:
    """Agregados da `complementacao_documental` no período.

    Honra `id_unidade`/`id_servico`/`incluir_legado` via JOIN em `processo` —
    permite ao gestor restringir a visão à mesma fatia operacional.
    """
    def _base(stmt):
        stmt = stmt.where(
            ComplementacaoDocumental.tenant_id == tenant_id,
            ComplementacaoDocumental.excluido.is_(False),
        )
        # JOIN obrigatório com processo p/ honrar filtros do gestor.
        stmt = stmt.join(
            Processo, Processo.id == ComplementacaoDocumental.id_processo
        ).where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
        )
        return _aplicar_filtros_processo(
            stmt,
            id_unidade=id_unidade,
            id_servico=id_servico,
            incluir_legado=incluir_legado,
        )

    # Snapshot (status atual)
    abertas_now_stmt = _base(
        select(func.count(ComplementacaoDocumental.id))
    ).where(ComplementacaoDocumental.status == "aberta")
    abertas_now = (await db.execute(abertas_now_stmt)).scalar_one()

    proc_abertas_stmt = _base(
        select(func.count(func.distinct(ComplementacaoDocumental.id_processo)))
    ).where(ComplementacaoDocumental.status == "aberta")
    processos_com_aberta = (await db.execute(proc_abertas_stmt)).scalar_one()

    # Períodos (não usam status — filtram pela coluna temporal)
    solicit_stmt = _base(
        select(func.count(ComplementacaoDocumental.id))
    ).where(
        ComplementacaoDocumental.criado_em >= desde,
        ComplementacaoDocumental.criado_em < ate,
    )
    solicitadas = (await db.execute(solicit_stmt)).scalar_one()

    resp_stmt = _base(
        select(func.count(ComplementacaoDocumental.id))
    ).where(
        ComplementacaoDocumental.respondido_em.is_not(None),
        ComplementacaoDocumental.respondido_em >= desde,
        ComplementacaoDocumental.respondido_em < ate,
    )
    respondidas = (await db.execute(resp_stmt)).scalar_one()

    canc_stmt = _base(
        select(func.count(ComplementacaoDocumental.id))
    ).where(
        ComplementacaoDocumental.cancelado_em.is_not(None),
        ComplementacaoDocumental.cancelado_em >= desde,
        ComplementacaoDocumental.cancelado_em < ate,
    )
    canceladas = (await db.execute(canc_stmt)).scalar_one()

    # Tempo médio de resposta (em dias) — só sobre respondidas no período.
    tmr_stmt = _base(
        select(
            func.avg(
                func.extract(
                    "epoch",
                    ComplementacaoDocumental.respondido_em
                    - ComplementacaoDocumental.criado_em,
                )
                / 86400.0
            )
        )
    ).where(
        ComplementacaoDocumental.respondido_em.is_not(None),
        ComplementacaoDocumental.respondido_em >= desde,
        ComplementacaoDocumental.respondido_em < ate,
    )
    tmr_val = (await db.execute(tmr_stmt)).scalar_one()
    tempo_medio_resp = float(tmr_val) if tmr_val is not None else None

    return {
        "abertas_agora": int(abertas_now),
        "solicitadas_periodo": int(solicitadas),
        "respondidas_periodo": int(respondidas),
        "canceladas_periodo": int(canceladas),
        "processos_com_aberta_agora": int(processos_com_aberta),
        "tempo_medio_resposta_dias": tempo_medio_resp,
    }


async def _prazos_kpis(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> dict[str, Any]:
    """Bloco `prazos` (PR 5b). 2 queries SQL agregadas — snapshot + período.

    Snapshot: processos NÃO concluídos (sem Movimentacao ativa de
    arquivamento). Período: concluídos por arquivamento em [desde, ate).
    Honra filtros do gestor via `_processo_filtros_sql` (mesmo padrão PR 5a).

    Regra D-VENCENDO replicada em SQL: `GREATEST(1, CEIL(snap * 0.2))`.
    """
    extra_where, extra_params = _processo_filtros_sql(
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    extra_clause = f" AND {extra_where}" if extra_where else ""

    # ===== Snapshot — processos NÃO concluídos =====
    sql_snapshot = text(
        f"""
        WITH em_andamento AS (
            SELECT p.id,
                   p.data_hora_abertura,
                   p.prazo_servico_dias_snapshot AS snap
            FROM protocolos.processo p
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              AND NOT EXISTS (
                  SELECT 1
                  FROM protocolos.movimentacao mv
                  WHERE mv.id_processo = p.id
                    AND mv.tenant_id = :tenant_id
                    AND mv.excluido = false
                    AND mv.ativo = true
                    AND mv.id_arquivamento IS NOT NULL
              )
              {extra_clause}
        ),
        com_prazo AS (
            SELECT id,
                   data_hora_abertura + (snap * INTERVAL '1 day') AS prazo_previsto,
                   GREATEST(1, CEIL(snap * 0.2)) AS limiar
            FROM em_andamento
            WHERE snap IS NOT NULL
        )
        SELECT
            (SELECT COUNT(*) FROM em_andamento WHERE snap IS NULL) AS sem_prazo,
            COUNT(*) FILTER (
                WHERE (prazo_previsto - NOW()) > (limiar * INTERVAL '1 day')
            ) AS dentro_do_prazo,
            COUNT(*) FILTER (
                WHERE NOW() <= prazo_previsto
                  AND (prazo_previsto - NOW()) <= (limiar * INTERVAL '1 day')
            ) AS vencendo,
            COUNT(*) FILTER (WHERE NOW() > prazo_previsto) AS atrasado,
            AVG(EXTRACT(EPOCH FROM (NOW() - prazo_previsto)) / 86400.0)
                FILTER (WHERE NOW() > prazo_previsto) AS atraso_medio_andamento,
            COUNT(*) FILTER (WHERE NOW() > prazo_previsto) AS qtd_atrasado_for_avg
        FROM com_prazo;
        """
    )
    snap_row = (
        await db.execute(
            sql_snapshot,
            {"tenant_id": tenant_id, **extra_params},
        )
    ).one()

    # ===== Período — concluídos por arquivamento em [desde, ate) =====
    sql_periodo = text(
        f"""
        WITH ultimo_arquiv AS (
            SELECT DISTINCT ON (mv.id_processo)
                   mv.id_processo,
                   mv.data_hora_movimentacao AS data_conclusao
            FROM protocolos.movimentacao mv
            WHERE mv.tenant_id = :tenant_id
              AND mv.excluido = false
              AND mv.ativo = true
              AND mv.id_arquivamento IS NOT NULL
              AND mv.data_hora_movimentacao >= :desde
              AND mv.data_hora_movimentacao <  :ate
            ORDER BY mv.id_processo, mv.data_hora_movimentacao DESC
        ),
        concluidos AS (
            SELECT p.id,
                   p.data_hora_abertura,
                   p.prazo_servico_dias_snapshot AS snap,
                   ua.data_conclusao
            FROM ultimo_arquiv ua
            JOIN protocolos.processo p ON p.id = ua.id_processo
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              {extra_clause}
        )
        SELECT
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao <= data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS concluido_no_prazo,
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS concluido_atrasado,
            AVG(
                EXTRACT(
                    EPOCH FROM (data_conclusao
                                - (data_hora_abertura + (snap * INTERVAL '1 day')))
                ) / 86400.0
            ) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS atraso_medio_concluidos,
            COUNT(*) FILTER (
                WHERE snap IS NOT NULL
                  AND data_conclusao >  data_hora_abertura + (snap * INTERVAL '1 day')
            ) AS qtd_concluido_atrasado_for_avg
        FROM concluidos;
        """
    )
    per_row = (
        await db.execute(
            sql_periodo,
            {"tenant_id": tenant_id, "desde": desde, "ate": ate, **extra_params},
        )
    ).one()

    sem_prazo = int(snap_row.sem_prazo or 0)
    dentro = int(snap_row.dentro_do_prazo or 0)
    vencendo = int(snap_row.vencendo or 0)
    atrasado = int(snap_row.atrasado or 0)
    conc_no_prazo = int(per_row.concluido_no_prazo or 0)
    conc_atrasado = int(per_row.concluido_atrasado or 0)

    com_prazo_andamento = dentro + vencendo + atrasado
    pct = (
        round(((dentro + vencendo) / com_prazo_andamento) * 100, 1)
        if com_prazo_andamento > 0
        else None
    )

    # Média ponderada do atraso (em-andamento + concluídos atrasado no período).
    qtd_at_a = int(snap_row.qtd_atrasado_for_avg or 0)
    qtd_at_c = int(per_row.qtd_concluido_atrasado_for_avg or 0)
    soma_at = (
        float(snap_row.atraso_medio_andamento or 0.0) * qtd_at_a
        + float(per_row.atraso_medio_concluidos or 0.0) * qtd_at_c
    )
    qtd_total_at = qtd_at_a + qtd_at_c
    tempo_medio_atraso = (
        round(soma_at / qtd_total_at, 1) if qtd_total_at > 0 else None
    )

    return {
        "sem_prazo": sem_prazo,
        "dentro_do_prazo": dentro,
        "vencendo": vencendo,
        "atrasado": atrasado,
        "concluido_no_prazo_periodo": conc_no_prazo,
        "concluido_atrasado_periodo": conc_atrasado,
        "percentual_no_prazo": pct,
        "tempo_medio_atraso_dias": tempo_medio_atraso,
    }


async def _breakdown_servico(
    db: AsyncSession,
    *,
    tenant_id: int,
    desde: datetime,
    ate: datetime,
    id_unidade: int | None,
    id_servico: int | None,
    incluir_legado: bool,
) -> list[dict[str, Any]]:
    """Top 10 serviços (por nº de processos no período) + linha "(sem serviço)"
    quando `incluir_legado=True` e sem filtro de `id_servico`.

    Estratégia: 2 queries SQL agregadas — uma por id_servico (top 10), outra
    para o checklist por id_servico (CTE), combinadas no Python.
    """
    extra_where, extra_params = _processo_filtros_sql(
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=True,  # CTE filtra IS NOT NULL — incluir_legado tratado
                              # à parte (linha "(sem serviço)" no fim)
    )
    extra_clause = f" AND {extra_where}" if extra_where else ""

    # PR 5a-fix: as subqueries de complementação usam alias `pp` (não `p`).
    # `extra_clause` traz `p.*` filters da função `_processo_filtros_sql`;
    # construímos uma cláusula equivalente com alias `pp` para honrar o
    # filtro `id_unidade` nos subindicadores de complementação (e na linha
    # legado). Não introduz parâmetros novos — reutiliza :id_unidade.
    pp_id_unidade_clause = (
        " AND (pp.id_unidade_proprietaria = :id_unidade "
        "OR pp.id_local_atual = :id_unidade)"
        if id_unidade is not None
        else ""
    )

    # Query A: contagem por serviço + sub-agregados de complementacao por id_servico
    # (subqueries escalares evitam multi-join sem GROUP BY).
    sql_servicos = text(
        f"""
        WITH processos_no_periodo AS (
            SELECT p.id, p.id_servico
            FROM protocolos.processo p
            WHERE p.tenant_id = :tenant_id
              AND p.excluido = false
              AND p.id_servico IS NOT NULL
              AND p.data_hora_abertura >= :desde
              AND p.data_hora_abertura <  :ate
              {extra_clause}
        ),
        contagens_por_servico AS (
            SELECT id_servico, COUNT(*) AS qt
            FROM processos_no_periodo
            GROUP BY id_servico
            ORDER BY qt DESC
            LIMIT 10
        )
        SELECT
            s.id AS id_servico,
            s.nome AS nome,
            c.qt AS qt,
            (
                SELECT COUNT(*)
                FROM protocolos.complementacao_documental cd
                JOIN protocolos.processo pp ON pp.id = cd.id_processo
                WHERE cd.tenant_id = :tenant_id
                  AND cd.excluido = false
                  AND cd.status = 'aberta'
                  AND pp.tenant_id = :tenant_id
                  AND pp.excluido = false
                  AND pp.id_servico = s.id
                  {pp_id_unidade_clause}
            ) AS compl_abertas,
            (
                SELECT COUNT(*)
                FROM protocolos.complementacao_documental cd
                JOIN protocolos.processo pp ON pp.id = cd.id_processo
                WHERE cd.tenant_id = :tenant_id
                  AND cd.excluido = false
                  AND cd.respondido_em IS NOT NULL
                  AND cd.respondido_em >= :desde
                  AND cd.respondido_em <  :ate
                  AND pp.tenant_id = :tenant_id
                  AND pp.excluido = false
                  AND pp.id_servico = s.id
                  {pp_id_unidade_clause}
            ) AS compl_respondidas,
            -- PR 5b — atrasados: processos NÃO concluídos com prazo já vencido.
            -- Snapshot atual (independente do recorte de período), honra id_unidade.
            (
                SELECT COUNT(*)
                FROM protocolos.processo pp
                WHERE pp.tenant_id = :tenant_id
                  AND pp.excluido = false
                  AND pp.id_servico = s.id
                  AND pp.prazo_servico_dias_snapshot IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM protocolos.movimentacao mv
                      WHERE mv.id_processo = pp.id
                        AND mv.tenant_id = :tenant_id
                        AND mv.excluido = false
                        AND mv.ativo = true
                        AND mv.id_arquivamento IS NOT NULL
                  )
                  AND NOW() > pp.data_hora_abertura
                              + (pp.prazo_servico_dias_snapshot * INTERVAL '1 day')
                  {pp_id_unidade_clause}
            ) AS atrasados
        FROM contagens_por_servico c
        JOIN protocolos.servico s ON s.id = c.id_servico
        ORDER BY c.qt DESC;
        """
    )
    rows_serv = (
        await db.execute(
            sql_servicos,
            {
                "tenant_id": tenant_id,
                "desde": desde,
                "ate": ate,
                **extra_params,
            },
        )
    ).all()

    # Query B: checklist agregado por id_servico (top 10) — mesmo padrão do
    # _documental_periodo, mas com GROUP BY id_servico depois do COUNT por
    # processo.
    ids_top = [int(r.id_servico) for r in rows_serv]
    checklist_por_servico: dict[int, dict[str, int]] = {}
    if ids_top:
        sql_check = text(
            f"""
            WITH docs_exigidos AS (
                SELECT s.id AS id_servico,
                       (item ->> 'key') AS doc_key,
                       (COALESCE(item ->> 'obrigatorio', 'false'))::bool AS obrigatorio
                FROM protocolos.servico s,
                     LATERAL jsonb_array_elements(
                         CASE
                             WHEN jsonb_typeof(s.documentos_exigidos) = 'array'
                             THEN s.documentos_exigidos
                             ELSE '[]'::jsonb
                         END
                     ) AS item
                WHERE s.tenant_id = :tenant_id
                  AND s.excluido = false
                  AND s.id = ANY(:ids)
            ),
            processos_filtrados AS (
                SELECT p.id, p.id_servico
                FROM protocolos.processo p
                WHERE p.tenant_id = :tenant_id
                  AND p.excluido = false
                  AND p.id_servico = ANY(:ids)
                  AND p.data_hora_abertura >= :desde
                  AND p.data_hora_abertura <  :ate
                  {extra_clause}
            ),
            processo_doc AS (
                SELECT pf.id AS processo_id,
                       pf.id_servico,
                       d.doc_key,
                       d.obrigatorio,
                       EXISTS (
                           SELECT 1
                           FROM protocolos.anexo_processo ap
                           JOIN protocolos.anexo a
                                ON a.id = ap.id_anexo
                               AND a.excluido = false
                               AND a.ativo = true
                               AND a.documento_exigido_key = d.doc_key
                               AND a.tenant_id = :tenant_id
                           WHERE ap.id_processo = pf.id
                             AND ap.excluido = false
                             AND ap.tenant_id = :tenant_id
                       ) AS enviado
                FROM processos_filtrados pf
                LEFT JOIN docs_exigidos d ON d.id_servico = pf.id_servico
            ),
            por_processo AS (
                SELECT processo_id,
                       id_servico,
                       COUNT(doc_key) FILTER (WHERE obrigatorio) AS obrigatorios,
                       COUNT(doc_key) FILTER (
                           WHERE obrigatorio AND enviado
                       ) AS obrigatorios_enviados
                FROM processo_doc
                GROUP BY processo_id, id_servico
            )
            SELECT
                id_servico,
                COUNT(*) FILTER (
                    WHERE obrigatorios > 0 AND obrigatorios_enviados = 0
                ) AS pendente,
                COUNT(*) FILTER (
                    WHERE obrigatorios > 0
                      AND obrigatorios_enviados > 0
                      AND obrigatorios_enviados < obrigatorios
                ) AS parcial,
                COUNT(*) FILTER (
                    WHERE obrigatorios > 0 AND obrigatorios_enviados = obrigatorios
                ) AS completo,
                COUNT(*) FILTER (
                    WHERE obrigatorios = 0
                ) AS sem_documentos
            FROM por_processo
            GROUP BY id_servico;
            """
        )
        check_rows = (
            await db.execute(
                sql_check,
                {
                    "tenant_id": tenant_id,
                    "desde": desde,
                    "ate": ate,
                    "ids": ids_top,
                    **extra_params,
                },
            )
        ).all()
        checklist_por_servico = {
            int(r.id_servico): {
                "pendente": int(r.pendente or 0),
                "parcial": int(r.parcial or 0),
                "completo": int(r.completo or 0),
                "sem_documentos_exigidos": int(r.sem_documentos or 0),
            }
            for r in check_rows
        }

    breakdown: list[dict[str, Any]] = []
    _CK_ZERO = {"pendente": 0, "parcial": 0, "completo": 0, "sem_documentos_exigidos": 0}
    for r in rows_serv:
        ck = checklist_por_servico.get(int(r.id_servico), _CK_ZERO)
        breakdown.append(
            {
                "id_servico": int(r.id_servico),
                "nome": r.nome,
                "count": int(r.qt),
                "complementacoes_abertas": int(r.compl_abertas or 0),
                "complementacoes_respondidas_periodo": int(r.compl_respondidas or 0),
                "checklist_pendente": ck["pendente"],
                "checklist_parcial": ck["parcial"],
                "checklist_completo": ck["completo"],
                "sem_documentos_exigidos": ck["sem_documentos_exigidos"],
                "atrasados": int(r.atrasados or 0),  # PR 5b
            }
        )

    # Linha "(sem serviço)" — só quando incluir_legado=True E sem filtro de id_servico.
    if incluir_legado and id_servico is None:
        legado_qt = (
            await db.execute(
                _aplicar_filtros_processo(
                    select(func.count(Processo.id)).where(
                        Processo.tenant_id == tenant_id,
                        Processo.excluido.is_(False),
                        Processo.data_hora_abertura >= desde,
                        Processo.data_hora_abertura < ate,
                        Processo.id_servico.is_(None),
                    ),
                    id_unidade=id_unidade,
                    id_servico=None,
                    incluir_legado=True,
                )
            )
        ).scalar_one()
        if legado_qt > 0:
            # PR 5a-fix: aplicar id_unidade também nas complementações da
            # linha legado — antes só filtrava tenant + id_servico IS NULL,
            # podendo mostrar complementações de outras unidades.
            def _aplicar_unid(stmt):
                if id_unidade is None:
                    return stmt
                return stmt.where(
                    (Processo.id_unidade_proprietaria == id_unidade)
                    | (Processo.id_local_atual == id_unidade)
                )

            legado_compl_abertas = (
                await db.execute(
                    _aplicar_unid(
                        select(func.count(ComplementacaoDocumental.id))
                        .join(
                            Processo,
                            Processo.id == ComplementacaoDocumental.id_processo,
                        )
                        .where(
                            ComplementacaoDocumental.tenant_id == tenant_id,
                            ComplementacaoDocumental.excluido.is_(False),
                            ComplementacaoDocumental.status == "aberta",
                            Processo.tenant_id == tenant_id,
                            Processo.excluido.is_(False),
                            Processo.id_servico.is_(None),
                        )
                    )
                )
            ).scalar_one()
            legado_compl_respondidas = (
                await db.execute(
                    _aplicar_unid(
                        select(func.count(ComplementacaoDocumental.id))
                        .join(
                            Processo,
                            Processo.id == ComplementacaoDocumental.id_processo,
                        )
                        .where(
                            ComplementacaoDocumental.tenant_id == tenant_id,
                            ComplementacaoDocumental.excluido.is_(False),
                            ComplementacaoDocumental.respondido_em.is_not(None),
                            ComplementacaoDocumental.respondido_em >= desde,
                            ComplementacaoDocumental.respondido_em < ate,
                            Processo.tenant_id == tenant_id,
                            Processo.excluido.is_(False),
                            Processo.id_servico.is_(None),
                        )
                    )
                )
            ).scalar_one()
            breakdown.append(
                {
                    "id_servico": None,
                    "nome": "(sem serviço)",
                    "count": int(legado_qt),
                    "complementacoes_abertas": int(legado_compl_abertas or 0),
                    "complementacoes_respondidas_periodo": int(
                        legado_compl_respondidas or 0
                    ),
                    # Sem checklist — legado é sem_documentos_exigidos por
                    # definição (sem id_servico → sem documentos exigidos).
                    "checklist_pendente": 0,
                    "checklist_parcial": 0,
                    "checklist_completo": 0,
                    "sem_documentos_exigidos": int(legado_qt),
                    # PR 5b — legado é sem_prazo por definição (sem snapshot).
                    "atrasados": 0,
                }
            )

    return breakdown


async def kpis(
    db: AsyncSession,
    *,
    tenant_id: int,
    periodo_dias: int = 30,
    id_unidade: int | None = None,
    id_servico: int | None = None,
    incluir_legado: bool = True,
) -> dict[str, Any]:
    """Devolve um payload pronto pra UI render. Forma JSON estável documentada
    no schema Pydantic correspondente.

    PR 5a: `id_servico` e `incluir_legado` propagam-se a TODOS os contadores
    janelados; quando `id_servico` é dado, prevalece sobre `incluir_legado`.
    """
    if periodo_dias not in (7, 30, 90, 365):
        periodo_dias = 30
    now = datetime.utcnow()
    desde_atual = now - timedelta(days=periodo_dias)
    desde_anterior = now - timedelta(days=2 * periodo_dias)

    def _base_processo():
        stmt = select(Processo).where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
        )
        return _aplicar_filtros_processo(
            stmt,
            id_unidade=id_unidade,
            id_servico=id_servico,
            incluir_legado=incluir_legado,
        )

    atual = await _counts_intervalo(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    anterior = await _counts_intervalo(
        db,
        tenant_id=tenant_id,
        desde=desde_anterior,
        ate=desde_atual,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )

    # Ativos hoje (snapshot — não janelado)
    ativos_hoje_stmt = _base_processo().where(Processo.ativo.is_(True))
    sq_ah = ativos_hoje_stmt.subquery()
    ativos_hoje = (await db.execute(select(func.count(sq_ah.c.id)))).scalar_one()

    # SLA pendentes agora (snapshot — não janelado). PR 5a-fix: respeita
    # filtros id_unidade/id_servico/incluir_legado via WorkflowInstance →
    # Processo.
    sla_pend_stmt = (
        select(func.count(WorkflowSlaAlerta.id))
        .join(
            WorkflowInstance,
            WorkflowInstance.id == WorkflowSlaAlerta.id_workflow_instance,
        )
        .join(Processo, Processo.id == WorkflowInstance.id_processo)
        .where(
            WorkflowSlaAlerta.tenant_id == tenant_id,
            WorkflowSlaAlerta.resolvido_em.is_(None),
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
        )
    )
    sla_pend_stmt = _aplicar_filtros_processo(
        sla_pend_stmt,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    sla_pendentes = (await db.execute(sla_pend_stmt)).scalar_one()

    def _aplicar_break(stmt):
        return _aplicar_filtros_processo(
            stmt,
            id_unidade=id_unidade,
            id_servico=id_servico,
            incluir_legado=incluir_legado,
        )

    # ===== Breakdown por tipo_processo (top 5) =====
    tipo_q = _aplicar_break(
        select(
            TipoProcesso.tipo_processo.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .join(TipoProcesso, TipoProcesso.id == Assunto.id_tipo_processo)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
            Processo.data_hora_abertura < now,
        )
        .group_by(TipoProcesso.tipo_processo)
        .order_by(func.count(Processo.id).desc())
        .limit(5)
    )
    por_tipo = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(tipo_q)).all()
    ]

    # ===== Breakdown por assunto (top 10) =====
    assunto_q = _aplicar_break(
        select(
            Assunto.assunto.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(Assunto, Assunto.id == Processo.id_assunto)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
            Processo.data_hora_abertura < now,
        )
        .group_by(Assunto.assunto)
        .order_by(func.count(Processo.id).desc())
        .limit(10)
    )
    por_assunto = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(assunto_q)).all()
    ]

    # ===== Breakdown por unidade proprietária (top 10) =====
    unid_q = _aplicar_break(
        select(
            UnidadeTrabalho.unidade_trabalho.label("label"),
            func.count(Processo.id).label("count"),
        )
        .select_from(Processo)
        .join(UnidadeTrabalho, UnidadeTrabalho.id == Processo.id_unidade_proprietaria)
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
            Processo.data_hora_abertura < now,
        )
        .group_by(UnidadeTrabalho.unidade_trabalho)
        .order_by(func.count(Processo.id).desc())
        .limit(10)
    )
    por_unidade = [
        {"label": lbl, "count": int(cnt)}
        for lbl, cnt in (await db.execute(unid_q)).all()
    ]

    # ===== Série temporal (abertos por dia) =====
    serie_q = _aplicar_break(
        select(
            func.date_trunc("day", Processo.data_hora_abertura).label("dia"),
            func.count(Processo.id).label("count"),
        )
        .where(
            Processo.tenant_id == tenant_id,
            Processo.excluido.is_(False),
            Processo.data_hora_abertura >= desde_atual,
            Processo.data_hora_abertura < now,
        )
        .group_by(literal_column("1"))
        .order_by(literal_column("1"))
    )
    serie_rows = (await db.execute(serie_q)).all()
    serie_temporal = [
        {"dia": dia.isoformat(), "count": int(cnt)} for dia, cnt in serie_rows
    ]

    # ===== PR 5a — blocos novos =====
    documental = await _documental_periodo(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    complementacao = await _complementacao_periodo(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    por_servico = await _breakdown_servico(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )
    prazos = await _prazos_kpis(
        db,
        tenant_id=tenant_id,
        desde=desde_atual,
        ate=now,
        id_unidade=id_unidade,
        id_servico=id_servico,
        incluir_legado=incluir_legado,
    )

    return {
        "periodo_dias": periodo_dias,
        "id_unidade": id_unidade,
        "volume": {
            "abertos_periodo": atual["abertos"],
            "ativos_hoje": int(ativos_hoje),
            "externos_periodo": atual["externos"],
            "sigilosos_periodo": atual["sigilosos"],
        },
        "conclusao": {
            "arquivados_periodo": atual["arquivados"],
            "taxa_conclusao_pct": atual["taxa_conclusao_pct"],
            "tempo_medio_dias": atual["tempo_medio_dias"],
        },
        "sla": {
            "pendentes": int(sla_pendentes),
            "resolvidos_periodo": atual["sla_resolvidos"],
        },
        "comparativo": {
            "abertos_anterior": anterior["abertos"],
            "externos_anterior": anterior["externos"],
            "sigilosos_anterior": anterior["sigilosos"],
            "arquivados_anterior": anterior["arquivados"],
            "tempo_medio_dias_anterior": anterior["tempo_medio_dias"],
            "taxa_conclusao_pct_anterior": anterior["taxa_conclusao_pct"],
            "sla_resolvidos_anterior": anterior["sla_resolvidos"],
        },
        "por_tipo": por_tipo,
        "por_assunto": por_assunto,
        "por_unidade": por_unidade,
        "serie_temporal": serie_temporal,
        # PR 5a
        "documental": documental,
        "complementacao": complementacao,
        "por_servico": por_servico,
        # PR 5b
        "prazos": prazos,
    }

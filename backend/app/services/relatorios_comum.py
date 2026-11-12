"""Regras comuns dos relatórios de protocolo (SI-34).

Cada relatório filtra e conta processos. As decisões que precisam dar o mesmo
número em todos eles moram aqui, uma vez só:

- **Período em hora local.** As colunas de data são `TIMESTAMP` sem fuso e
  guardam UTC (Postgres em UTC, `NOW()`). Quem pede "até 10/11" quer o fim do
  dia 10 em Itaitinga, que em UTC é 11/11 03:00. Comparar a data local direto
  com a coluna deixava de fora tudo o que foi aberto depois das 21h.
- **Situação real.** Arquivado e em trânsito vêm das mesmas condições das
  caixas de trabalho (`processos.condicao_*`); `Processo.ativo` não é escrito
  por nenhum caminho e não entra em conta nenhuma.
- **Unidade.** "Dona" é a unidade proprietária escolhida na abertura (decisão
  de produto de 2026-11-10). O filtro tem três sentidos: dona ou onde está
  (padrão), só a dona, só onde está. Na tramitação pela data de entrada, a
  unidade é onde o processo DEU ENTRADA (abertura na dona ou recebimento);
  envio não recebido e recusa não contam — a unidade nunca esteve com ele.

O fuso é fixo (`America/Fortaleza`) porque todos os municípios atendidos hoje
estão no Ceará e o tenant não guarda fuso. Município em outro fuso exige essa
configuração antes — está registrado na documentação da sprint.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Integer, and_, case, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import (
    Assunto,
    Encaminhamento,
    Movimentacao,
    Processo,
    Servico,
    TipoProcesso,
    UnidadeTrabalho,
)
from ..schemas.relatorio import ModoUnidade, RelatorioFiltro
from ..schemas.relatorio_assinaturas import AssinaturasFiltro

# Os dois filtros têm os campos do recorte comum (unidade, assunto, tipo,
# período, data base); só a lista de datas base muda.
FiltroComum = RelatorioFiltro | AssinaturasFiltro
from .processos import condicao_arquivado, condicao_em_transito

FUSO_RELATORIO = ZoneInfo("America/Fortaleza")

ROTULO_DATA_BASE: dict[str, str] = {
    "abertura": "data de abertura",
    "arquivamento": "data de arquivamento",
    "chegada": "data de chegada na unidade",
    "pedido": "data do pedido de assinatura",
    "conclusao": "data de conclusão da assinatura",
}

ROTULO_MODO_UNIDADE: dict[str, str] = {
    "envolvida": "dona do processo ou onde ele está agora",
    "dona": "dona do processo",
    "atual": "onde o processo está agora",
}
ROTULO_PRAZO: dict[str, str] = {
    "sem_prazo": "sem prazo de serviço",
    "dentro_do_prazo": "em andamento, dentro do prazo",
    "vencendo": "em andamento, vencendo",
    "atrasado": "em andamento, prazo vencido",
    "concluido_no_prazo": "arquivado dentro do prazo",
    "concluido_atrasado": "arquivado com atraso",
}
ROTULO_SITUACAO: dict[str, str] = {
    "em_andamento": "Em andamento",
    "em_transito": "Em trânsito",
    "arquivado": "Arquivado",
}


def _utc_ingenuo(dia: date) -> datetime:
    """Meia-noite local de `dia`, em UTC sem `tzinfo` — o formato da coluna."""
    return (
        datetime.combine(dia, time.min, tzinfo=FUSO_RELATORIO)
        .astimezone(UTC)
        .replace(tzinfo=None)
    )


def intervalo_utc(de: date | None, ate: date | None) -> tuple[datetime | None, datetime | None]:
    """Dias locais `[de, ate]` (inclusive) como `[início, fim)` em UTC.

    Fim exclusivo (meia-noite do dia seguinte) em vez de `23:59:59`: não perde
    o último segundo nem depende da precisão da coluna.
    """
    return (
        _utc_ingenuo(de) if de else None,
        _utc_ingenuo(ate + timedelta(days=1)) if ate else None,
    )


def no_intervalo(coluna, de: date | None, ate: date | None):
    """Condições de `coluna` dentro dos dias locais `[de, ate]`.

    "Pela data X" exige que X exista, COM ou SEM período. Antes, sem período
    não sobrava condição nenhuma: "arquivados pela data de arquivamento" sem
    período contava todos os processos, abertos inclusive (a Saída dizia 20
    com 1 arquivado), e "concluídas pela data de conclusão" contava pendentes.
    """
    inicio, fim = intervalo_utc(de, ate)
    conds = [coluna.is_not(None)]
    if inicio is not None:
        conds.append(coluna >= inicio)
    if fim is not None:
        conds.append(coluna < fim)
    return conds


def hora_local(dt: datetime | None) -> datetime | None:
    """UTC sem fuso (como vem do banco) → hora local de Brasília, sem fuso.

    Relatório exportado (CSV/PDF) é lido fora do navegador, que não converte
    nada: tem de sair já na hora de quem vai ler.
    """
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC).astimezone(FUSO_RELATORIO).replace(tzinfo=None)


def data_arquivamento(tenant_id: int):
    """Subconsulta escalar: quando o processo foi arquivado (ou NULL).

    Arquivar não tem volta (`acoes_processo.arquivar`), então há no máximo uma
    movimentação de arquivamento viva; `min` só blinda contra lixo legado.
    """
    return (
        select(func.min(Movimentacao.data_hora_movimentacao))
        .where(
            Movimentacao.id_processo == Processo.id,
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.id_arquivamento.is_not(None),
            Movimentacao.excluido.is_(False),
        )
        .scalar_subquery()
    )


def ultima_movimentacao(tenant_id: int):
    """Subconsulta escalar: a movimentação mais recente do processo, ou a
    abertura se não houver nenhuma. Envio, recebimento, despacho, assinatura —
    qualquer ato registrado conta."""
    return func.coalesce(
        select(func.max(Movimentacao.data_hora_movimentacao))
        .where(
            Movimentacao.id_processo == Processo.id,
            Movimentacao.tenant_id == tenant_id,
            Movimentacao.excluido.is_(False),
        )
        .scalar_subquery(),
        Processo.data_hora_abertura,
    )


def condicao_parado(tenant_id: int, dias: int, agora_utc: datetime):
    """Não arquivado e sem movimentação há `dias` dias ou mais (decisão de
    2026-11-11: conta da última movimentação de qualquer tipo)."""
    return and_(
        ~condicao_arquivado(tenant_id),
        ultima_movimentacao(tenant_id) <= agora_utc - timedelta(days=dias),
    )


def situacao_prazo(tenant_id: int, agora_utc: datetime):
    """Status do prazo do SERVIÇO em SQL — espelho de `prazos.calcular_prazo`.

    Existe para a lista poder filtrar e contar no banco ("ver lista" dos
    vencidos). Duas cópias de uma regra divergem; por isso
    `test_relatorios_protocolo_medidas.py::test_prazo_em_sql_igual_a_calcular_prazo`
    compara as duas, caso a caso e nos limites de cada faixa. Mudou
    `calcular_prazo`? Mude aqui — o teste reprova se esquecer.

    - sem snapshot → `sem_prazo`;
    - arquivado → `concluido_no_prazo` se arquivou até abertura + N dias
      corridos, senão `concluido_atrasado`;
    - aberto → `atrasado` se já passou; `vencendo` se faltam menos de
      `limiar + 1` dias (o `.days` do Python arredonda para baixo), com
      limiar = 20% do prazo, mínimo 1; senão `dentro_do_prazo`.
    """
    dias = Processo.prazo_servico_dias_snapshot
    previsto = Processo.data_hora_abertura + func.make_interval(0, 0, 0, dias)
    # `ceil` devolve double; `make_interval` só aceita inteiro em dias.
    limiar = func.greatest(1, cast(func.ceil(dias * 0.2), Integer))
    arquivado_em = data_arquivamento(tenant_id)
    return case(
        (dias.is_(None), "sem_prazo"),
        (arquivado_em.is_not(None),
         case((arquivado_em <= previsto, "concluido_no_prazo"), else_="concluido_atrasado")),
        (literal(agora_utc) > previsto, "atrasado"),
        (previsto - literal(agora_utc) < func.make_interval(0, 0, 0, limiar + 1), "vencendo"),
        else_="dentro_do_prazo",
    )


def semana_local(coluna):
    """Segunda-feira (dia local) da semana de `coluna`, que guarda UTC."""
    local = func.timezone(FUSO_RELATORIO.key, func.timezone("UTC", coluna))
    return func.date(func.date_trunc("week", local))


def situacao(tenant_id: int):
    """Expressão SQL com a situação do processo. Arquivado vence trânsito:
    processo arquivado com encaminhamento esquecido já teve a decisão."""
    return case(
        (condicao_arquivado(tenant_id), "arquivado"),
        (condicao_em_transito(tenant_id), "em_transito"),
        else_="em_andamento",
    )


def condicao_unidade(id_unidade: int, modo: ModoUnidade, tenant_id: int):
    """Processo ligado à unidade, no sentido escolhido."""
    dona = Processo.id_unidade_proprietaria == id_unidade
    atual = Processo.id_local_atual == id_unidade
    if modo == "dona":
        return dona
    if modo == "atual":
        return atual
    # "Por onde passou" saiu do filtro em 2026-11-12 (decisão do usuário). O
    # sentido continua na tramitação pela data de entrada, que conta as
    # entradas na unidade (`relatorios_tramitacao._filter_processos`).
    return or_(dona, atual)


def aplicar_filtros_processo(
    stmt,
    f: FiltroComum,
    *,
    tenant_id: int,
    niveis_permitidos: list[str] | None,
    coluna_data,
):
    """Recorte comum sobre `Processo` (a consulta precisa ter `Assunto` no
    join quando houver filtro de tipo).

    - prefeitura, excluído e rascunho (relatório é documento numerado; rascunho
      é de quem o criou, SI-16);
    - sigilo de quem consulta (`None` = super-usuário);
    - unidade no modo escolhido, assunto, tipo e serviço;
    - período sobre `coluna_data`, em dias locais.
    """
    stmt = stmt.where(
        Processo.tenant_id == tenant_id,
        Processo.excluido.is_(False),
        Processo.situacao != "rascunho",
    )
    if niveis_permitidos is not None:
        stmt = stmt.where(Processo.nivel_sigilo.in_(niveis_permitidos))
    if f.id_unidade:
        stmt = stmt.where(condicao_unidade(f.id_unidade, f.modo_unidade, tenant_id))
    if f.id_assunto:
        stmt = stmt.where(Processo.id_assunto == f.id_assunto)
    if f.id_tipo_processo:
        stmt = stmt.where(Assunto.id_tipo_processo == f.id_tipo_processo)
    if f.id_servico:
        stmt = stmt.where(Processo.id_servico == f.id_servico)
    return stmt.where(*no_intervalo(coluna_data, f.desde, f.ate))


async def descrever_filtros(
    db: AsyncSession, f: FiltroComum, *, tenant_id: int, por_secao: bool = False,
    rotulo_data: str | None = None,
) -> list[str]:
    """O recorte em frases curtas, para a tela, o CSV e o PDF dizerem o mesmo.

    Nomes buscados com o `tenant_id`: id de outra prefeitura vira "não
    encontrada", nunca o nome dela.
    """

    async def _nome(coluna, modelo, id_):
        return (
            await db.execute(select(coluna).where(modelo.id == id_, modelo.tenant_id == tenant_id))
        ).scalar_one_or_none()

    linhas: list[str] = []
    if f.desde or f.ate:
        de = f.desde.strftime("%d/%m/%Y") if f.desde else "o início"
        ate = f.ate.strftime("%d/%m/%Y") if f.ate else "hoje"
        periodo = f"Período: {de} a {ate}"
    else:
        periodo = "Período: todo o histórico"
    if por_secao:
        # Página gerencial: cada seção conta pela sua data (ver
        # `schemas/relatorio_gerencial.py`); dizer uma só seria falso.
        linhas.append(
            f"{periodo} — cada seção diz por qual data conta; Andamento é a situação de hoje"
        )
    else:
        linhas.append(f"{periodo}, pela {rotulo_data or ROTULO_DATA_BASE[f.data_base]}")
    if f.id_unidade:
        nome = await _nome(UnidadeTrabalho.unidade_trabalho, UnidadeTrabalho, f.id_unidade)
        sentido = (
            "onde o processo deu entrada: abertura ou recebimento"
            if f.data_base == "chegada"
            else ROTULO_MODO_UNIDADE[f.modo_unidade]
        )
        linhas.append(f"Unidade: {nome or 'não encontrada'} ({sentido})")
    if f.id_tipo_processo:
        nome = await _nome(TipoProcesso.tipo_processo, TipoProcesso, f.id_tipo_processo)
        linhas.append(f"Tipo de processo: {nome or 'não encontrado'}")
    if f.id_assunto:
        nome = await _nome(Assunto.assunto, Assunto, f.id_assunto)
        linhas.append(f"Assunto: {nome or 'não encontrado'}")
    if f.id_servico:
        nome = await _nome(Servico.nome, Servico, f.id_servico)
        linhas.append(f"Serviço: {nome or 'não encontrado'}")
    if getattr(f, "sigilo", None):
        linhas.append(
            "Sigilo: só ostensivos (públicos)" if f.sigilo == "ostensivo"
            else "Sigilo: só sigilosos (qualquer nível acima de ostensivo)"
        )
    if getattr(f, "origem", None):
        linhas.append("Origem: só externos" if f.origem == "externa" else "Origem: só internos")
    if getattr(f, "com_atraso", False):
        linhas.append("Só processos com atraso na tramitação (prazo do envio)")
    if getattr(f, "situacao", None):
        linhas.append(f"Situação hoje: {ROTULO_SITUACAO[f.situacao]}")
    if getattr(f, "prazo", None):
        linhas.append(f"Prazo do serviço: {ROTULO_PRAZO[f.prazo]}")
    if getattr(f, "parado_ha_dias", None):
        linhas.append(
            f"Parados: sem nenhuma movimentação há {f.parado_ha_dias} dias ou mais (não arquivados)"
        )
    linhas.append("Horários em hora de Brasília. Só entram processos que a sua credencial de sigilo alcança.")
    return linhas

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
  de produto de 2026-11-10). "Passou pela unidade" conta a dona e quem RECEBEU
  o processo; envio não recebido e recusa não contam — a unidade nunca esteve
  com ele.

O fuso é fixo (`America/Fortaleza`) porque todos os municípios atendidos hoje
estão no Ceará e o tenant não guarda fuso. Município em outro fuso exige essa
configuração antes — está registrado na documentação da sprint.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Assunto, Encaminhamento, Movimentacao, Processo, TipoProcesso, UnidadeTrabalho
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
    "passou": "por onde o processo passou",
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
    """Condições de `coluna` dentro dos dias locais `[de, ate]`."""
    inicio, fim = intervalo_utc(de, ate)
    conds = []
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
    if modo == "passou":
        recebeu = (
            select(Encaminhamento.id)
            .where(
                Encaminhamento.id_processo == Processo.id,
                Encaminhamento.tenant_id == tenant_id,
                Encaminhamento.id_unidade_destino == id_unidade,
                Encaminhamento.recebido.is_(True),
                Encaminhamento.excluido.is_(False),
            )
            .exists()
        )
        return or_(dona, recebeu)
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
    - unidade no modo escolhido, assunto e tipo;
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
    return stmt.where(*no_intervalo(coluna_data, f.desde, f.ate))


async def descrever_filtros(db: AsyncSession, f: FiltroComum, *, tenant_id: int) -> list[str]:
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
        linhas.append(f"Período: {de} a {ate}, pela {ROTULO_DATA_BASE[f.data_base]}")
    else:
        linhas.append(f"Período: todo o histórico (contado pela {ROTULO_DATA_BASE[f.data_base]})")
    if f.id_unidade:
        nome = await _nome(UnidadeTrabalho.unidade_trabalho, UnidadeTrabalho, f.id_unidade)
        linhas.append(
            f"Unidade: {nome or 'não encontrada'} ({ROTULO_MODO_UNIDADE[f.modo_unidade]})"
        )
    if f.id_tipo_processo:
        nome = await _nome(TipoProcesso.tipo_processo, TipoProcesso, f.id_tipo_processo)
        linhas.append(f"Tipo de processo: {nome or 'não encontrado'}")
    if f.id_assunto:
        nome = await _nome(Assunto.assunto, Assunto, f.id_assunto)
        linhas.append(f"Assunto: {nome or 'não encontrado'}")
    linhas.append("Horários em hora de Brasília. Só entram processos que a sua credencial de sigilo alcança.")
    return linhas

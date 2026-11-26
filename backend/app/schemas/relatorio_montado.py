"""Relatório montado pela própria pessoa (SI-35).

A pessoa escolhe colunas e filtros, vê o resultado e salva o "seu" relatório.
O que se salva é só a DEFINIÇÃO (este schema), nunca os dados: cada vez que o
relatório abre, a consulta roda de novo com as permissões e o sigilo de quem
abre, naquele momento.

Duas travas moram aqui, no schema, e não na tela:

- **Catálogo fechado.** Coluna, agrupamento e ordem são `Literal`; o backend
  não aceita nome de campo vindo de fora. `extra="forbid"` recusa chave que
  não existe — um `"cpf"` enviado à mão é 422, não coluna nova.
- **Sem dado pessoal além do nome.** CPF/CNPJ, telefones e e-mail do
  manifestante ficaram fora por decisão do PO (2026-11-12), mesmo sendo
  visíveis na tela do processo. Observação, corpo e despachos (texto livre)
  também. `test_relatorio_montado.py` trava o catálogo.

Uma linha por processo. Tramitação e assinaturas entram como colunas e filtros
resumidos do processo — não como fonte própria.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .relatorio import (
    FiltroOrigem,
    FiltroSigilo,
    ModoUnidade,
    RelatorioBreakdownItem,
    Situacao,
    StatusPrazoRelatorio,
)

ColunaMontado = Literal[
    # Processo
    "nup",
    "aberto_em",
    "arquivado_em",
    "situacao",
    "tipo",
    "assunto",
    "servico",
    "unidade_dona",
    "local_atual",
    "responsavel",
    "manifestante",
    "sigilo",
    "origem",
    "canal",
    # Andamento e prazo
    "ultima_movimentacao",
    "dias_parado",
    "prazo_situacao",
    "prazo_previsto",
    # Documentação
    "doc_situacao",
    "doc_obrigatorios",
    "complementacao",
    # Tramitação (resumo do processo)
    "tram_envios",
    "tram_unidades",
    "tram_atrasos",
    "tram_ultimo_envio",
    "tram_unidade_mais_tempo",
    # Assinaturas (resumo do processo)
    "ass_pedidas",
    "ass_concluidas",
    "ass_pendentes",
    "ass_ultima_conclusao",
]

OrdemMontado = Literal[
    "numero", "aberto_em", "arquivado_em", "ultima_movimentacao",
    "assunto", "servico", "unidade_dona", "local_atual",
]
AgruparPor = Literal["situacao", "tipo", "unidade_dona", "local_atual", "assunto", "servico"]
TipoPeriodo = Literal["sem", "fixo", "ultimos_dias", "mes_atual", "mes_anterior", "ano_atual"]
StatusDocFiltro = Literal["sem_documentos_exigidos", "pendente", "parcial", "completo"]
TipoValor = Literal["texto", "numero", "data", "data_hora"]

MAX_COLUNAS = 30


class _Fechado(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PeriodoMontado(_Fechado):
    """Fixo (de/até) ou relativo ao dia em que o relatório ABRE — "últimos 30
    dias" salvo em outubro e aberto em dezembro mostra dezembro."""

    tipo: TipoPeriodo = "sem"
    desde: date | None = None
    ate: date | None = None
    dias: int | None = Field(default=None, ge=1, le=3650)

    @model_validator(mode="after")
    def _coerente(self) -> "PeriodoMontado":
        if self.tipo == "fixo":
            if not (self.desde or self.ate):
                raise ValueError("Período fixo precisa de data inicial ou final.")
            if self.desde and self.ate and self.desde > self.ate:
                raise ValueError("A data inicial do período é posterior à final.")
        if self.tipo == "ultimos_dias" and not self.dias:
            raise ValueError("Informe quantos dias.")
        return self


class FiltrosMontado(_Fechado):
    # Recorte comum, o mesmo das outras telas de relatório.
    id_unidade: int | None = None
    modo_unidade: ModoUnidade = "envolvida"
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    id_servico: int | None = None
    # Por qual data o período conta.
    data_base: Literal["abertura", "arquivamento"] = "abertura"
    # Os da lista de processos.
    situacao: Situacao | None = None
    parado_ha_dias: int | None = Field(default=None, ge=1, le=3650)
    prazo: StatusPrazoRelatorio | None = None
    sigilo: FiltroSigilo | None = None
    origem: FiltroOrigem | None = None
    # Documentação, tramitação e assinaturas — resumidos por processo.
    documentacao: StatusDocFiltro | None = None
    complementacao_aberta: bool = False
    com_atraso: bool = False
    assinatura_pendente: bool = False


class DefinicaoMontado(_Fechado):
    versao: Literal[1] = 1
    # O número do processo sempre vem, na frente: sem ele a linha não diz de
    # quem é. Não entra na lista.
    colunas: list[ColunaMontado] = Field(min_length=1, max_length=MAX_COLUNAS)
    filtros: FiltrosMontado = Field(default_factory=FiltrosMontado)
    periodo: PeriodoMontado = Field(default_factory=PeriodoMontado)
    agrupar_por: AgruparPor | None = None
    ordem: OrdemMontado | None = None
    ordem_desc: bool = True

    @field_validator("colunas")
    @classmethod
    def _sem_repetir(cls, v: list[str]) -> list[str]:
        vistos: list[str] = []
        for c in v:
            if c not in vistos:
                vistos.append(c)
        return vistos


class ColunaInfo(BaseModel):
    chave: str
    rotulo: str
    grupo: str
    tipo: TipoValor


class LinhaMontado(BaseModel):
    id: int
    numero_processo: str
    nivel_sigilo: str
    # chave da coluna → valor. Data e hora em ISO, hora de Brasília, sem fuso.
    valores: dict[str, str | int | None]


class TotaisMontado(BaseModel):
    total: int
    em_andamento: int
    em_transito: int
    arquivados: int


class ResultadoMontado(BaseModel):
    definicao: DefinicaoMontado
    colunas: list[ColunaInfo]
    descricao_filtros: list[str]
    # O período que valeu nesta execução (o relativo, já resolvido).
    desde: date | None
    ate: date | None
    totais: TotaisMontado
    rotulo_agrupamento: str | None = None
    agrupamento: list[RelatorioBreakdownItem] | None = None
    linhas: list[LinhaMontado]
    cortado: bool
    # Partes de uma definição salva que não valem mais (coluna que saiu do
    # catálogo, por exemplo) — ditas em vez de quebrar o relatório.
    avisos: list[str] = Field(default_factory=list)


class CatalogoMontado(BaseModel):
    colunas: list[ColunaInfo]
    colunas_padrao: list[str]
    ordens: dict[str, str]
    agrupamentos: dict[str, str]
    max_colunas: int


# ---------- Relatórios salvos ----------


class RelatorioSalvoCriar(_Fechado):
    nome: str = Field(min_length=1, max_length=120)
    definicao: DefinicaoMontado

    @field_validator("nome")
    @classmethod
    def _apara(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Dê um nome ao relatório.")
        return v


class RelatorioSalvoAtualizar(_Fechado):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    definicao: DefinicaoMontado | None = None

    @field_validator("nome")
    @classmethod
    def _apara(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = " ".join(v.split())
        if not v:
            raise ValueError("Dê um nome ao relatório.")
        return v


class RelatorioSalvoResumo(BaseModel):
    id: int
    nome: str
    criado_em: datetime
    atualizado_em: datetime


class RelatorioSalvoOut(RelatorioSalvoResumo):
    definicao: DefinicaoMontado
    avisos: list[str] = Field(default_factory=list)

"""Relatório de documentação (SI-34) — uma linha por processo.

Duas coisas, ambas sobre o processo:

- **Documentos exigidos pelo serviço**: a situação de hoje (pendente, parcial,
  completo), com a mesma regra da tela do processo
  (`checklist_documentos._calcular_status`).
- **Complementação documental**: pedido do servidor ao cidadão para mandar
  documentos (`complementacao_documental`).

A mensagem do pedido e o motivo de cancelamento NÃO entram aqui: são texto
livre, podem trazer dado pessoal, e o relatório não precisa deles.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .checklist_documentos import StatusDocumental
from .relatorio import RelatorioFiltro

# Cada visão é a lista de um número do grupo Documentação da página gerencial.
VisaoDocumentacao = Literal[
    "documentos",        # abertos no período cujo serviço exige documentos
    "doc_pendente",      # ... e nenhum obrigatório enviado
    "doc_parcial",       # ... e parte dos obrigatórios enviada
    "doc_completo",      # ... e todos os obrigatórios enviados
    "compl_pedida",      # com pedido de complementação feito no período
    "compl_aberta",      # com pedido aguardando o cidadão hoje (sem período)
    "compl_respondida",  # com pedido respondido pelo cidadão no período
]
StatusComplementacao = Literal["aberta", "respondida", "cancelada"]


class DocumentacaoProcessoRow(BaseModel):
    id: int
    numero_processo: str
    data_hora_abertura: datetime  # hora local
    servico: str | None
    status_documental: StatusDocumental
    obrigatorios_total: int
    obrigatorios_enviados: int
    # O pedido de complementação mais recente do processo, se houver.
    complementacao_status: StatusComplementacao | None
    complementacao_pedida_em: datetime | None  # hora local
    complementacao_respondida_em: datetime | None  # hora local
    local_atual: str | None
    nivel_sigilo: str


class DocumentacaoTotais(BaseModel):
    total: int
    pendentes: int
    parciais: int
    completos: int
    aguardando_cidadao: int


class RelatorioDocumentacaoResposta(BaseModel):
    filtros_aplicados: RelatorioFiltro
    visao: VisaoDocumentacao
    descricao_filtros: list[str]
    totais: DocumentacaoTotais
    processos: list[DocumentacaoProcessoRow]
    cortado: bool = False

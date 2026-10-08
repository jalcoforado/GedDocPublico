"""Schemas do módulo Contratos (G1).

Spec: docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md

Campos server-side — `situacao`, `exercicio`, `sequencial`,
`id_usuario_registro` e todos os derivados — NÃO entram em schema de entrada.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .pagamentos import CategoriaLit, TipoPessoa

SituacaoContratoLit = Literal["RASCUNHO", "VIGENTE", "ENCERRADO", "RESCINDIDO"]
SituacaoAditivoLit = Literal["RASCUNHO", "VIGENTE", "ANULADO"]
NaturezaDuracaoLit = Literal["ESCOPO", "CONTINUO"]
# Campo 6 da tabela 511 do SIM (Manual do SIM 2026, TCE-CE).
TipoObjetoLit = Literal[
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
]
# Campo 7 da tabela 511 do SIM, sem o "OR" (contrato original).
TipoAditivoLit = Literal["AA", "AR", "AP", "PA", "PR", "RE"]
TipoApostilaLit = Literal["REAJUSTE", "REPACTUACAO", "RAZAO_SOCIAL", "DOTACAO", "OUTRO"]

TIPOS_OBJETO: dict[str, str] = {
    "A": "Assessoria / Consultoria",
    "B": "Publicidade / Propaganda",
    "C": "Coleta de Resíduos Sólidos",
    "D": "Material Didático",
    "E": "Obra / Serviço de Engenharia",
    "F": "Festividade / Evento / Comemoração / Show",
    "G": "Medicamentos / Material Hospitalar",
    "H": "Locação de Mão-de-Obra / Terceirização",
    "I": "Locação de Imóveis",
    "J": "Transporte Escolar",
    "K": "Combustível / Lubrificante / Manutenção Veicular",
    "L": "Locação de Veículos",
    "M": "Merenda Escolar",
    "N": "Serviço / Sistema / Equipamento de TI",
    "O": "Outros tipos de objeto",
    "P": "Material de Consumo",
    "Q": "Gênero Alimentício",
    "R": "Bem Permanente",
}

TIPOS_ADITIVO: dict[str, str] = {
    "AA": "Acréscimo",
    "AR": "Redução",
    "AP": "Prazo",
    "PA": "Prazo e acréscimo",
    "PR": "Prazo e redução",
    "RE": "Renovação",
}


# ---------- contrato ----------
class ContratoCreate(BaseModel):
    # 50 na tabela (herança do cadastro de pagamentos); os 15 do SIM são
    # cobrados na assinatura — rascunho pode ter número provisório.
    numero: str = Field(min_length=1, max_length=50)
    id_fornecedor: int
    id_unidade: int
    objeto: str = Field(min_length=1, max_length=3000)
    vigencia_inicio: date
    vigencia_fim: date
    valor_total: Decimal = Field(gt=0)
    categoria: CategoriaLit
    data_celebracao: date | None = None
    tipo_objeto: TipoObjetoLit | None = None
    natureza_duracao: NaturezaDuracaoLit | None = None
    reforma: bool = False
    id_processo: int | None = None
    processo_numero: str | None = Field(default=None, max_length=15)
    processo_data_autuacao: date | None = None
    pncp_id: str | None = Field(default=None, max_length=25)
    pncp_publicado_em: date | None = None


class ContratoUpdate(BaseModel):
    numero: str | None = Field(default=None, min_length=1, max_length=50)
    id_fornecedor: int | None = None
    id_unidade: int | None = None
    objeto: str | None = Field(default=None, min_length=1, max_length=3000)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    categoria: CategoriaLit | None = None
    data_celebracao: date | None = None
    tipo_objeto: TipoObjetoLit | None = None
    natureza_duracao: NaturezaDuracaoLit | None = None
    reforma: bool | None = None
    id_processo: int | None = None
    processo_numero: str | None = Field(default=None, max_length=15)
    processo_data_autuacao: date | None = None
    pncp_id: str | None = Field(default=None, max_length=25)
    pncp_publicado_em: date | None = None


class ContratoEncerrar(BaseModel):
    data_encerramento: date


class ContratoRescindir(BaseModel):
    data_encerramento: date
    motivo: str = Field(min_length=5, max_length=500)


class ContratoCalculoOut(BaseModel):
    """Os derivados do §2.4 do spec. Nenhum destes é coluna."""
    valor_inicial: Decimal
    valor_inicial_atualizado: Decimal
    acrescimos: Decimal
    supressoes: Decimal
    renovacoes: Decimal
    valor_atualizado: Decimal
    vigencia_fim_atual: date
    percentual_acrescimo: Decimal
    percentual_supressao: Decimal
    limite_acrescimo: Decimal
    limite_supressao: Decimal
    acima_do_limite: bool
    dias_para_vencer: int | None


class ContratoResumoOut(BaseModel):
    """Linha da listagem."""
    id: int
    numero: str
    exercicio: int
    situacao: SituacaoContratoLit
    id_fornecedor: int
    fornecedor_nome: str | None
    id_unidade: int
    unidade_nome: str | None
    objeto: str
    tipo_objeto: TipoObjetoLit | None
    valor_inicial: Decimal
    valor_atualizado: Decimal
    vigencia_inicio: date
    vigencia_fim_atual: date
    percentual_acrescimo: Decimal
    acima_do_limite: bool
    dias_para_vencer: int | None


class AditivoCreate(BaseModel):
    numero: str = Field(min_length=1, max_length=15)
    tipo: TipoAditivoLit
    data_assinatura: date
    valor: Decimal = Field(default=Decimal("0"), ge=0)
    nova_vigencia_fim: date | None = None
    justificativa: str | None = Field(default=None, max_length=1000)
    pncp_id: str | None = Field(default=None, max_length=25)
    pncp_publicado_em: date | None = None


class AditivoUpdate(BaseModel):
    numero: str | None = Field(default=None, min_length=1, max_length=15)
    tipo: TipoAditivoLit | None = None
    data_assinatura: date | None = None
    valor: Decimal | None = Field(default=None, ge=0)
    nova_vigencia_fim: date | None = None
    justificativa: str | None = Field(default=None, max_length=1000)
    pncp_id: str | None = Field(default=None, max_length=25)
    pncp_publicado_em: date | None = None


class AditivoAnular(BaseModel):
    motivo: str = Field(min_length=5, max_length=500)


class AditivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_contrato: int
    sequencial: int
    numero: str
    exercicio: int
    tipo: TipoAditivoLit
    data_assinatura: date
    valor: Decimal
    nova_vigencia_fim: date | None
    justificativa: str | None
    situacao: SituacaoAditivoLit
    motivo_anulacao: str | None
    pncp_id: str | None
    pncp_publicado_em: date | None
    criado_em: datetime
    atualizado_em: datetime | None


class ApostilaCreate(BaseModel):
    tipo: TipoApostilaLit
    data: date
    valor_delta: Decimal | None = None
    indice: str | None = Field(default=None, max_length=60)
    descricao: str = Field(min_length=3, max_length=1000)


class ApostilaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    id_contrato: int
    sequencial: int
    tipo: TipoApostilaLit
    data: date
    valor_delta: Decimal | None
    indice: str | None
    descricao: str
    criado_em: datetime


class ProcessoVinculadoOut(BaseModel):
    """Só o que identifica o processo. Vem `None` no contrato quando o usuário
    não tem credencial de sigilo para ele — o contrato aparece, o vínculo não."""
    id: int
    numero_processo: str | None


class ContratoOut(BaseModel):
    """Detalhe: contrato + derivados + atos."""
    id: int
    numero: str
    exercicio: int
    situacao: SituacaoContratoLit
    id_fornecedor: int
    fornecedor_nome: str | None
    id_unidade: int
    unidade_nome: str | None
    objeto: str
    vigencia_inicio: date
    vigencia_fim: date
    valor_total: Decimal
    categoria: CategoriaLit | None
    data_celebracao: date | None
    tipo_objeto: TipoObjetoLit | None
    natureza_duracao: NaturezaDuracaoLit | None
    reforma: bool
    processo: ProcessoVinculadoOut | None
    processo_numero: str | None
    processo_data_autuacao: date | None
    pncp_id: str | None
    pncp_publicado_em: date | None
    data_encerramento: date | None
    motivo_rescisao: str | None
    criado_em: datetime
    atualizado_em: datetime | None
    calculo: ContratoCalculoOut
    aditivos: list[AditivoOut]
    apostilas: list[ApostilaOut]


class ContratosPainelOut(BaseModel):
    """Contagens do painel (`GET /contratos/resumo`)."""
    vigentes: int
    rascunhos: int
    vencidos: int
    vencendo_30: int
    vencendo_60: int
    vencendo_90: int
    vencendo_120: int
    acima_do_limite: int
    valor_vigente_total: Decimal


class FornecedorContratoCreate(BaseModel):
    """Fornecedor criado a partir do módulo de contratos: só identificação.

    Dados bancários e situação cadastral são do módulo de pagamentos e ficam
    de fora de propósito (decisão Q2 do spec) — quem tem só a transação
    `contrato` não lê nem grava conta bancária de fornecedor."""
    tipo_pessoa: TipoPessoa
    cnpj_cpf: str = Field(min_length=11, max_length=18)
    nome: str = Field(min_length=1, max_length=200)


class FornecedorContratoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tipo_pessoa: str
    cnpj_cpf: str
    nome: str
    situacao_cadastral: str


class TipoOpcaoOut(BaseModel):
    codigo: str
    rotulo: str


class ContratoCatalogosOut(BaseModel):
    """Opções fixas dos formulários — vêm do backend para a tela não manter
    uma segunda cópia da tabela do SIM."""
    tipos_objeto: list[TipoOpcaoOut]
    tipos_aditivo: list[TipoOpcaoOut]

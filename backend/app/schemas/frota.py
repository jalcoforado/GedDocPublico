"""Schemas do módulo de Frota — Veículo (fundação).

`placa` é normalizada (upper, sem espaços/hífen) e validada nos formatos
brasileiro antigo (ABC1234) e Mercosul (ABC1D23). `VeiculoUpdate` é whitelist:
`tenant_id`/`id`/`excluido` nunca são aceitos no corpo.
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Situacao = Literal["disponivel", "em_uso", "manutencao", "inativo", "baixado"]
FormaPosse = Literal["proprio", "locado", "cedido", "convenio"]

# Placa BR antiga (ABC1234) ou Mercosul (ABC1D23), já em maiúsculas.
PLACA_PATTERN = r"^[A-Z]{3}[0-9][0-9A-Z][0-9]{2}$"


def _normalizar_placa(v: str) -> str:
    return v.replace("-", "").replace(" ", "").strip().upper()


class VeiculoBase(BaseModel):
    renavam: str | None = Field(default=None, max_length=20)
    chassi: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=80)
    ano_fabricacao: int | None = Field(default=None, ge=1900, le=2100)
    ano_modelo: int | None = Field(default=None, ge=1900, le=2100)
    cor: str | None = Field(default=None, max_length=30)
    tipo_veiculo: str | None = Field(default=None, max_length=40)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    situacao: Situacao = "disponivel"
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int = Field(default=0, ge=0)
    data_aquisicao: date | None = None
    forma_posse: FormaPosse = "proprio"
    observacoes: str | None = None


class VeiculoCreate(VeiculoBase):
    placa: str

    # mode="before": normaliza (upper, sem espaço/hífen) ANTES das constraints,
    # senão uma placa digitada com hífen/espaço estouraria max_length.
    @field_validator("placa", mode="before")
    @classmethod
    def _placa(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = _normalizar_placa(v)
        import re

        if not re.match(PLACA_PATTERN, v):
            raise ValueError(
                "Placa inválida. Use o formato ABC1234 ou ABC1D23 (Mercosul)."
            )
        return v


class VeiculoUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido` nunca aceitos."""

    placa: str | None = None
    renavam: str | None = Field(default=None, max_length=20)
    chassi: str | None = Field(default=None, max_length=30)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=80)
    ano_fabricacao: int | None = Field(default=None, ge=1900, le=2100)
    ano_modelo: int | None = Field(default=None, ge=1900, le=2100)
    cor: str | None = Field(default=None, max_length=30)
    tipo_veiculo: str | None = Field(default=None, max_length=40)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    situacao: Situacao | None = None
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int | None = Field(default=None, ge=0)
    data_aquisicao: date | None = None
    forma_posse: FormaPosse | None = None
    observacoes: str | None = None

    @field_validator("placa", mode="before")
    @classmethod
    def _placa(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        v = _normalizar_placa(v)
        import re

        if not re.match(PLACA_PATTERN, v):
            raise ValueError(
                "Placa inválida. Use o formato ABC1234 ou ABC1D23 (Mercosul)."
            )
        return v


class VeiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    placa: str
    renavam: str | None = None
    chassi: str | None = None
    marca: str | None = None
    modelo: str | None = None
    ano_fabricacao: int | None = None
    ano_modelo: int | None = None
    cor: str | None = None
    tipo_veiculo: str | None = None
    tipo_combustivel: str | None = None
    situacao: str
    id_unidade_responsavel: int | None = None
    quilometragem_atual: int
    data_aquisicao: date | None = None
    forma_posse: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# --- Motorista / Condutor (PR Frota-2) --------------------------------------
CnhCategoria = Literal["A", "B", "AB", "C", "D", "E", "AC", "AD", "AE"]
MotoristaSituacao = Literal["ativo", "afastado", "inativo"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _so_digitos(v: str) -> str:
    import re

    return re.sub(r"\D", "", v)


class MotoristaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    cpf: str = Field(min_length=11, max_length=14)
    matricula: str | None = Field(default=None, max_length=40)
    cnh_numero: str = Field(min_length=9, max_length=14)
    cnh_categoria: CnhCategoria
    cnh_validade: date
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: MotoristaSituacao = "ativo"
    observacoes: str | None = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str) -> str:
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("CPF inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str) -> str:
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("Número da CNH inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v == "":
            return None
        import re

        if not re.match(EMAIL_PATTERN, v):
            raise ValueError("E-mail inválido.")
        return v


class MotoristaUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`excluido` nunca aceitos."""

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    cpf: str | None = Field(default=None, min_length=11, max_length=14)
    matricula: str | None = Field(default=None, max_length=40)
    cnh_numero: str | None = Field(default=None, min_length=9, max_length=14)
    cnh_categoria: CnhCategoria | None = None
    cnh_validade: date | None = None
    telefone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: MotoristaSituacao | None = None
    observacoes: str | None = None

    @field_validator("cpf")
    @classmethod
    def _cpf(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("CPF inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("cnh_numero")
    @classmethod
    def _cnh(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = _so_digitos(v)
        if len(v) != 11:
            raise ValueError("Número da CNH inválido. Deve conter 11 dígitos.")
        return v

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if v == "":
            return None
        import re

        if not re.match(EMAIL_PATTERN, v):
            raise ValueError("E-mail inválido.")
        return v


class MotoristaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    cpf: str
    matricula: str | None = None
    cnh_numero: str
    cnh_categoria: str
    cnh_validade: date
    telefone: str | None = None
    email: str | None = None
    id_unidade: int | None = None
    id_usuario: int | None = None
    situacao: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# --- Solicitação de Veículo (PR Frota-3) ------------------------------------
# em_uso/concluida (PR Frota-5) são estados operacionais: aprovada → em_uso
# (saída real) → concluida (retorno real).
SolicitacaoStatus = Literal[
    "solicitada", "aprovada", "rejeitada", "cancelada", "em_uso", "concluida"
]


class SolicitacaoVeiculoCreate(BaseModel):
    """`id_usuario_solicitante` e `status` NÃO entram no payload — são definidos
    server-side (usuário autenticado / 'solicitada')."""

    id_unidade_solicitante: int | None = None
    finalidade: str = Field(min_length=1, max_length=255)
    destino: str = Field(min_length=1, max_length=255)
    data_saida_prevista: datetime
    data_retorno_prevista: datetime
    quantidade_passageiros: int = Field(ge=1)
    necessita_motorista: bool = False
    observacoes: str | None = None

    @model_validator(mode="after")
    def _datas_coerentes(self) -> "SolicitacaoVeiculoCreate":
        if self.data_retorno_prevista < self.data_saida_prevista:
            raise ValueError(
                "data_retorno_prevista deve ser posterior ou igual à data_saida_prevista."
            )
        return self


class SolicitacaoVeiculoUpdate(BaseModel):
    """Whitelist de edição — `status`/`justificativa_rejeicao`/
    `id_usuario_solicitante`/`tenant_id`/`id`/`excluido` nunca aceitos. A coerência
    de datas é revalidada no serviço sobre os valores efetivos (parciais)."""

    id_unidade_solicitante: int | None = None
    finalidade: str | None = Field(default=None, min_length=1, max_length=255)
    destino: str | None = Field(default=None, min_length=1, max_length=255)
    data_saida_prevista: datetime | None = None
    data_retorno_prevista: datetime | None = None
    quantidade_passageiros: int | None = Field(default=None, ge=1)
    necessita_motorista: bool | None = None
    observacoes: str | None = None


class SolicitacaoVeiculoRejeitar(BaseModel):
    justificativa_rejeicao: str = Field(min_length=1, max_length=2000)


class SolicitacaoVeiculoDesignar(BaseModel):
    """Designação de veículo/motorista (PR Frota-4). `id_usuario_designador` e
    `data_designacao` são server-side. A obrigatoriedade do motorista quando
    `necessita_motorista` e os status de veículo/motorista são validados no
    serviço (dependem do registro armazenado)."""

    id_veiculo: int
    id_motorista: int | None = None
    observacoes_designacao: str | None = Field(default=None, max_length=2000)


class SolicitacaoVeiculoRegistrarSaida(BaseModel):
    """Registro de saída real (PR Frota-5). `data_saida_real`/
    `id_usuario_registro_saida` são server-side — nunca no payload. `km_saida`
    é obrigatório (>= 0); a regra `km_saida >= quilometragem_atual` do veículo
    é validada no serviço (depende do registro armazenado)."""

    km_saida: int = Field(ge=0)
    observacoes_saida: str | None = Field(default=None, max_length=2000)


class SolicitacaoVeiculoRegistrarRetorno(BaseModel):
    """Registro de retorno real (PR Frota-5). `data_retorno_real`/
    `id_usuario_registro_retorno` são server-side. `km_retorno` é obrigatório
    (>= 0); a regra `km_retorno >= km_saida` é validada no serviço."""

    km_retorno: int = Field(ge=0)
    observacoes_retorno: str | None = Field(default=None, max_length=2000)


class SolicitacaoVeiculoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_usuario_solicitante: int
    id_unidade_solicitante: int | None = None
    finalidade: str
    destino: str
    data_saida_prevista: datetime
    data_retorno_prevista: datetime
    quantidade_passageiros: int
    necessita_motorista: bool
    observacoes: str | None = None
    status: str
    justificativa_rejeicao: str | None = None
    id_veiculo_designado: int | None = None
    id_motorista_designado: int | None = None
    id_usuario_designador: int | None = None
    data_designacao: datetime | None = None
    observacoes_designacao: str | None = None
    data_saida_real: datetime | None = None
    data_retorno_real: datetime | None = None
    km_saida: int | None = None
    km_retorno: int | None = None
    observacoes_saida: str | None = None
    observacoes_retorno: str | None = None
    id_usuario_registro_saida: int | None = None
    id_usuario_registro_retorno: int | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# --- Documento do Veículo (PR Frota-6) --------------------------------------
# Apenas metadados + alertas de vencimento — SEM upload/anexos.
TipoDocumento = Literal[
    "crlv", "seguro", "licenciamento", "autorizacao", "vistoria", "outro"
]
DocumentoStatus = Literal["ativo", "vencido", "substituido", "cancelado"]


class VeiculoDocumentoBase(BaseModel):
    numero: str | None = Field(default=None, max_length=60)
    orgao_emissor: str | None = Field(default=None, max_length=120)
    data_emissao: date | None = None
    data_vencimento: date
    status: DocumentoStatus = "ativo"
    observacoes: str | None = None

    @model_validator(mode="after")
    def _datas_coerentes(self) -> "VeiculoDocumentoBase":
        if self.data_emissao is not None and self.data_emissao > self.data_vencimento:
            raise ValueError(
                "data_emissao não pode ser posterior à data_vencimento."
            )
        return self


class VeiculoDocumentoCreate(VeiculoDocumentoBase):
    """`id_veiculo` vem da rota (não do payload); `tenant_id`/`id`/`excluido`
    nunca aceitos."""

    tipo_documento: TipoDocumento


class VeiculoDocumentoUpdate(BaseModel):
    """Whitelist de edição — `tenant_id`/`id`/`id_veiculo`/`excluido`/`criado_em`/
    `atualizado_em` nunca aceitos. A coerência de datas é revalidada no serviço
    sobre os valores efetivos (parciais)."""

    tipo_documento: TipoDocumento | None = None
    numero: str | None = Field(default=None, max_length=60)
    orgao_emissor: str | None = Field(default=None, max_length=120)
    data_emissao: date | None = None
    data_vencimento: date | None = None
    status: DocumentoStatus | None = None
    observacoes: str | None = None


class VeiculoDocumentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_veiculo: int
    tipo_documento: str
    numero: str | None = None
    orgao_emissor: str | None = None
    data_emissao: date | None = None
    data_vencimento: date
    status: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


class VeiculoDocumentoAlertas(BaseModel):
    """Documentos vencidos / a vencer dentro de `dias` (tenant-scoped)."""

    dias: int
    vencidos: list[VeiculoDocumentoOut]
    a_vencer: list[VeiculoDocumentoOut]


# --- Manutenção do Veículo (Frota — operacional) ----------------------------
ManutencaoTipo = Literal["preventiva", "corretiva"]
ManutencaoStatus = Literal["aberta", "em_andamento", "concluida", "cancelada"]


class VeiculoManutencaoCreate(BaseModel):
    """`id_veiculo` no corpo (página standalone, validado same-tenant no serviço);
    `status`/`data_conclusao`/`custo_final` são server-side (status inicial
    'aberta'). `data_abertura` opcional (default hoje no serviço).
    `tenant_id`/`id`/`excluido` nunca aceitos."""

    id_veiculo: int
    tipo: ManutencaoTipo
    descricao: str = Field(min_length=1)
    data_abertura: date | None = None
    data_prevista: date | None = None
    km_atual: int | None = Field(default=None, ge=0)
    fornecedor: str | None = Field(default=None, max_length=150)
    custo_estimado: float | None = Field(default=None, ge=0)
    observacoes: str | None = None


class VeiculoManutencaoUpdate(BaseModel):
    """Whitelist de edição de metadados — `status`/`data_abertura`/
    `data_conclusao`/`custo_final` (mudam por ações dedicadas) e
    `tenant_id`/`id`/`id_veiculo`/`excluido` nunca aceitos."""

    tipo: ManutencaoTipo | None = None
    descricao: str | None = Field(default=None, min_length=1)
    data_prevista: date | None = None
    km_atual: int | None = Field(default=None, ge=0)
    fornecedor: str | None = Field(default=None, max_length=150)
    custo_estimado: float | None = Field(default=None, ge=0)
    observacoes: str | None = None


class VeiculoManutencaoConcluir(BaseModel):
    """Conclusão da manutenção — `data_conclusao` (default hoje no serviço),
    `custo_final` e `km_atual` opcionais."""

    data_conclusao: date | None = None
    custo_final: float | None = Field(default=None, ge=0)
    km_atual: int | None = Field(default=None, ge=0)
    observacoes: str | None = None


class VeiculoManutencaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_veiculo: int
    tipo: str
    descricao: str
    data_abertura: date
    data_prevista: date | None = None
    data_conclusao: date | None = None
    km_atual: int | None = None
    fornecedor: str | None = None
    custo_estimado: float | None = None
    custo_final: float | None = None
    status: str
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


# --- Abastecimento do Veículo (Frota — operacional) -------------------------
class VeiculoAbastecimentoCreate(BaseModel):
    """`id_veiculo` no corpo (validado same-tenant no serviço). `data_abastecimento`
    opcional (default hoje). `tenant_id`/`id`/`excluido` nunca aceitos."""

    id_veiculo: int
    id_motorista: int | None = None
    data_abastecimento: date | None = None
    km_atual: int = Field(ge=0)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    litros: float = Field(gt=0)
    valor_total: float = Field(ge=0)
    posto: str | None = Field(default=None, max_length=150)
    observacoes: str | None = None


class VeiculoAbastecimentoUpdate(BaseModel):
    """Whitelist de edição — `id_veiculo`/`tenant_id`/`id`/`excluido` nunca
    aceitos. (Edição não reprocessa a quilometragem do veículo.)"""

    id_motorista: int | None = None
    data_abastecimento: date | None = None
    km_atual: int | None = Field(default=None, ge=0)
    tipo_combustivel: str | None = Field(default=None, max_length=20)
    litros: float | None = Field(default=None, gt=0)
    valor_total: float | None = Field(default=None, ge=0)
    posto: str | None = Field(default=None, max_length=150)
    observacoes: str | None = None


class VeiculoAbastecimentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_veiculo: int
    id_motorista: int | None = None
    data_abastecimento: date
    km_atual: int
    tipo_combustivel: str | None = None
    litros: float
    valor_total: float
    posto: str | None = None
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


class AbastecimentoResumo(BaseModel):
    """Indicadores agregados (tenant-scoped, opcionalmente por veículo)."""

    total_abastecimentos: int
    total_litros: float
    total_valor: float
    media_valor_litro: float | None = None
    ultimo_abastecimento: date | None = None


# --- Vistoria / Checklist interno (Frota — operacional) ---------------------
VistoriaTipo = Literal["saida", "retorno", "periodica"]
VistoriaResultado = Literal["aprovada", "reprovada", "com_ressalvas"]


class VeiculoVistoriaBase(BaseModel):
    data_vistoria: date | None = None
    pneus_ok: bool = False
    luzes_ok: bool = False
    freios_ok: bool = False
    documentacao_ok: bool = False
    limpeza_ok: bool = False
    equipamentos_ok: bool = False
    observacoes: str | None = None


class VeiculoVistoriaCreate(VeiculoVistoriaBase):
    """`id_veiculo` no corpo (validado same-tenant). `tipo` e `resultado`
    obrigatórios. `tenant_id`/`id`/`excluido` nunca aceitos."""

    id_veiculo: int
    tipo: VistoriaTipo
    resultado: VistoriaResultado


class VeiculoVistoriaUpdate(BaseModel):
    """Whitelist de edição — `id_veiculo`/`tenant_id`/`id`/`excluido` nunca aceitos."""

    data_vistoria: date | None = None
    tipo: VistoriaTipo | None = None
    resultado: VistoriaResultado | None = None
    pneus_ok: bool | None = None
    luzes_ok: bool | None = None
    freios_ok: bool | None = None
    documentacao_ok: bool | None = None
    limpeza_ok: bool | None = None
    equipamentos_ok: bool | None = None
    observacoes: str | None = None


class VeiculoVistoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_veiculo: int
    data_vistoria: date
    tipo: str
    resultado: str
    pneus_ok: bool
    luzes_ok: bool
    freios_ok: bool
    documentacao_ok: bool
    limpeza_ok: bool
    equipamentos_ok: bool
    observacoes: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None

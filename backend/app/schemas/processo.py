from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProcessoCreate(BaseModel):
    id_assunto: int
    id_manifestante: int
    id_unidade_proprietaria: int
    observacao: str | None = Field(default=None, max_length=10000)
    corpo: str | None = Field(default=None, max_length=50000)
    numero_origem: str | None = None
    # `publico` é entrada legada; `nivel_sigilo` (ostensivo|interno) tem
    # precedência quando != ostensivo. Sigilo legal (reservado+) só via
    # endpoint de classificação, que captura o TCI.
    publico: bool = True
    nivel_sigilo: str = "ostensivo"
    externo: bool = False
    virtual: bool = True
    # Só "interno"/"email" aqui — "balcao" e "portal" são setados pelos
    # fluxos dedicados (protocolo de balcão, portal do cidadão); "api" é
    # programático. Ver `CanalEntrada` em schemas/protocolo.py para o
    # domínio completo da coluna.
    canal_entrada: Literal["interno", "email"] = "interno"


class ClassificarSigiloRequest(BaseModel):
    """Classifica/reclassifica o sigilo de um processo (LAI).

    Graus de sigilo legal (reservado/secreto/ultrassecreto) exigem
    `fundamento_legal` + `autoridade`; `prazo_anos` default = máximo legal.
    """

    nivel: str = Field(..., description="ostensivo|interno|reservado|secreto|ultrassecreto")
    fundamento_legal: str | None = Field(default=None, max_length=2000)
    autoridade: str | None = Field(default=None, max_length=300)
    prazo_anos: int | None = Field(default=None, ge=1, le=25)


class EncaminharRequest(BaseModel):
    id_unidade_destino: int
    id_prioridade: int
    quantidade_folhas: int = Field(default=0, ge=0)
    data_prazo: date | None = None
    despacho: str | None = Field(default=None, max_length=10000)
    # Strict workflow override: super-usuário pode quebrar o trilho do
    # workflow informando motivo. Será auditado.
    override_motivo: str | None = Field(default=None, max_length=500)


class CancelarEncaminhamentoRequest(BaseModel):
    despacho: str | None = Field(default=None, max_length=2000)
    override_motivo: str | None = Field(default=None, max_length=500)


class PrioridadeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    prioridade: str
    fator: int
    cor: str


class ProcessoListItem(BaseModel):
    """Visão para listagem — campos enriquecidos com nomes via JOIN."""
    id: int
    numero_processo: str
    nup: str | None = None  # Fase P2 — NUP federal (preenchido só se tenant tem flag)
    numero_origem: str | None
    data_hora_abertura: datetime
    ativo: bool
    publico: bool
    nivel_sigilo: str = "ostensivo"
    externo: bool
    canal_entrada: str | None = None

    assunto: str | None
    tipo_processo: str | None
    manifestante: str | None
    manifestante_cpf_cnpj: str | None
    unidade_proprietaria: str | None
    local_atual: str | None

    # F2 — responsável-pessoa. `None` NÃO é ausência de dado: é o estado
    # "pendente de designação", que a tela mostra como tal. Default nos dois
    # para não quebrar quem monta o schema à mão (testes, fixtures), já que o
    # valor correto nesse caso é justamente "sem responsável".
    id_usuario_responsavel: int | None = None
    responsavel: str | None = None


class EscopoProcesso(str, Enum):
    """Recorte da lista por responsabilidade. Ausente = sem recorte (tudo).

    `unidade` e `unidade_e_subordinadas` recortam pelo LOCAL ATUAL do processo,
    não pela unidade proprietária: o que interessa a quem opera é o que está na
    sua mesa agora, não o que nasceu ali e já saiu.
    """

    meus = "meus"
    unidade = "unidade"
    unidade_e_subordinadas = "unidade_e_subordinadas"


class DestinosPermitidosOut(BaseModel):
    """F3 — unidades que o workflow ativo permite como próximo destino.

    `restrito=False` é o comportamento de hoje (nenhuma restrição — a tela
    oferece todas as unidades); `ids_unidade=None` só ocorre junto disso.
    """

    restrito: bool
    ids_unidade: list[int] | None = None
    motivo: str | None = None


class ArquivarRequest(BaseModel):
    """F4 — encerramento do processo por arquivamento.

    `motivo` é obrigatório pelo mesmo princípio de `apensamento.motivo`: ato que
    encerra o processo tem de dizer por quê, e campo opcional vira campo vazio.

    `observacao` não é coluna de `protocolos.arquivamento` — vira um `Despacho`
    ligado à movimentação, que é o mecanismo que a linha do tempo já renderiza.
    Criar coluna nova para texto livre duplicaria o que existe.

    Os campos de endereçamento físico (`local`, `estante`, `prateleira`,
    `caixa`, `pasta`) são colunas da tabela legada e ficam opcionais: processo
    virtual não tem prateleira.
    """

    motivo: str = Field(min_length=3, max_length=255)
    observacao: str | None = Field(default=None, max_length=10000)
    local: str | None = Field(default=None, max_length=255)
    estante: str | None = Field(default=None, max_length=255)
    prateleira: str | None = Field(default=None, max_length=255)
    caixa: str | None = Field(default=None, max_length=255)
    pasta: str | None = Field(default=None, max_length=255)
    permanente: bool = False
    # Workflow strict: arquivar fora de estado final é bloqueado; super-usuário
    # passa informando motivo, que é auditado. Mesmo contrato de `encaminhar`.
    override_motivo: str | None = Field(default=None, max_length=500)


class AtribuirResponsavelRequest(BaseModel):
    """`id_usuario=None` desatribui — volta ao estado pendente de designação."""

    id_usuario: int | None = None


class AnexoNoProcesso(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int  # id do Anexo (file row)
    id_anexo_processo: int | None = None  # id do join AnexoProcesso (pra desentranhar)
    descricao: str | None
    publico: bool
    qtd_paginas: int | None
    e_doc: str | None
    tipo_anexo: str | None = None
    ordem: int | None = None


class EncaminhamentoOut(BaseModel):
    id: int
    unidade_origem: str | None
    unidade_destino: str
    prioridade: str | None
    quantidade_folhas: int
    data_prazo: date | None
    recebido: bool
    data_hora_recebimento: datetime | None
    cancelado: bool


class DespachoOut(BaseModel):
    id: int
    despacho: str
    usuario: str | None


class PermanenciaNo(BaseModel):
    """Quanto tempo o processo ficou NESTE nó da linha do tempo.

    `natureza` separa fila de trabalho: `espera` é o processo encaminhado
    aguardando alguém receber, `analise` é o processo nas mãos de alguém,
    `encerrado` é o trecho posterior ao arquivamento — que não é nenhum dos
    dois e não entra no total ativo. A regra vive em `services/permanencia.py`.

    Segundos, e não `timedelta`: Pydantic serializa `timedelta` como duração
    ISO-8601 (`P1DT2H`), que o front teria de reparsear para formatar.
    """

    segundos: int
    natureza: Literal["espera", "analise", "encerrado"]
    # `aberto` = não há nó posterior; este tempo ainda está correndo.
    aberto: bool


class PermanenciaProcesso(BaseModel):
    """O agregado do processo. Sempre presente, como `prazo`."""

    # Espera + análise. NÃO é abertura->agora: ver `PermanenciaNo.natureza`.
    total_ativo_segundos: int
    espera_segundos: int
    analise_segundos: int
    tramitacoes: int
    em_curso: bool


class MovimentacaoItem(BaseModel):
    """Item da timeline — agrega acao + despacho + encaminhamento opcionais."""
    id: int
    data_hora_movimentacao: datetime
    acao_flag: str
    acao: str
    status_acao: str
    status_movimentacao: str
    unidade_responsavel: str | None
    usuario: str | None
    despacho: DespachoOut | None = None
    encaminhamento: EncaminhamentoOut | None = None
    permanencia: PermanenciaNo


class PrazoInfo(BaseModel):
    """Bloco de prazo no detalhe do processo (admin). PR 5b.

    `status` reflete o cálculo end-to-end do processo a partir de
    `prazo_servico_dias_snapshot` (congelado na abertura). Cidadão recebe
    versão reduzida em `PrazoCidadao` (schemas/cidadao.py).
    """

    status: Literal[
        "sem_prazo",
        "dentro_do_prazo",
        "vencendo",
        "atrasado",
        "concluido_no_prazo",
        "concluido_atrasado",
    ]
    prazo_servico_dias_snapshot: int | None
    prazo_previsto_em: datetime | None
    dias_restantes: int | None  # >0 quando há folga; None se sem_prazo/atrasado
    dias_atraso: int | None  # >0 quando em atraso; None se não atrasado
    concluido_em: datetime | None
    origem: Literal["servico"] | None  # None quando status='sem_prazo'


class ProcessoDetail(ProcessoListItem):
    observacao: str | None
    corpo: str | None
    virtual: bool
    migrado: bool
    id_processo_pai: int | None

    # Sigilo gradual — TCI (preenchido só para graus de sigilo legal).
    sigilo_fundamento_legal: str | None = None
    sigilo_autoridade: str | None = None
    sigilo_prazo_anos: int | None = None
    sigilo_data_classificacao: datetime | None = None
    sigilo_data_desclassificacao: date | None = None

    movimentacoes: list[MovimentacaoItem]
    anexos: list[AnexoNoProcesso]

    # PR 5b — bloco de prazo end-to-end (sempre presente; status='sem_prazo'
    # em processos legados ou sem prazo definido no serviço).
    prazo: PrazoInfo

    # F1 — permanência agregada. Sempre presente; zerada em processo sem
    # movimentação (que não existe no fluxo normal, mas existe em base migrada).
    permanencia: PermanenciaProcesso

"""Schemas Pydantic do Workflow — Fase 19.

Definem a estrutura do DSL JSON que vive em `aprimora_py.workflow_definition.dsl`.
A intenção é ser simples e legível por humanos (consultor de implantação edita
JSON em editor de texto antes da UI React Flow chegar na fase 22).

Exemplo de DSL:

```json
{
  "version": "1.0",
  "estado_inicial": "solicitado",
  "estados": [
    {"slug": "solicitado", "nome": "Solicitado"},
    {"slug": "analise_chefia", "nome": "Em análise pela chefia", "sla_dias": 3},
    {"slug": "aprovado", "nome": "Aprovado", "final": true}
  ],
  "transicoes": [
    {
      "de": "solicitado",
      "para": "analise_chefia",
      "label": "Encaminhar para chefia",
      "condicao": null
    },
    {
      "de": "analise_chefia",
      "para": "aprovado",
      "label": "Aprovar",
      "condicao": "dias_aberto < 30"
    }
  ]
}
```
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PosicaoXY(BaseModel):
    """Posição opcional do nodo no editor (Fase 22b). Float pra permitir
    drag suave em qualquer resolução."""

    x: float
    y: float


class WorkflowEstado(BaseModel):
    slug: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z][a-z0-9_]*$")
    nome: str = Field(..., min_length=1, max_length=120)
    descricao: str | None = None
    final: bool = False  # Estados finais não permitem transições saindo
    sla_dias: int | None = Field(None, ge=1, le=365)
    # Fase 22b — posição no editor visual. Quando ausente, o renderer usa
    # layout BFS automático. Backend não lê pra lógica de negócio.
    posicao: PosicaoXY | None = None
    # Workflow↔Org (UX fix): unidade responsável pelo estado. Quando setada,
    # `executar_transicao` faz auto-encaminhamento do processo para essa
    # unidade ao entrar nela; `transicoes_disponiveis` esconde transições
    # cujo estado destino tem unidade diferente da unidade do usuário
    # (bypass pra super-usuário). Null = sem amarração.
    id_unidade_responsavel: int | None = None


class WorkflowTransicao(BaseModel):
    de: str = Field(..., description="slug do estado de origem")
    para: str = Field(..., description="slug do estado de destino")
    label: str = Field(..., min_length=1, max_length=120, description="Texto do botão/ação na UI")
    descricao: str | None = None
    # Expressão SAFE — None significa transição sempre permitida.
    # Avaliada via simpleeval em workflow_dsl.evaluate_expr (NUNCA eval()).
    condicao: str | None = Field(None, max_length=500)
    # Grupos de usuários que podem executar (lista de slugs de grupo do tenant).
    grupos_permitidos: list[str] = Field(default_factory=list)
    # Evento gatilho — Fase 20b. "manual" = só via API; "abertura" = dispara
    # logo após criar a instance; "encaminhamento"/"recebimento" = disparados
    # automaticamente quando o processo associado é encaminhado/recebido.
    evento: str = Field(
        default="manual",
        pattern=r"^(manual|abertura|encaminhamento|recebimento)$",
    )


class WorkflowDSL(BaseModel):
    """Representação tipada do DSL. Validado na criação/atualização."""

    model_config = ConfigDict(extra="forbid")

    version: str = "1.0"
    estado_inicial: str
    estados: list[WorkflowEstado] = Field(..., min_length=1)
    transicoes: list[WorkflowTransicao] = Field(default_factory=list)

    @field_validator("estados")
    @classmethod
    def _estados_slugs_unicos(cls, v: list[WorkflowEstado]) -> list[WorkflowEstado]:
        slugs = [e.slug for e in v]
        if len(slugs) != len(set(slugs)):
            duplicados = sorted({s for s in slugs if slugs.count(s) > 1})
            raise ValueError(f"Slugs de estado duplicados: {duplicados}")
        return v

    @model_validator(mode="after")
    def _validar_referencias(self) -> "WorkflowDSL":
        slugs = {e.slug for e in self.estados}

        if self.estado_inicial not in slugs:
            raise ValueError(
                f"estado_inicial '{self.estado_inicial}' não está na lista de estados"
            )

        estados_finais = {e.slug for e in self.estados if e.final}
        # Cada transição referencia estados válidos + não sai de estado final.
        for i, t in enumerate(self.transicoes):
            if t.de not in slugs:
                raise ValueError(f"transicoes[{i}].de='{t.de}' não existe nos estados")
            if t.para not in slugs:
                raise ValueError(f"transicoes[{i}].para='{t.para}' não existe nos estados")
            if t.de in estados_finais:
                raise ValueError(
                    f"transicoes[{i}] sai de estado final '{t.de}' — proibido"
                )

        # Pelo menos um estado final é recomendado (warning no router, não bloqueia).
        return self


# ===== API I/O =====


class WorkflowDefinitionCreate(BaseModel):
    slug: str = Field(..., min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_-]*$")
    nome: str = Field(..., min_length=1, max_length=200)
    descricao: str | None = None
    dsl: WorkflowDSL


class WorkflowDefinitionUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=200)
    descricao: str | None = None
    dsl: WorkflowDSL | None = None
    ativo: bool | None = None


class WorkflowDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    descricao: str | None
    versao: int
    ativo: bool
    dsl: WorkflowDSL
    criado_em: datetime
    atualizado_em: datetime | None
    id_usuario_criador: int | None


class WorkflowDefinitionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    nome: str
    versao: int
    ativo: bool
    criado_em: datetime


# ===== Avaliador de expressões =====


class EvaluateExprRequest(BaseModel):
    """Payload para `POST /api/v2/workflow-definitions/test-expr`."""

    expressao: str = Field(..., min_length=1, max_length=500)
    contexto: dict = Field(default_factory=dict, description="Variáveis disponíveis na expressão")


class EvaluateExprResponse(BaseModel):
    resultado: bool | int | float | str | None
    truthy: bool
    erro: str | None = None


# ===== Instâncias (Fase 20a) =====


class WorkflowInstanceCreate(BaseModel):
    id_workflow_definition: int
    id_processo: int


class WorkflowTransicaoExec(BaseModel):
    """Body do POST /workflow-instances/{id}/transicao."""
    para: str = Field(..., description="slug do estado destino")
    contexto_extra: dict = Field(
        default_factory=dict,
        description="Variáveis extras passadas para o avaliador (sobrescrevem auto-contexto)",
    )


class TransicaoDisponivel(BaseModel):
    """Uma transição habilitada para o estado atual da instance."""
    de: str
    para: str
    label: str
    descricao: str | None = None
    grupos_permitidos: list[str] = Field(default_factory=list)


class WorkflowTransicaoLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    estado_de: str
    estado_para: str
    transicao_label: str
    id_usuario: int | None
    executada_em: datetime
    contexto_snapshot: dict | None


class WorkflowInstanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_workflow_definition: int
    id_processo: int
    estado_atual: str
    ativa: bool
    iniciada_em: datetime
    finalizada_em: datetime | None
    id_usuario_inicio: int | None


class WorkflowInstanceDetail(WorkflowInstanceOut):
    """Detalhe: instance + transições disponíveis + log."""
    transicoes_disponiveis: list[TransicaoDisponivel]
    log: list[WorkflowTransicaoLogOut]
    contexto_atual: dict


# ===== Mapeamento tipo_processo → workflow (Fase 20b) =====


class TipoProcessoWorkflowSet(BaseModel):
    """Body do PUT /tipo-processo-workflow/{id_tipo_processo}."""
    slug_workflow: str | None = Field(
        None,
        description="Slug do workflow_definition a auto-instanciar. None remove o mapeamento.",
        max_length=80,
    )


class TipoProcessoWorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_tipo_processo: int
    slug_workflow: str
    criado_em: datetime
    atualizado_em: datetime | None


# ===== SLA alertas (Fase 21) =====


class WorkflowSlaAlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_workflow_instance: int
    estado: str
    sla_dias: int
    dias_no_estado: int
    criado_em: datetime
    resolvido_em: datetime | None
    resolucao: str | None
    notificado_em: datetime | None


class WorkflowSlaAlertaDetail(WorkflowSlaAlertaOut):
    """Detalhe — inclui dados do processo associado para a listagem em UI."""
    id_processo: int
    numero_processo: str | None
    estado_atual: str  # estado atual da instance (pode ter mudado desde o alerta)
    instance_ativa: bool


class WorkflowSlaAlertaResolve(BaseModel):
    """Body do POST /workflow-alertas/{id}/resolver — resolução manual.

    `resolucao` é uma string curta livre (max 40) tipo "ciente",
    "escalado", "reagendado". O engine usa "transitado" automaticamente
    quando o estado muda.
    """
    resolucao: str = Field(..., min_length=1, max_length=40)

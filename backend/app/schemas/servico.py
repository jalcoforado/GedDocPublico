"""Schemas do Catálogo de Serviços (PR 4a).

`documentos_exigidos` é validado como **lista de objetos** simples (D1): payload
malformado (não-lista, item sem `nome`) cai em 422 pela validação do Pydantic.
A projeção pública (`ServicoPublicOut`) nunca expõe campos internos.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NivelSigilo = Literal["ostensivo", "interno", "reservado", "secreto", "ultrassecreto"]
CanalEntrada = Literal["balcao", "portal", "email", "api", "interno"]
SLUG_PATTERN = r"^[a-z0-9][a-z0-9-]{1,78}[a-z0-9]$"


class ServicoDocumento(BaseModel):
    """Item de `documentos_exigidos` (JSONB)."""

    nome: str = Field(min_length=1, max_length=150)
    obrigatorio: bool = False
    descricao: str | None = Field(default=None, max_length=500)


class ServicoCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    slug: str = Field(pattern=SLUG_PATTERN, max_length=80)
    descricao_curta: str | None = Field(default=None, max_length=300)
    descricao_detalhada: str | None = None
    publico_alvo: str | None = Field(default=None, max_length=255)
    instrucoes_cidadao: str | None = None
    documentos_exigidos: list[ServicoDocumento] | None = None
    prazo_estimado_dias: int | None = Field(default=None, ge=0)
    id_unidade_responsavel: int | None = None
    id_tipo_processo_padrao: int | None = None
    id_assunto_padrao: int | None = None
    id_especie_documental_padrao: int | None = None
    nivel_sigilo_padrao: NivelSigilo = "ostensivo"
    canal_entrada_permitido: CanalEntrada = "portal"
    destaque: bool = False
    ordem_exibicao: int = 0
    categoria: str | None = Field(default=None, max_length=80)
    texto_confirmacao: str | None = None


class ServicoUpdate(BaseModel):
    """Whitelist de edição. `tenant_id`/`id`/`ativo`/`excluido` nunca aceitos
    (ativar/desativar têm endpoints próprios)."""

    nome: str | None = Field(default=None, min_length=1, max_length=150)
    slug: str | None = Field(default=None, pattern=SLUG_PATTERN, max_length=80)
    descricao_curta: str | None = Field(default=None, max_length=300)
    descricao_detalhada: str | None = None
    publico_alvo: str | None = Field(default=None, max_length=255)
    instrucoes_cidadao: str | None = None
    documentos_exigidos: list[ServicoDocumento] | None = None
    prazo_estimado_dias: int | None = Field(default=None, ge=0)
    id_unidade_responsavel: int | None = None
    id_tipo_processo_padrao: int | None = None
    id_assunto_padrao: int | None = None
    id_especie_documental_padrao: int | None = None
    nivel_sigilo_padrao: NivelSigilo | None = None
    canal_entrada_permitido: CanalEntrada | None = None
    destaque: bool | None = None
    ordem_exibicao: int | None = None
    categoria: str | None = Field(default=None, max_length=80)
    texto_confirmacao: str | None = None


class ServicoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    slug: str
    descricao_curta: str | None = None
    descricao_detalhada: str | None = None
    publico_alvo: str | None = None
    instrucoes_cidadao: str | None = None
    documentos_exigidos: list[ServicoDocumento] | None = None
    prazo_estimado_dias: int | None = None
    id_unidade_responsavel: int | None = None
    id_tipo_processo_padrao: int | None = None
    id_assunto_padrao: int | None = None
    id_especie_documental_padrao: int | None = None
    nivel_sigilo_padrao: str
    canal_entrada_permitido: str
    ativo: bool
    destaque: bool
    ordem_exibicao: int
    categoria: str | None = None
    texto_confirmacao: str | None = None
    criado_em: datetime
    atualizado_em: datetime | None = None


class ServicoPublicOut(BaseModel):
    """Projeção pública SEGURA — sem ids internos, sigilo, canal ou flags admin."""

    nome: str
    slug: str
    descricao_curta: str | None = None
    descricao_detalhada: str | None = None
    publico_alvo: str | None = None
    instrucoes_cidadao: str | None = None
    prazo_estimado_dias: int | None = None
    unidade_responsavel: str | None = None
    documentos_exigidos: list[ServicoDocumento] | None = None
    categoria: str | None = None
    destaque: bool
    ordem_exibicao: int
    # Mensagem ao cidadão exibida na confirmação/tela final (citizen-facing).
    texto_confirmacao: str | None = None
    # PR 4b: true só quando o serviço está solicitável pelo portal (§ _to_public).
    solicitar_habilitado: bool = False

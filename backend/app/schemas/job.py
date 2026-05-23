from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    descricao: str | None
    status: str
    parametros: dict[str, Any] | None
    resultado_path: str | None
    erro: str | None
    id_usuario: int
    nome_usuario: str | None = None
    celery_task_id: str | None
    criado_em: datetime
    iniciado_em: datetime | None
    concluido_em: datetime | None


class DispararProcessoCompletoRequest(BaseModel):
    id_processo: int


class DispararCarimbarAnexosRequest(BaseModel):
    id_processo: int


class DispararRelatorioTramitacaoRequest(BaseModel):
    id_unidade: int | None = None
    id_assunto: int | None = None
    id_tipo_processo: int | None = None
    desde: datetime | None = None
    ate: datetime | None = None
    apenas_ativos: bool = False
    max_processos: int = 200


class DispararLimpezaRequest(BaseModel):
    dias: int = 30


class AgendaItem(BaseModel):
    nome: str
    task: str
    schedule: str
    kwargs: dict[str, Any] | None = None

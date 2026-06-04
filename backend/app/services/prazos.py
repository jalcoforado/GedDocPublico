"""Cálculo de prazo end-to-end de processo (PR 5b).

Helper puro. Recebe dados já carregados, devolve dados derivados. Não
acessa banco. Não conhece schemas Pydantic. Reutilizado por:

- routers/processos detail (admin)
- routers/cidadao detail (com mapeamento reduzido — `status_cidadao`)
- services/dashboard (a versão SQL agregada replica a mesma regra)
- testes

Conceito (D-SNAPSHOT, D-NOME, D-CONCLUSAO, D-VENCENDO do PR 5b):

- O prazo é congelado em `processo.prazo_servico_dias_snapshot` na abertura
  por serviço. Mudanças posteriores em `servico.prazo_estimado_dias` NÃO
  reverberam — promessa estável ao cidadão.
- Fim do processo (`data_conclusao`) = data da ÚLTIMA `Movimentacao` ativa
  com `id_arquivamento IS NOT NULL`. Caller resolve antes de chamar o
  helper; quando não há, passa `None` → tratado como "em andamento".
- "Vencendo" = restante ≤ 20% do prazo, com mínimo de 1 dia, sem teto.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil
from typing import Literal

StatusPrazo = Literal[
    "sem_prazo",
    "dentro_do_prazo",
    "vencendo",
    "atrasado",
    "concluido_no_prazo",
    "concluido_atrasado",
]

StatusPrazoCidadao = Literal[
    "sem_previsao",
    "dentro_da_previsao",
    "proximo_do_prazo",
    "fora_da_previsao",
    "concluido",
]


@dataclass(frozen=True)
class PrazoCalculado:
    status: StatusPrazo
    prazo_servico_dias_snapshot: int | None
    prazo_previsto_em: datetime | None
    dias_restantes: int | None  # >0 quando há folga; None quando sem_prazo/atrasado
    dias_atraso: int | None  # >0 quando em atraso; None se não atrasado
    concluido_em: datetime | None


def limiar_vencendo_dias(prazo_snapshot_dias: int) -> int:
    """20% do prazo, com mínimo de 1 dia. Sem teto.

    Exemplos: prazo 30 → 6d; 10 → 2d; 3 → 1d; 1 → 1d.
    """
    if prazo_snapshot_dias <= 0:
        return 1
    return max(1, ceil(prazo_snapshot_dias * 0.2))


def calcular_prazo(
    *,
    data_abertura: datetime,
    prazo_snapshot_dias: int | None,
    data_conclusao: datetime | None,
    now: datetime,
) -> PrazoCalculado:
    """Calcula `status` e datas derivadas.

    Regras:
    - Sem `prazo_snapshot_dias` → `sem_prazo` (independente de conclusão).
    - Com snapshot e `data_conclusao` setada → `concluido_{no_prazo|atrasado}`
      comparando contra `data_abertura + snapshot dias`.
    - Sem `data_conclusao`, com snapshot → estado em andamento:
      `atrasado` se já passou, `vencendo` se está nos últimos
      `limiar_vencendo_dias`, senão `dentro_do_prazo`.
    """
    if prazo_snapshot_dias is None:
        return PrazoCalculado(
            status="sem_prazo",
            prazo_servico_dias_snapshot=None,
            prazo_previsto_em=None,
            dias_restantes=None,
            dias_atraso=None,
            concluido_em=data_conclusao,
        )

    prazo_previsto = data_abertura + timedelta(days=prazo_snapshot_dias)

    if data_conclusao is not None:
        no_prazo = data_conclusao <= prazo_previsto
        delta_dias = (prazo_previsto - data_conclusao).days
        return PrazoCalculado(
            status="concluido_no_prazo" if no_prazo else "concluido_atrasado",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=delta_dias if no_prazo else None,
            dias_atraso=(-delta_dias) if not no_prazo else None,
            concluido_em=data_conclusao,
        )

    delta_dias = (prazo_previsto - now).days
    if delta_dias < 0:
        return PrazoCalculado(
            status="atrasado",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=None,
            dias_atraso=-delta_dias,
            concluido_em=None,
        )
    if delta_dias <= limiar_vencendo_dias(prazo_snapshot_dias):
        return PrazoCalculado(
            status="vencendo",
            prazo_servico_dias_snapshot=prazo_snapshot_dias,
            prazo_previsto_em=prazo_previsto,
            dias_restantes=delta_dias,
            dias_atraso=None,
            concluido_em=None,
        )
    return PrazoCalculado(
        status="dentro_do_prazo",
        prazo_servico_dias_snapshot=prazo_snapshot_dias,
        prazo_previsto_em=prazo_previsto,
        dias_restantes=delta_dias,
        dias_atraso=None,
        concluido_em=None,
    )


_CIDADAO_MAP: dict[StatusPrazo, StatusPrazoCidadao] = {
    "sem_prazo": "sem_previsao",
    "dentro_do_prazo": "dentro_da_previsao",
    "vencendo": "proximo_do_prazo",
    "atrasado": "fora_da_previsao",
    "concluido_no_prazo": "concluido",
    "concluido_atrasado": "concluido",
}


def status_cidadao(status_admin: StatusPrazo) -> StatusPrazoCidadao:
    """Mapeamento p/ portal cidadão. Concluído (no prazo ou com atraso) vira
    sempre 'concluido' — cidadão não recebe juízo sobre tempestividade."""
    return _CIDADAO_MAP[status_admin]

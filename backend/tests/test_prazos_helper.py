"""PR 5b — testes do helper puro `app/services/prazos.py`.

Sem banco, sem fixtures HTTP — só dataclass + comparações de datas.
Cobre as regras D-CONCLUSAO (6 status), D-VENCENDO (20% com mínimo de 1d,
sem teto) e o mapeamento D-CIDADAO (6 → 5).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services.prazos import (
    calcular_prazo,
    limiar_vencendo_dias,
    status_cidadao,
)

NOW = datetime(2026, 6, 4, 12, 0, 0)


def _abrir(dias_atras: int) -> datetime:
    return NOW - timedelta(days=dias_atras)


def test_sem_snapshot_devolve_sem_prazo() -> None:
    r = calcular_prazo(
        data_abertura=_abrir(5),
        prazo_snapshot_dias=None,
        data_conclusao=None,
        now=NOW,
    )
    assert r.status == "sem_prazo"
    assert r.prazo_previsto_em is None
    assert r.dias_restantes is None
    assert r.dias_atraso is None


def test_sem_snapshot_mesmo_concluido_continua_sem_prazo() -> None:
    """Legado concluído não dá pra classificar como no_prazo/atrasado — sem snapshot, sem comparação."""
    r = calcular_prazo(
        data_abertura=_abrir(20),
        prazo_snapshot_dias=None,
        data_conclusao=_abrir(2),
        now=NOW,
    )
    assert r.status == "sem_prazo"
    assert r.concluido_em == _abrir(2)


def test_em_andamento_com_folga_grande_dentro_do_prazo() -> None:
    # Aberto há 1 dia, prazo de 30 → restam ~29 dias, muito acima do limiar (6).
    r = calcular_prazo(
        data_abertura=_abrir(1),
        prazo_snapshot_dias=30,
        data_conclusao=None,
        now=NOW,
    )
    assert r.status == "dentro_do_prazo"
    assert r.dias_restantes == 29
    assert r.dias_atraso is None


def test_em_andamento_dentro_do_limiar_e_vencendo() -> None:
    # Aberto há 26 dias, prazo de 30 → restam 4 dias, abaixo do limiar (6).
    r = calcular_prazo(
        data_abertura=_abrir(26),
        prazo_snapshot_dias=30,
        data_conclusao=None,
        now=NOW,
    )
    assert r.status == "vencendo"
    assert r.dias_restantes == 4
    assert r.dias_atraso is None


def test_em_andamento_prazo_passou_atrasado() -> None:
    # Aberto há 35 dias, prazo de 30 → 5 dias de atraso.
    r = calcular_prazo(
        data_abertura=_abrir(35),
        prazo_snapshot_dias=30,
        data_conclusao=None,
        now=NOW,
    )
    assert r.status == "atrasado"
    assert r.dias_atraso == 5
    assert r.dias_restantes is None


def test_concluido_no_prazo() -> None:
    # Aberto há 10d, prazo 15, concluído há 2d → no prazo.
    r = calcular_prazo(
        data_abertura=_abrir(10),
        prazo_snapshot_dias=15,
        data_conclusao=_abrir(2),
        now=NOW,
    )
    assert r.status == "concluido_no_prazo"
    assert r.concluido_em == _abrir(2)
    assert r.dias_atraso is None
    assert r.dias_restantes is not None and r.dias_restantes >= 0


def test_concluido_com_atraso() -> None:
    # Aberto há 30d, prazo 10, concluído há 2d → atraso de 18d.
    r = calcular_prazo(
        data_abertura=_abrir(30),
        prazo_snapshot_dias=10,
        data_conclusao=_abrir(2),
        now=NOW,
    )
    assert r.status == "concluido_atrasado"
    assert r.dias_atraso == 18
    assert r.dias_restantes is None


@pytest.mark.parametrize(
    "prazo,esperado",
    [
        (30, 6),
        (10, 2),
        (5, 1),
        (3, 1),
        (1, 1),
        (0, 1),    # edge: prazo zero não deveria existir, mas guarda piso.
        (-5, 1),   # idem.
        (100, 20),  # sem teto — 20% bate em 20d.
    ],
)
def test_limiar_vencendo_regra_20pct_min_1(prazo: int, esperado: int) -> None:
    assert limiar_vencendo_dias(prazo) == esperado


def test_status_cidadao_mapeamento_6_para_5() -> None:
    assert status_cidadao("sem_prazo") == "sem_previsao"
    assert status_cidadao("dentro_do_prazo") == "dentro_da_previsao"
    assert status_cidadao("vencendo") == "proximo_do_prazo"
    assert status_cidadao("atrasado") == "fora_da_previsao"
    # Concluído (ambos os sub-status) colapsam num único valor cidadão.
    assert status_cidadao("concluido_no_prazo") == "concluido"
    assert status_cidadao("concluido_atrasado") == "concluido"

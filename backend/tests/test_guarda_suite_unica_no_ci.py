"""Guarda: a suíte roda UMA vez no CI (item 1.0.66).

Até 2026-08-16 o `backend-tests.yml` tinha dois passos que rodavam
`pytest tests/` inteiro: o de teste e um "Coverage report" logo abaixo, com
`|| true`. Medido no job `95111304477`:

    Run pytest        8 min 49 s
    Coverage report  10 min 11 s   ← a mesma suíte de novo, instrumentada

**Mais da metade do job era duplicata.** O item 1.0.66 do backlog discutia
`pytest-xdist` e banco por worker — trabalho grande e arriscado — sem que
ninguém tivesse olhado onde o tempo ia. O bootstrap inteiro (dump, migrations,
seeds), que parecia o suspeito, leva 35 s.

Esta guarda existe porque **duplicar a suíte não quebra nada**. Não há teste
vermelho, não há alerta, não há sintoma: o job só fica mais lento, e "o CI está
lento" é queixa que ninguém rastreia até a linha do YAML. Foi assim que a
duplicata sobreviveu — e é assim que ela voltaria.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[2]
    / ".github"
    / "workflows"
    / "backend-tests.yml"
)

#: Invocação da suíte INTEIRA. `pytest tests/test_x.py` ou `pytest -k algo` não
#: contam: rodar um subconjunto de propósito é legítimo (um passo de smoke, por
#: exemplo). O que a guarda proíbe é a suíte completa duas vezes.
_SUITE_INTEIRA = re.compile(r"pytest\s+tests/(?:\s|$)")


def _exige_workflow() -> None:
    """Pula fora do CI; **falha** dentro dele.

    Mesma assimetria de `test_guarda_portao_de_deploy.py`, pelo mesmo motivo: o
    container local monta só `./backend:/app` e `.github/` não existe ali.
    """
    if WORKFLOW.exists():
        return
    if os.getenv("CI"):
        pytest.fail(
            f"`{WORKFLOW}` não encontrado COM CI=1. Esta guarda não pode ser "
            "pulada no CI; se a estrutura mudou, conserte o caminho."
        )
    pytest.skip(".github/workflows fora do alcance do container. Roda no CI.")


def test_a_suite_inteira_roda_uma_vez_so():
    _exige_workflow()
    linhas = WORKFLOW.read_text(encoding="utf-8").splitlines()
    # Só linhas de comando: comentários citam `pytest tests/` ao explicar a
    # própria regra, e contá-los faria a guarda reprovar a documentação dela.
    invocacoes = [
        linha.strip()
        for linha in linhas
        if _SUITE_INTEIRA.search(linha) and not linha.lstrip().startswith("#")
    ]
    assert len(invocacoes) == 1, (
        "A suíte inteira aparece "
        f"{len(invocacoes)} vez(es) em backend-tests.yml:\n  "
        + "\n  ".join(invocacoes)
        + "\n\nRodar duas vezes não quebra nada — só dobra o job, em silêncio. "
        "Cobertura vai na MESMA execução (`--cov` junto do `-v`)."
    )


def test_a_execucao_unica_ainda_produz_cobertura():
    """Controle: sem isto, apagar o passo de cobertura passaria verde.

    O teste acima ficaria satisfeito com **zero** cobertura — uma invocação só,
    afinal. A economia de tempo não pode ser paga com a perda do relatório.
    """
    _exige_workflow()
    texto = WORKFLOW.read_text(encoding="utf-8")
    assert "--cov=app" in texto, "o `--cov=app` sumiu: o CI parou de medir cobertura"
    assert "--cov-report=xml" in texto, (
        "o relatório XML sumiu, e é ele que alimenta o artefato `coverage-xml`"
    )

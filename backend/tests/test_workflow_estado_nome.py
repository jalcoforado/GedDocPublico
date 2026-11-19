"""SI-57 — abrir a definição de um workflow do transporte dava 500.

As sementes de `services/transporte_workflow.py` gravavam os estados com
`label`, e `WorkflowEstado` exige `nome`: a validação da resposta de
`GET /api/v2/workflow-definitions/{id}` estourava. Testes puros de schema,
sem banco: o defeito mora inteiro na validação do DSL.
"""

import pytest

from app.schemas.workflow import WorkflowDSL, WorkflowEstado
from app.services.transporte_workflow import SEMENTES


@pytest.mark.parametrize("slug", sorted(SEMENTES))
def test_toda_semente_valida_contra_o_schema(slug):
    """A semente nova já nasce no formato que a API devolve."""
    dsl = WorkflowDSL.model_validate(SEMENTES[slug])
    for estado in dsl.estados:
        assert estado.nome


@pytest.mark.parametrize("slug", sorted(SEMENTES))
def test_semente_usa_nome_e_nao_label_nos_estados(slug):
    """Guarda contra a volta do formato antigo na própria semente."""
    for estado in SEMENTES[slug]["estados"]:
        assert "nome" in estado, estado
        assert "label" not in estado, estado


def test_estado_gravado_com_label_ainda_e_lido():
    """Definições já criadas no banco continuam com `label` — e precisam abrir."""
    estado = WorkflowEstado.model_validate({"slug": "registrada", "label": "Registrada"})
    assert estado.nome == "Registrada"
    assert "label" not in estado.model_dump()


def test_nome_prevalece_quando_vem_os_dois():
    estado = WorkflowEstado.model_validate(
        {"slug": "registrada", "nome": "Registrada", "label": "Outro"}
    )
    assert estado.nome == "Registrada"


def test_dsl_antigo_inteiro_valida():
    """O DSL exatamente como foi gravado antes da correção."""
    antigo = {
        **SEMENTES["transporte-ocorrencia"],
        "estados": [
            {"slug": e["slug"], "label": e["nome"], **({"final": True} if e.get("final") else {})}
            for e in SEMENTES["transporte-ocorrencia"]["estados"]
        ],
    }
    dsl = WorkflowDSL.model_validate(antigo)
    assert [e.nome for e in dsl.estados][:2] == ["Registrada", "Em apuração"]


def test_estado_sem_nome_nem_label_continua_invalido():
    with pytest.raises(ValueError):
        WorkflowEstado.model_validate({"slug": "registrada"})

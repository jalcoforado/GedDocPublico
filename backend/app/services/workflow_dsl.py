"""Avaliador SAFE de expressões do DSL de workflow — Fase 19.

Por que não `eval()`: aceitar expressões arbitrárias do tenant em `eval()`
permite RCE (`__import__('os').system(...)`). Usamos `simpleeval` que:
- Limita operadores e funções a um conjunto whitelisted
- Não tem acesso a __builtins__
- Permite definir funções/variáveis explicitamente

Operadores permitidos (default do simpleeval):
- aritméticos: +, -, *, /, //, %
- comparações: ==, !=, <, <=, >, >=, in, not in
- lógicos: and, or, not
- pertinência: in, not in (list, str, dict)

Funções extras whitelisted aqui:
- len(x), min(...), max(...), abs(x)
- str(x), int(x), float(x), bool(x)

Variáveis disponíveis por padrão (contexto de processo, populado pelo engine
na fase 20a):
- dias_aberto (int)
- dias_na_unidade (int)
- numero_processo (str)
- id_assunto (int), id_tipo_processo (int)
- id_manifestante (int), id_unidade_atual (int), id_unidade_proprietaria (int)
- estado_anterior (str | None)
- qtd_anexos (int)
- externo (bool), publico (bool)

Em modo `test-expr` o usuário passa um dict de contexto livre — útil pra
provar uma expressão na UI antes de salvar o workflow.

Limites duros (defesa em camadas):
- Tamanho máximo da expressão: 500 chars (validado no schema Pydantic)
- Profundidade de AST: simpleeval default (50)
- Sem chamadas de função arbitrárias: `__call__` bloqueado
"""
from __future__ import annotations

from typing import Any

from simpleeval import (  # type: ignore[import-untyped]
    DEFAULT_FUNCTIONS,
    AttributeDoesNotExist,
    FeatureNotAvailable,
    InvalidExpression,
    NameNotDefined,
    NumberTooHigh,
    SimpleEval,
)


class WorkflowExprError(Exception):
    """Erro semântico de expressão (Pydantic já valida tamanho/regex)."""


# Funções extras permitidas (além das do DEFAULT_FUNCTIONS do simpleeval:
# int, float, str, bool, etc).
_EXTRA_FUNCTIONS: dict[str, Any] = {
    "len": len,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    # Funções convenientes pra workflow:
    "dias_entre": lambda a, b: max(0, (b - a).days) if a and b else 0,
}


def _new_evaluator(contexto: dict[str, Any]) -> SimpleEval:
    return SimpleEval(
        functions={**DEFAULT_FUNCTIONS, **_EXTRA_FUNCTIONS},
        names=contexto,
    )


def evaluate_expr(expressao: str, contexto: dict[str, Any]) -> Any:
    """Avalia expressão contra contexto. Lança WorkflowExprError em caso de
    erro semântico (variável inexistente, função proibida, AST muito profunda).
    """
    if not expressao or not expressao.strip():
        raise WorkflowExprError("Expressão vazia")
    if len(expressao) > 500:
        raise WorkflowExprError("Expressão excede 500 caracteres")

    evaluator = _new_evaluator(contexto)
    try:
        return evaluator.eval(expressao)
    except NameNotDefined as e:
        raise WorkflowExprError(f"Variável não permitida ou inexistente: {e}") from e
    except FeatureNotAvailable as e:
        raise WorkflowExprError(f"Operação não permitida: {e}") from e
    except AttributeDoesNotExist as e:
        raise WorkflowExprError(f"Atributo inválido: {e}") from e
    except NumberTooHigh as e:
        raise WorkflowExprError(f"Número fora do limite seguro: {e}") from e
    except InvalidExpression as e:
        raise WorkflowExprError(f"Expressão inválida: {e}") from e
    except SyntaxError as e:
        raise WorkflowExprError(f"Erro de sintaxe: {e}") from e
    except Exception as e:
        # Catch-all defensivo (simpleeval pode emitir outras subclasses)
        raise WorkflowExprError(
            f"Erro ao avaliar: {type(e).__name__}: {e}"
        ) from e


def validate_expr(expressao: str, contexto_keys: list[str]) -> str | None:
    """Valida sintaticamente que a expressão é avaliável com um contexto
    contendo as chaves dadas (valor arbitrário). Útil para validar workflows
    sem precisar de um processo real.

    Retorna None se OK, string com erro caso contrário.
    """
    # Atribui 0 a cada nome — só queremos detectar erro de parse/sintaxe ou
    # uso de função/atributo proibido.
    contexto_dummy = {k: 0 for k in contexto_keys}
    try:
        evaluate_expr(expressao, contexto_dummy)
        return None
    except WorkflowExprError as e:
        return str(e)


def transicoes_a_partir(
    dsl: dict[str, Any], estado: str, contexto: dict[str, Any]
) -> list[dict[str, Any]]:
    """Retorna a lista de transições saindo de `estado` que satisfazem
    suas condições no `contexto`. Usado pela engine (Fase 20a).

    Transições sem `condicao` (None ou vazia) são sempre incluídas.
    Erros em avaliação são silenciados e a transição é EXCLUÍDA — defesa
    em camadas contra DSLs maliciosos.
    """
    out: list[dict[str, Any]] = []
    for t in dsl.get("transicoes", []):
        if t.get("de") != estado:
            continue
        cond = t.get("condicao")
        if cond is None or not str(cond).strip():
            out.append(t)
            continue
        try:
            if bool(evaluate_expr(cond, contexto)):
                out.append(t)
        except WorkflowExprError:
            # Condição malformada: tratar como falsa (transição não disponível)
            continue
    return out

"""Guarda de ordem de declaração de rotas.

O FastAPI casa rotas na ordem em que foram declaradas. Uma rota de segmento
literal (`/vencidos`) declarada DEPOIS de uma paramétrica irmã (`/{alvara_id}`)
fica inalcançável: a paramétrica casa primeiro, a validação do tipo falha e a
resposta é 422 — sem nunca chegar no handler.

Esse defeito não aparece em teste de service, não aparece no type-check e não
aparece na leitura do arquivo: só aparece se alguém pedir a URL. Ele já ocorreu
TRÊS vezes neste repositório (vistorias/vencidas, alvaras/vencidos,
alvaras/relatorio). Esta guarda é a resposta a isso.
"""
from __future__ import annotations

import re

from app.main import app

# Rotas que sabidamente ficam à sombra de outra e cuja correção NÃO pertence a
# esta fatia. Entrada aqui é dívida registrada, não permissão: cada uma precisa
# de uma razão escrita ao lado. Lista vazia é o estado desejado.
SOMBREADAS_CONHECIDAS: set[tuple[str, str]] = set()


def _concretiza(caminho: str) -> str:
    """Troca cada `{param}` por `1` para obter uma URL concreta que a rota atende."""
    return re.sub(r"\{[^}]+\}", "1", caminho)


def rotas_sombreadas() -> set[tuple[str, str]]:
    """(método, caminho) de toda rota que outra, declarada antes, engole.

    `path_regex` é atributo interno do Starlette (não é API pública) — é o que
    permite testar "esta URL concreta casa com esta rota?" sem duplicar a
    lógica de matching do roteador. Se uma atualização do Starlette mudar essa
    semântica, é aqui que a guarda vai quebrar; quem depurar precisa saber que
    o apoio é num detalhe interno, não num contrato documentado.
    """
    rotas = [
        r for r in app.routes
        if getattr(r, "path_regex", None) is not None
        and getattr(r, "path", "").startswith("/api/v2")
    ]
    sombreadas: set[tuple[str, str]] = set()
    for rota in rotas:
        alvo = _concretiza(rota.path)
        for metodo in getattr(rota, "methods", set()):
            primeira = next(
                (
                    outra for outra in rotas
                    if metodo in getattr(outra, "methods", set())
                    and outra.path_regex.match(alvo)
                ),
                None,
            )
            # Identidade, não igualdade de `.path`: duas rotas DISTINTAS podem
            # ter o mesmo path literal e o mesmo método (ex.: decorador
            # duplicado por engano). Nesse caso `primeira.path == rota.path`
            # seria verdadeiro mesmo a segunda sendo outro objeto e genuinamente
            # inalcançável — comparar string mascararia exatamente o defeito que
            # esta guarda existe para achar. `primeira` vem de `next(...)` sobre
            # a mesma lista `rotas`, então é o mesmo objeto quando a rota casa
            # consigo própria; `is not` captura isso sem esse ponto cego.
            if primeira is not None and primeira is not rota:
                sombreadas.add((metodo, rota.path))
    return sombreadas


def test_nenhuma_rota_fica_a_sombra_de_outra():
    """Rota inalcançável é código morto que o CI reprova, não que produção descobre."""
    novas = rotas_sombreadas() - SOMBREADAS_CONHECIDAS
    assert not novas, (
        "Rotas inalcançáveis — outra declarada ANTES casa a mesma URL: "
        f"{sorted(novas)}. Mova a declaração de segmento literal para antes da "
        "paramétrica irmã, ou registre em SOMBREADAS_CONHECIDAS com a razão."
    )


def test_allowlist_nao_tem_entrada_obsoleta():
    """Allowlist que apodrece deixa de ser dívida registrada e vira ruído.

    Com `SOMBREADAS_CONHECIDAS` vazia este teste passa trivialmente — não há
    nada para comparar, então "passou" não significa "verificou alguma coisa".
    Ele só ganha poder de detecção real a partir do dia em que a allowlist
    tiver ao menos uma entrada.
    """
    obsoletas = SOMBREADAS_CONHECIDAS - rotas_sombreadas()
    assert not obsoletas, (
        f"Entradas obsoletas em SOMBREADAS_CONHECIDAS: {sorted(obsoletas)}. "
        "A rota foi consertada ou removida — tire-a da lista."
    )

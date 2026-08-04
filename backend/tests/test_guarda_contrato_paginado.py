"""Guarda do contrato `Paginated` entre backend e `frontend/lib/api.ts`.

O defeito que esta guarda trava custou **onze dias** no transporte regulado
(`628ca34`, 2026-07-20): 13 endpoints passaram a devolver `Paginated[...]` e o
`api.ts` continuou declarando array simples. Como `request<T>()` faz **cast sem
validar**, o tipo é uma afirmação sobre a resposta, não uma verificação dela:

- o `tsc` fica **verde**, porque ninguém checa o JSON;
- no navegador estoura `TypeError: ….map is not a function`;
- e onde o código faz `data?.length`, a tela diz **"nenhum registro"** com
  registros no banco — sem erro no console.

Nenhum teste de backend pega isso (o backend está certo) e nenhum teste de
frontend pega (o mock devolve o que o autor do teste acreditar). Só a
comparação entre os dois lados.

Registrado como pendência aberta no item 2.2 do backlog; esta é a opção (1) que
ele descreve.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from fastapi.routing import APIRoute

from app.main import app

API_TS = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "api.ts"
PREFIXO_API = "/api/v2"


def _exige_api_ts() -> None:
    """Pula fora do CI; **falha** dentro dele.

    O container local monta só `./backend:/app`, então `frontend/` não existe
    ali. O CI roda pytest no runner, com o repositório inteiro (`checkout@v4` +
    `working-directory: backend`), e lá o arquivo tem de estar.

    Sem esta assimetria explícita a guarda teria o pior comportamento possível:
    sumir em silêncio no único lugar onde ela é obrigatória. Para exercitá-la
    localmente:

        docker exec aprimora-py-backend mkdir -p /frontend/lib
        docker cp frontend/lib/api.ts aprimora-py-backend:/frontend/lib/api.ts
    """
    if API_TS.exists():
        return
    if os.getenv("CI"):
        pytest.fail(
            f"`{API_TS}` não encontrado COM CI=1. A guarda de contrato "
            "`Paginated` não pode ser pulada no CI — é o único lugar em que ela "
            "roda. Se a estrutura do repositório mudou, conserte o caminho."
        )
    pytest.skip(
        "frontend/lib/api.ts fora do alcance (container monta só ./backend). "
        "Esta guarda roda no CI; veja o docstring para exercitá-la aqui."
    )


def _normaliza(caminho: str) -> str:
    """Reduz rota a uma forma comparável entre backend e frontend.

    Backend: `/api/v2/transporte-regulado/alvaras/{alvara_id}/documentos`
    Frontend: `` `/transporte-regulado/alvaras/${alvaraId}/documentos` ``

    Ambos viram `/transporte-regulado/alvaras/{}/documentos`.
    """
    c = caminho.strip()
    if c.startswith(PREFIXO_API):
        c = c[len(PREFIXO_API) :]
    # `${qs(...)}` é query string, não caminho — sai inteiro.
    c = re.sub(r"\$\{qs\([^`]*?\)\}", "", c)
    # Qualquer outra interpolação é parâmetro de rota.
    c = re.sub(r"\$\{[^}]*\}", "{}", c)
    # Parâmetro nomeado do FastAPI vira o mesmo marcador.
    c = re.sub(r"\{[^}]*\}", "{}", c)
    return c.rstrip("/") or "/"


def _rotas_paginadas_do_backend() -> dict[str, str]:
    """`{caminho normalizado: nome do endpoint}` para GETs que devolvem Paginated."""
    achadas: dict[str, str] = {}
    for rota in app.routes:
        if not isinstance(rota, APIRoute) or "GET" not in rota.methods:
            continue
        modelo = getattr(rota, "response_model", None)
        # `Paginated[X]` é um genérico do Pydantic; o nome da origem é o que
        # identifica. Comparar por `__name__` cobre `Paginated[X]` e o alias
        # concreto que o Pydantic cria.
        origem = getattr(modelo, "__pydantic_generic_metadata__", {}).get("origin")
        nome = getattr(origem, "__name__", "") or getattr(modelo, "__name__", "")
        if nome == "Paginated":
            achadas[_normaliza(rota.path)] = rota.name
    return achadas


_METODO = re.compile(r'method:\s*"(?P<m>[A-Z]+)"')


def _chamadas_get_do_api_ts() -> dict[str, set[str]]:
    """`{caminho normalizado: {tipos declarados}}`, **só para GET**.

    Varredura por caractere, não regex, e o motivo é concreto: uma primeira
    versão usava `request<(?P<tipo>.+?)>\\(` com `re.S`, e o `.+?` atravessava
    linhas e comentários até achar um `>(` qualquer — porque `>` também fecha
    genérico aninhado (`Paginated<X>>`). O "tipo" capturado chegava a conter
    blocos inteiros do arquivo, e a guarda ficava verde por comparar lixo.

    Aqui o tipo é lido contando profundidade de `<`/`>`, e o caminho é o
    primeiro literal do argumento — crase ou aspas, porque as duas formas
    aparecem no `api.ts`.

    Filtrar por método não é preciosismo: `create` e `list` compartilham rota, e
    o POST devolve UM item enquanto o GET devolve o envelope. Sem isso a guarda
    acusava cinco falsos positivos. Guarda que grita sem motivo é desligada pela
    próxima pessoa. Ausência de `method:` significa GET, o default de
    `request()`.
    """
    fonte = API_TS.read_text(encoding="utf-8")
    marca = "request<"
    achados: list[tuple[str, str, int]] = []  # (tipo, caminho, fim)

    i = fonte.find(marca)
    while i != -1:
        j = i + len(marca)
        prof = 1
        while j < len(fonte) and prof:
            if fonte[j] == "<":
                prof += 1
            elif fonte[j] == ">":
                prof -= 1
            j += 1
        tipo = fonte[i + len(marca) : j - 1].strip()

        # Depois do genérico vem `(` e então o caminho.
        k = j
        while k < len(fonte) and fonte[k] in " \t\r\n":
            k += 1
        if k < len(fonte) and fonte[k] == "(":
            k += 1
            # Pula espaços e comentários de linha antes do literal.
            while k < len(fonte):
                if fonte[k] in " \t\r\n":
                    k += 1
                elif fonte.startswith("//", k):
                    k = fonte.find("\n", k)
                    if k == -1:
                        k = len(fonte)
                else:
                    break
            if k < len(fonte) and fonte[k] in "`\"'":
                aspa = fonte[k]
                fim = fonte.find(aspa, k + 1)
                if fim != -1:
                    achados.append((" ".join(tipo.split()), fonte[k + 1 : fim], fim))
        i = fonte.find(marca, j)

    porcaminho: dict[str, set[str]] = {}
    for idx, (tipo, caminho, fim) in enumerate(achados):
        # `${path}` é o helper genérico de CRUD, não uma rota concreta.
        if caminho.startswith("${path}"):
            continue
        limite = achados[idx + 1][2] if idx + 1 < len(achados) else len(fonte)
        met = _METODO.search(fonte, fim, limite)
        if met and met.group("m") != "GET":
            continue
        porcaminho.setdefault(_normaliza(caminho), set()).add(tipo)
    return porcaminho


def test_o_arquivo_do_frontend_foi_lido():
    """Controle. Sem isto, um caminho errado deixaria tudo abaixo verde vazio."""
    _exige_api_ts()
    chamadas = _chamadas_get_do_api_ts()
    assert len(chamadas) > 100, (
        f"só {len(chamadas)} chamadas extraídas de api.ts — a regex parou de "
        "casar e a guarda deixaria de medir qualquer coisa."
    )


def test_ha_endpoints_paginados_para_conferir():
    """Controle do outro lado: `Paginated` deixou de ser detectado?"""
    assert len(_rotas_paginadas_do_backend()) > 10


@pytest.mark.parametrize(
    "caminho,endpoint",
    sorted(_rotas_paginadas_do_backend().items()),
)
def test_endpoint_paginado_tem_contraparte_paginada_no_api_ts(caminho, endpoint):
    """Endpoint que devolve `Paginated` não pode ser tipado como array no cliente."""
    _exige_api_ts()
    chamadas = _chamadas_get_do_api_ts()
    tipos = chamadas.get(caminho)
    if tipos is None:
        pytest.skip(f"`{caminho}` não é consumido pelo frontend")

    erradas = {t for t in tipos if not t.startswith("Paginated<")}
    assert not erradas, (
        f"`{endpoint}` devolve `Paginated[...]`, mas `frontend/lib/api.ts` "
        f"declara {sorted(erradas)} para `{caminho}`.\n\n"
        "`request<T>()` faz CAST SEM VALIDAR: o `tsc` fica verde e o defeito "
        "aparece só no navegador — `TypeError: ….map is not a function`, ou "
        "pior, a tela dizendo 'nenhum registro' com registros no banco (onde o "
        "código faz `data?.length`).\n"
        f"Correção: `request<Paginated<X>>` e a tela consumindo `.items`. NÃO "
        "desembrulhe dentro do api.ts — o tipo honesto é o que faz o tsc "
        "reprovar a próxima ocorrência."
    )


def test_nenhum_cliente_espera_paginado_de_endpoint_que_nao_pagina():
    """A divergência inversa: `api.ts` promete envelope que o backend não manda.

    Sintoma oposto e igualmente silencioso — a tela lê `.items` de um array e
    recebe `undefined`, exibindo vazio.
    """
    _exige_api_ts()
    paginadas = set(_rotas_paginadas_do_backend())
    # Rotas GET conhecidas do backend, para não acusar caminho que o teste
    # simplesmente não sabe resolver (montagem dinâmica, proxy, etc.).
    todas_get = {
        _normaliza(r.path)
        for r in app.routes
        if isinstance(r, APIRoute) and "GET" in r.methods
    }

    suspeitas = []
    for caminho, tipos in _chamadas_get_do_api_ts().items():
        if caminho not in todas_get or caminho in paginadas:
            continue
        if any(t.startswith("Paginated<") for t in tipos):
            suspeitas.append(caminho)

    assert not suspeitas, (
        "o `api.ts` declara `Paginated<...>` para rota que o backend NÃO "
        f"pagina: {sorted(suspeitas)}. A tela vai ler `.items` de um array e "
        "receber `undefined` — vazio silencioso."
    )

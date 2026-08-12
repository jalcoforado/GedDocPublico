"""Cliente DeepSeek e a escolha de provedor (2026-08-12).

Nenhum teste aqui toca a rede: o `httpx.AsyncClient` é substituído por um
`MockTransport`, que responde o fluxo SSE que a API de verdade responderia. É
a única forma de testar um parser de streaming sem chave e sem gastar — e o
parser é justamente onde o defeito mora, porque pedaço de rede não é evento.
"""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import get_settings
from app.services.ia import llm_client as mod
from app.services.ia.llm_client import (
    AnthropicClient,
    DeepSeekClient,
    IAIndisponivelError,
    obter_cliente,
)


def _sse(*eventos: dict | str) -> bytes:
    partes = []
    for e in eventos:
        dados = e if isinstance(e, str) else json.dumps(e)
        partes.append(f"data: {dados}\n\n")
    return "".join(partes).encode("utf-8")


def _delta(texto: str) -> dict:
    return {"choices": [{"delta": {"content": texto}}]}


def _cliente_com(resposta: httpx.Response, monkeypatch, capturar: list | None = None):
    """Instala um transporte falso e devolve um `DeepSeekClient` pronto."""
    def _handler(request: httpx.Request) -> httpx.Response:
        if capturar is not None:
            capturar.append(request)
        return resposta

    original = httpx.AsyncClient

    def _fake(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _fake)
    return DeepSeekClient(api_key="sk-teste", base_url="https://exemplo.invalido")


@pytest.mark.asyncio
async def test_junta_os_pedacos_na_ordem(monkeypatch) -> None:
    resposta = httpx.Response(
        200,
        content=_sse(_delta("Bom "), _delta("dia"), _delta("."), "[DONE]"),
        headers={"content-type": "text/event-stream"},
    )
    cliente = _cliente_com(resposta, monkeypatch)
    pedacos = [p async for p in cliente.stream(system="s", pergunta="p")]
    assert "".join(pedacos) == "Bom dia."


@pytest.mark.asyncio
async def test_ignora_evento_sem_content(monkeypatch) -> None:
    """O PRIMEIRO evento de um fluxo OpenAI-compatível traz só `role`.

    Indexar `delta["content"]` estouraria `KeyError` logo no primeiro pedaço —
    ou seja, o assistente falharia em 100% das perguntas. É o defeito mais
    provável deste parser, e o mais silencioso de escrever.
    """
    resposta = httpx.Response(
        200,
        content=_sse(
            {"choices": [{"delta": {"role": "assistant"}}]},
            {"choices": []},                       # evento de keep-alive
            "ruído que não é JSON",
            _delta("ok"),
            {"choices": [{"delta": {"content": None}}]},
            "[DONE]",
        ),
        headers={"content-type": "text/event-stream"},
    )
    cliente = _cliente_com(resposta, monkeypatch)
    pedacos = [p async for p in cliente.stream(system="s", pergunta="p")]
    assert pedacos == ["ok"]


@pytest.mark.asyncio
async def test_para_no_done_e_nao_entrega_o_que_vem_depois(monkeypatch) -> None:
    resposta = httpx.Response(
        200,
        content=_sse(_delta("antes"), "[DONE]", _delta("DEPOIS")),
        headers={"content-type": "text/event-stream"},
    )
    cliente = _cliente_com(resposta, monkeypatch)
    pedacos = [p async for p in cliente.stream(system="s", pergunta="p")]
    assert pedacos == ["antes"]


@pytest.mark.asyncio
async def test_erro_http_vira_indisponivel_com_o_corpo(monkeypatch) -> None:
    """401 de chave errada tem de dizer o que a API respondeu.

    Sem ler o corpo, o operador recebe "DeepSeek respondeu 401" e não sabe se
    é chave inválida, cota estourada ou modelo inexistente — três causas com
    ações diferentes.
    """
    resposta = httpx.Response(401, json={"error": {"message": "Invalid API key"}})
    cliente = _cliente_com(resposta, monkeypatch)
    with pytest.raises(IAIndisponivelError) as exc:
        [p async for p in cliente.stream(system="s", pergunta="p")]
    assert "401" in str(exc.value)
    assert "Invalid API key" in str(exc.value)


@pytest.mark.asyncio
async def test_manda_system_e_pergunta_separados(monkeypatch) -> None:
    """O system prompt carrega as REGRAS e o contexto do processo; a pergunta
    é texto de usuário. Fundir os dois num só `content` apagaria a fronteira
    que impede a pergunta de reescrever as regras."""
    capturadas: list[httpx.Request] = []
    resposta = httpx.Response(
        200, content=_sse(_delta("x"), "[DONE]"),
        headers={"content-type": "text/event-stream"},
    )
    cliente = _cliente_com(resposta, monkeypatch, capturar=capturadas)
    [p async for p in cliente.stream(system="REGRAS", pergunta="onde está?")]

    corpo = json.loads(capturadas[0].content)
    assert corpo["messages"] == [
        {"role": "system", "content": "REGRAS"},
        {"role": "user", "content": "onde está?"},
    ]
    assert corpo["stream"] is True
    assert capturadas[0].headers["authorization"] == "Bearer sk-teste"


def _config(monkeypatch, *, deepseek: str, anthropic: str) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", deepseek)
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic)


def test_sem_chave_nenhuma_continua_503(monkeypatch) -> None:
    _config(monkeypatch, deepseek="", anthropic="")
    with pytest.raises(IAIndisponivelError):
        obter_cliente()
    get_settings.cache_clear()


def test_deepseek_tem_precedencia_sobre_anthropic(monkeypatch) -> None:
    """A ordem é a decisão, e é o que evita conta chegando do lado errado."""
    _config(monkeypatch, deepseek="sk-ds", anthropic="sk-ant")
    assert isinstance(obter_cliente(), DeepSeekClient)
    get_settings.cache_clear()


def test_so_anthropic_configurada_usa_anthropic(monkeypatch) -> None:
    """O par do teste acima: sem ele, `obter_cliente` poderia devolver
    DeepSeek SEMPRE e a precedência passaria verde sem significar nada."""
    _config(monkeypatch, deepseek="", anthropic="sk-ant")
    assert isinstance(obter_cliente(), AnthropicClient)
    get_settings.cache_clear()


def test_modelo_e_base_url_vem_da_config(monkeypatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds")
    monkeypatch.setenv("DEEPSEEK_MODELO", "deepseek-reasoner")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://proxy.interno/v1/")
    cliente = obter_cliente()
    assert isinstance(cliente, DeepSeekClient)
    assert cliente._modelo == "deepseek-reasoner"
    # A barra final some: `f"{base}/chat/completions"` com barra dupla é 404
    # em boa parte dos gateways.
    assert cliente._base_url == "https://proxy.interno/v1"
    get_settings.cache_clear()


def test_o_teto_de_saida_e_o_mesmo_dos_dois_provedores() -> None:
    """`MAX_TOKENS` é limite de custo, e limite de custo que vale só para um
    provedor não é limite."""
    assert mod.MAX_TOKENS == 2048

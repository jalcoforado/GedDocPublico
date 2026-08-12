"""Cliente de LLM — interface fina + implementação Anthropic.

A interface existe para duas razões concretas, e nenhuma delas é "trocar de
provedor um dia":

1. **A suíte não pode tocar a rede.** Todo teste injeta `LLMClientDublê`. Sem a
   interface, testar o assistente exigiria chave, rede e o pacote instalado — e
   um teste que depende disso é um teste que a CI não roda de verdade.
2. **O `import anthropic` é LAZY, dentro do método.** Nada no boot da aplicação
   depende do SDK. Um ambiente sem o pacote sobe normalmente; só quem chamar o
   assistente recebe erro, e recebe um erro claro.

Modelo: `claude-opus-5`. A escolha não é por capacidade bruta — é porque a
propriedade que mais importa aqui é **recusar quando não sabe**. Resposta
inventada sobre andamento de processo é inaceitável num sistema de governo, e
vale mais um "não está no processo" do que uma frase plausível.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol

from ...config import get_settings

MODELO_PADRAO = "claude-opus-5"

# Teto de saída. Resposta sobre andamento de processo é curta por natureza; o
# teto existe para limitar custo de uma pergunta patológica, não para moldar o
# tamanho da resposta (isso é trabalho do prompt).
MAX_TOKENS = 2048


class IAIndisponivelError(Exception):
    """Sem credencial configurada — o chamador devolve 503, não 500.

    Distinção que importa: 500 diria "o sistema quebrou"; 503 diz "esta função
    não está ligada neste ambiente", que é a verdade. `ANTHROPIC_API_KEY` não
    está definida em nenhum ambiente hoje, então este é o caminho NORMAL até
    alguém configurá-la — e o resto do sistema não pode nem notar.
    """


class LLMClient(Protocol):
    """Contrato mínimo: recebe system + pergunta, devolve texto em pedaços."""

    async def stream(self, *, system: str, pergunta: str) -> AsyncIterator[str]:
        ...


class AnthropicClient:
    """Implementação real. Só é construída quando há chave."""

    def __init__(self, *, api_key: str, modelo: str = MODELO_PADRAO) -> None:
        self._api_key = api_key
        self._modelo = modelo

    async def stream(self, *, system: str, pergunta: str) -> AsyncIterator[str]:
        # Import aqui dentro, não no topo: ver docstring do módulo.
        from anthropic import AsyncAnthropic

        cliente = AsyncAnthropic(api_key=self._api_key)
        async with cliente.messages.stream(
            model=self._modelo,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": pergunta}],
        ) as fluxo:
            async for pedaco in fluxo.text_stream:
                yield pedaco


def obter_cliente() -> LLMClient:
    """Devolve o cliente configurado, ou levanta `IAIndisponivelError`.

    Chame isto no início do handler, ANTES de resolver qualquer recurso: sem
    chave não há motivo para consultar o banco.
    """
    chave = (get_settings().anthropic_api_key or "").strip()
    if not chave:
        raise IAIndisponivelError(
            "O assistente não está configurado neste ambiente "
            "(ANTHROPIC_API_KEY ausente)."
        )
    return AnthropicClient(api_key=chave)

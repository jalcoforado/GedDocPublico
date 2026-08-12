"""Cliente de LLM — interface fina + implementações DeepSeek e Anthropic.

A interface nasceu (2026-08-07) por duas razões concretas, e "trocar de
provedor um dia" estava escrito aqui como o que ela NÃO pretendia resolver.
Cinco dias depois trocamos de provedor, e o custo foi uma classe nova — o
assistente, o contexto e o roteador não foram tocados. Fica como está: as duas
razões abaixo continuam sendo as que sustentam a interface, e a portabilidade
foi um efeito colateral, não o projeto.

1. **A suíte não pode tocar a rede.** Todo teste injeta `LLMClientDublê`. Sem a
   interface, testar o assistente exigiria chave, rede e o pacote instalado — e
   um teste que depende disso é um teste que a CI não roda de verdade.
2. **O `import anthropic` é LAZY, dentro do método.** Nada no boot da aplicação
   depende do SDK. Um ambiente sem o pacote sobe normalmente; só quem chamar o
   assistente recebe erro, e recebe um erro claro.

Provedor em uso: **DeepSeek** (`deepseek-chat`), por decisão de custo do Jorge
em 2026-08-12; a Anthropic (`claude-opus-5`) fica como segunda opção, usada
quando só a chave dela está configurada.

A propriedade que mais importa aqui não é capacidade bruta: é **recusar quando
não sabe**. Resposta inventada sobre andamento de processo é inaceitável num
sistema de governo, e vale mais um "não está no processo" do que uma frase
plausível. Isso é trabalho do prompt (`conhecimento.py`, regra 2), não do
modelo — mas modelos diferentes obedecem de formas diferentes, e essa é a
primeira coisa a reavaliar ao trocar de provedor de novo.
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


class DeepSeekClient:
    """Implementação DeepSeek, pela API compatível com o formato OpenAI.

    Por que `httpx` cru e não o SDK `openai`: `httpx` já é dependência deste
    backend, e o que precisamos daqui é uma requisição e um parser de SSE. Um
    pacote novo no `requirements.txt` para isso custaria mais do que resolve —
    e o `import` continua LAZY, dentro do método, pela mesma razão que o da
    Anthropic (ver docstring do módulo).

    O formato do fluxo é `text/event-stream`: linhas `data: {json}`, cada uma
    com o pedaço em `choices[0].delta.content`, terminando em `data: [DONE]`.
    Duas armadilhas tratadas abaixo, ambas de SSE e nenhuma de DeepSeek:
    **pedaço de rede não é evento** (uma linha pode chegar partida), por isso
    `aiter_lines`; e `delta` pode vir SEM `content` (o primeiro evento traz só
    `role`), por isso o `.get` em vez de indexação.
    """

    def __init__(
        self,
        *,
        api_key: str,
        modelo: str | None = None,
        base_url: str | None = None,
    ) -> None:
        cfg = get_settings()
        self._api_key = api_key
        self._modelo = modelo or cfg.deepseek_modelo
        self._base_url = (base_url or cfg.deepseek_base_url).rstrip("/")

    async def stream(self, *, system: str, pergunta: str) -> AsyncIterator[str]:
        import json

        import httpx

        corpo = {
            "model": self._modelo,
            "max_tokens": MAX_TOKENS,
            "stream": True,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": pergunta},
            ],
        }
        # Timeout explícito: o default do httpx é 5s, que um fluxo de LLM
        # estoura com facilidade. `read` alto porque o tempo entre pedaços é
        # que importa; `connect` curto porque falha de conexão tem de aparecer
        # rápido.
        limites = httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=limites) as cliente:
            async with cliente.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=corpo,
            ) as resposta:
                if resposta.status_code != 200:
                    # `aread()` porque o corpo de um stream não foi lido ainda;
                    # sem isso a mensagem de erro sai vazia e o operador fica
                    # sem saber se é chave, cota ou modelo.
                    detalhe = (await resposta.aread()).decode("utf-8", "replace")
                    raise IAIndisponivelError(
                        f"DeepSeek respondeu {resposta.status_code}: {detalhe[:300]}"
                    )
                async for linha in resposta.aiter_lines():
                    if not linha.startswith("data:"):
                        continue
                    dados = linha[len("data:"):].strip()
                    if dados == "[DONE]":
                        return
                    try:
                        evento = json.loads(dados)
                    except json.JSONDecodeError:
                        continue
                    escolhas = evento.get("choices") or []
                    if not escolhas:
                        continue
                    pedaco = (escolhas[0].get("delta") or {}).get("content")
                    if pedaco:
                        yield pedaco


def obter_cliente() -> LLMClient:
    """Devolve o cliente configurado, ou levanta `IAIndisponivelError`.

    Chame isto no início do handler, ANTES de resolver qualquer recurso: sem
    chave não há motivo para consultar o banco.

    **DeepSeek tem precedência** quando as duas chaves estão configuradas.
    Decisão do Jorge (2026-08-12), por custo. A ordem é explícita, e não
    "a primeira que eu achar": ambiente com as duas chaves precisa de resposta
    previsível, senão a escolha do provedor passa a depender de ordem de
    leitura de variável — e o sintoma seria conta chegando do lado errado.
    """
    cfg = get_settings()
    chave_deepseek = (cfg.deepseek_api_key or "").strip()
    if chave_deepseek:
        return DeepSeekClient(api_key=chave_deepseek)

    chave_anthropic = (cfg.anthropic_api_key or "").strip()
    if chave_anthropic:
        return AnthropicClient(api_key=chave_anthropic)

    raise IAIndisponivelError(
        "O assistente não está configurado neste ambiente "
        "(DEEPSEEK_API_KEY e ANTHROPIC_API_KEY ausentes)."
    )

"""A chave do LLM não pode ganhar passthrough vazio no compose.

Esta guarda protege uma decisão que parece o contrário de uma boa prática, e
por isso é forte candidata a ser "corrigida" por quem chegar depois: a chave do
provedor de IA é o único segredo do projeto que NÃO está em
`docker-compose.yml`. Todos os outros estão — `DADOS_SENSIVEIS_ENCRYPTION_KEY`
inclusive, com `:?` para abortar o boot.

**Por que aqui é diferente.** Em `pydantic-settings`, variável de ambiente
vence arquivo `.env`, e "definida como string vazia" conta como definida. O
padrão `${VAR:-}` do compose define a variável **sempre** — com o valor da raiz
quando existe, e com string vazia quando não. Logo, acrescentar

    DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}

entrega `""` a todo ambiente que não a tenha no `.env` da raiz, e a string
vazia **sobrepõe** o `backend/.env` onde a chave de fato vive. Medido em
2026-08-12, no container de dev: com a env vazia definida, `get_settings()`
devolveu `''`; sem ela, devolveu a chave.

O efeito seria desligar o assistente onde ele funciona — e desligar em
silêncio, porque a ausência de chave é um caminho PROJETADO (503 no endpoint, o
painel some da tela). Não há erro, não há log de alerta: a funcionalidade
simplesmente deixa de existir para o usuário.

Se um dia a fiação tiver de ir para o compose, o caminho é a forma de LISTA
(`- DEEPSEEK_API_KEY`, sem valor), que repassa a variável **só quando ela está
definida** no ambiente. Aí esta guarda muda junto, com a razão reescrita.
"""
from __future__ import annotations

import pathlib
import re

import pytest

CHAVES_DE_IA = ("DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY")


def _raiz_do_repo() -> pathlib.Path | None:
    """Sobe até achar o `docker-compose.yml`, ou devolve None.

    None é o caso NORMAL dentro do container: o compose monta só `./backend`
    como `/app`, então a raiz do repositório não existe ali. Os testes abaixo
    então PULAM, e o skip diz por quê — um `assert` que passasse por não achar
    o arquivo seria pior do que não existir, porque leria como aprovação.

    Onde isto de fato enforça é no CI, que roda sobre o checkout inteiro
    (`.github/workflows/backend-tests.yml`, `working-directory: backend`).
    """
    for pasta in pathlib.Path(__file__).resolve().parents:
        if (pasta / "docker-compose.yml").is_file():
            return pasta
    return None


RAIZ = _raiz_do_repo()
_SEM_RAIZ = pytest.mark.skipif(
    RAIZ is None,
    reason=(
        "raiz do repositório não visível — dentro do container só `./backend` "
        "é montado. Esta guarda roda no CI, sobre o checkout completo."
    ),
)


def _linhas_de_codigo(texto: str) -> list[str]:
    """Descarta comentário: o compose FALA dessas chaves de propósito, para
    explicar por que elas não estão lá. Uma varredura por substring crua
    reprovaria exatamente a documentação que a decisão exige — e guarda que
    grita no caso legítimo é guarda que alguém desliga."""
    saida = []
    for linha in texto.splitlines():
        sem_comentario = linha.split("#", 1)[0]
        if sem_comentario.strip():
            saida.append(sem_comentario)
    return saida


@_SEM_RAIZ
@pytest.mark.parametrize("chave", CHAVES_DE_IA)
def test_compose_nao_define_a_chave_de_ia(chave: str) -> None:
    codigo = _linhas_de_codigo((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
    ofensoras = [ln for ln in codigo if chave in ln]
    assert not ofensoras, (
        f"{chave} apareceu em docker-compose.yml: {ofensoras}. "
        "Com `${VAR:-}` isso entrega string vazia a todo ambiente que não a "
        "defina na raiz, e a string vazia VENCE o backend/.env — o assistente "
        "desliga em silêncio. Leia o docstring deste arquivo antes de mudar."
    )


def test_o_padrao_perigoso_e_reconhecido_pela_guarda() -> None:
    """Inversão: a varredura precisa PEGAR o passthrough se ele existir.

    Sem este teste, `_linhas_de_codigo` poderia estar devolvendo lista vazia
    por defeito próprio — um `split` trocado, um `strip` a mais — e o teste
    acima passaria para sempre sem olhar nada.
    """
    falso_compose = (
        "x-backend-env: &backend-env\n"
        "  # comentario citando DEEPSEEK_API_KEY, que nao deve reprovar\n"
        "  DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}\n"
    )
    linhas = _linhas_de_codigo(falso_compose)
    assert any("DEEPSEEK_API_KEY" in ln for ln in linhas)
    assert not any(ln.strip().startswith("#") for ln in linhas)


@_SEM_RAIZ
def test_a_fiacao_esta_documentada_onde_alguem_procura() -> None:
    """O problema que esta fatia resolve é DESCOBERTA, não funcionamento.

    A chave vive num arquivo que não existe no repositório (`backend/.env`),
    criado à mão em cada ambiente. Quem for montar o próximo não tem como
    adivinhar isso lendo o código — e foi assim que a VPS ficou com o
    assistente ligado por um caminho que nenhum documento mencionava.
    """
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    assert "backend/.env" in texto, (
        ".env.example precisa dizer ONDE a chave do LLM mora — é o primeiro "
        "arquivo que alguém abre ao montar um ambiente."
    )
    assert re.search(r"DEEPSEEK_API_KEY", texto), (
        ".env.example precisa nomear a variável, senão não é encontrável por busca."
    )

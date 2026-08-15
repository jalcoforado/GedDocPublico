"""Guarda do classificador de `app.cli.limpar_tenants_de_teste`.

`eh_tenant_de_teste` é a única coisa entre o comando e um `DELETE` em tenant de
verdade. É função pura de propósito: dá para exercitar o caso perigoso — um slug
municipal real — sem precisar de um tenant municipal real no banco.

O risco que estes testes cobrem não é o falso negativo (deixar lixo, que só
custa espaço) e sim o **falso positivo**: classificar como teste um tenant que
não é. Por isso a maior parte da tabela é de nomes que NÃO podem casar.
"""
from __future__ import annotations

import pytest

from app.cli.limpar_tenants_de_teste import SLUGS_RESERVADOS, eh_tenant_de_teste

# Slugs realmente encontrados no dev local em 2026-08-14, um por prefixo dos
# mais numerosos. Não são inventados: é a amostra que motivou o item 1.1.6.
VAZADOS_REAIS = [
    "p52-fbcfd1f1",
    "p51-fec2f27d",
    "vis47e4010d",
    "alv29081774",
    "alvdoc34ac50b1",
    "alvrespc8adba6a",
    "alvren8d2d71ac",
    "exc12-7c6dfe95",
    "gdocs-63be6a78",
    "ia1-4b1d31a2",
    "md5-234a8bd8",
    "test-rls-a-1b2c3d4e",
    "e2e-0a1b2c3d",
    "sec1-deadbeef",
]


@pytest.mark.parametrize("slug", VAZADOS_REAIS)
def test_reconhece_os_vazados_reais(slug: str) -> None:
    assert eh_tenant_de_teste(slug), slug


# O que NUNCA pode ser apagado. Cada linha é um jeito diferente de um nome de
# município se parecer com lixo de teste.
NAO_SAO_TESTE = [
    "sobral",
    "default",
    "demo",
    "fortaleza",
    "sao-goncalo-do-amarante",
    "juazeiro-do-norte",
    # Comprimento suficiente (9+), rejeitado pelo HEXADECIMAL: os 8 últimos de
    # "fortaleza" são "ortaleza", e `o`/`r`/`t`/`l`/`z` não são hex. É este o
    # caso que uma regex de "termina em 8 caracteres" pegaria por engano.
    "fortaleza",
    "cascavel1",
    # Rejeitados pelo COMPRIMENTO: 8 no total, sem sobrar prefixo.
    "sobrinho",
    "0a1b2c3d",
]


@pytest.mark.parametrize("slug", NAO_SAO_TESTE)
def test_nao_toca_no_que_nao_e_teste(slug: str) -> None:
    assert not eh_tenant_de_teste(slug), slug


def test_as_duas_rejeicoes_sao_por_motivos_diferentes() -> None:
    """Controle: a tabela acima cobre hexadecimal E comprimento, não só um.

    Sem isto, alguém poderia trocar o `{8}` por `{12}` e a tabela inteira
    continuaria verde — todos os nomes municipais são rejeitados por comprimento
    ou por caractere, e nenhum teste distinguiria os dois motivos.
    """
    # Comprimento OK, hex falha.
    assert len("fortaleza") > 8 and not eh_tenant_de_teste("fortaleza")
    # Hex OK, comprimento falha (não sobra prefixo).
    assert len("0a1b2c3d") == 8 and not eh_tenant_de_teste("0a1b2c3d")
    # Os dois OK — passa.
    assert eh_tenant_de_teste("x0a1b2c3d")


def test_reservado_vence_o_padrao() -> None:
    """Mesmo que um reservado passasse a casar o padrão, ele não entra.

    Controle: sem esta precedência, bastaria alguém renomear um tenant real para
    algo terminado em 8 hexadecimais para ele virar alvo.
    """
    for reservado in SLUGS_RESERVADOS:
        assert not eh_tenant_de_teste(reservado)
    # E o padrão sozinho de fato casaria com um nome assim:
    assert eh_tenant_de_teste("qualquer-deadbeef")


def test_o_padrao_exige_um_prefixo() -> None:
    """Só o sufixo hexadecimal não basta — senão `12345678` seria alvo."""
    assert not eh_tenant_de_teste("deadbeef")
    assert eh_tenant_de_teste("x-deadbeef")

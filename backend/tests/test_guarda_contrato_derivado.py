"""Guarda: valor e vigência ORIGINAIS do contrato não são reescritos por ato.

Contratos G1 (spec docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md,
§2 e §8). `pagamentos.contrato.valor_total`, `vigencia_inicio` e `vigencia_fim`
são os originais, congelados na assinatura. Valor atualizado e vigência atual
são DERIVADOS dos aditivos e apostilas por `services.contratos.calcular`.

O defeito que esta guarda impede é silencioso e parece conserto: alguém, vendo
que "o contrato foi aditivado e a coluna continua com o valor velho", faz o
aditivo dar UPDATE na coluna. A tela passa a mostrar o número certo, o
percentual aditivado some (a base mudou), e a remessa do SIM — que quer o valor
do aditivo separado do original — sai errada sem erro nenhum.

Duas varreduras de texto e um controle. São varreduras, não prova: pegam a
forma óbvia do erro. A prova de comportamento é
`test_contratos_servico.py::test_aditivo_nao_altera_as_colunas_do_contrato`.

LIMITE CONHECIDO: `setattr(obj, nome, valor)` com `nome` dinâmico não é
detectável por texto. Os dois únicos pontos que fazem isso com um `Contrato`
são os listados em `ESCRITORES_PERMITIDOS`.
"""
from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"

# Quem pode gravar as três colunas, e por quê:
ESCRITORES_PERMITIDOS = {
    # Dono da regra: cria o contrato e o edita enquanto é RASCUNHO.
    "services/contratos.py",
    # Cadastro simples de pagamentos, para município SEM o módulo `contratos`.
    # Com o módulo contratado, o router recusa a escrita com 409 (spec §5.2).
    "services/pagamentos_cadastros.py",
}

COLUNAS = "valor_total|vigencia_inicio|vigencia_fim"

# `contrato.valor_total = ...` (atribuição, não comparação) e UPDATE em massa.
ATRIBUICAO = re.compile(rf"\bcontrato\w*\.({COLUNAS})\s*=(?!=)")
UPDATE_EM_MASSA = re.compile(r"\bupdate\(\s*Contrato\s*\)|UPDATE\s+pagamentos\.contrato\b", re.I)

MARCO_ADITIVO = "# ============================ aditivo"


def _arquivos():
    arquivos = sorted(APP.rglob("*.py"))
    assert len(arquivos) > 100, f"só {len(arquivos)} arquivos — o glob quebrou"
    return arquivos


def _ocorrencias(padrao: re.Pattern[str]) -> list[str]:
    achados = []
    for arquivo in _arquivos():
        relativo = arquivo.relative_to(APP).as_posix()
        if relativo in ESCRITORES_PERMITIDOS:
            continue
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            if padrao.search(linha):
                achados.append(f"{relativo}:{n}: {linha.strip()}")
    return achados


def test_ninguem_fora_dos_donos_atribui_valor_ou_vigencia_do_contrato():
    achados = _ocorrencias(ATRIBUICAO)
    assert not achados, (
        "Escrita direta em valor/vigência ORIGINAIS do contrato fora dos donos:\n  "
        + "\n  ".join(achados)
        + "\nValor atualizado e vigência atual são derivados "
        "(services.contratos.calcular). Registre um aditivo ou uma apostila."
    )


def test_ninguem_fora_dos_donos_faz_update_em_massa_no_contrato():
    achados = _ocorrencias(UPDATE_EM_MASSA)
    assert not achados, (
        "UPDATE em massa em pagamentos.contrato fora dos donos:\n  " + "\n  ".join(achados)
    )


def test_o_codigo_de_aditivo_e_apostila_nao_toca_o_contrato():
    """Dentro do próprio dono, a metade que registra ATOS não pode escrever no
    contrato: nem atribuição direta, nem `setattr(c, ...)`.

    É a varredura que cobre o limite da anterior — o `setattr` dinâmico só é
    legítimo em `atualizar`, que fica ANTES do marco.
    """
    fonte = (APP / "services" / "contratos.py").read_text(encoding="utf-8")
    assert fonte.count(MARCO_ADITIVO) == 1, (
        "O marco da seção de aditivos sumiu ou duplicou em services/contratos.py; "
        "esta guarda depende dele para saber onde começa o código de atos."
    )
    atos = fonte.split(MARCO_ADITIVO, 1)[1]
    assert "async def assinar_aditivo" in atos and "async def criar_apostila" in atos, (
        "A seção depois do marco não contém mais as funções de ato — a guarda "
        "estaria varrendo o trecho errado e passaria por vacuidade."
    )
    proibidos = [
        linha.strip() for linha in atos.splitlines()
        if re.search(rf"\bc\.({COLUNAS}|situacao|exercicio)\s*=(?!=)", linha)
        or re.search(r"\bsetattr\(\s*c\s*,", linha)
    ]
    assert not proibidos, (
        "O código de aditivo/apostila está escrevendo no contrato:\n  "
        + "\n  ".join(proibidos)
    )


def test_a_guarda_enxerga_o_que_diz_enxergar():
    """Controle contra verde por vacuidade: as expressões têm de casar com a
    forma real do erro e NÃO casar com leitura ou comparação."""
    erros = (
        "contrato.valor_total = novo",
        "    contrato.vigencia_fim = aditivo.nova_vigencia_fim",
        "contrato_atual.vigencia_inicio=data",
    )
    inocentes = (
        "if contrato.valor_total == total:",
        "saldo = contrato.valor_total - pago",
        "debito.valor_total = soma",
        "assert contrato.vigencia_fim >= hoje",
    )
    for linha in erros:
        assert ATRIBUICAO.search(linha), f"a guarda NÃO pegou: {linha!r}"
    for linha in inocentes:
        assert not ATRIBUICAO.search(linha), f"falso-positivo: {linha!r}"

    assert UPDATE_EM_MASSA.search("await db.execute(update(Contrato).values(valor_total=1))")
    assert UPDATE_EM_MASSA.search('text("UPDATE pagamentos.contrato SET valor_total = 0")')
    assert not UPDATE_EM_MASSA.search("UPDATE pagamentos.contrato_aditivo SET situacao = 'X'")
    assert not UPDATE_EM_MASSA.search("select(Contrato).where(Contrato.id == 1)")

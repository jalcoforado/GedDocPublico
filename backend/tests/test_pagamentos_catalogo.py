"""Catálogo de indicadores (fatia 7, §12 do brief).

O catálogo é domínio puro — não toca banco — então o que vale testar é o
CONTRATO dele:

- Ficha incompleta não serve. Indicador sem fórmula, sem fonte ou sem
  "não confundir com" devolve ao leitor a dúvida que o catálogo existe para
  tirar.
- Os conceitos que o §12 manda distinguir precisam estar TODOS lá, inclusive
  os que o sistema não tem. Omitir "disponibilidade orçamentária" faria o
  leitor concluir que foi esquecida; a ficha dizendo "não existe, porque não há
  dotação cadastrada" é informação.
- O que não existe tem de estar marcado como não existindo. Uma ficha
  indisponível apresentada como disponível seria pior que a omissão: viraria
  promessa.
"""
from __future__ import annotations

import pytest

from app.services import pagamentos_catalogo as cat


def test_toda_ficha_esta_completa():
    for i in cat.listar():
        assert i.codigo and i.nome and i.grupo, i.codigo
        assert len(i.definicao) > 20, f"{i.codigo}: definição curta demais para definir algo"
        assert i.fonte.strip(), f"{i.codigo}: sem fonte — número que ninguém confere"
        assert i.restricoes.strip(), f"{i.codigo}: sem restrições — todo indicador tem limite"
        assert i.nao_confundir.strip(), (
            f"{i.codigo}: sem 'não confundir com' — é o campo que evita a discussão")


def test_indicador_disponivel_tem_formula_e_granularidade():
    """Se o sistema calcula, o catálogo tem de dizer COMO."""
    for i in cat.listar():
        if not i.disponivel:
            continue
        assert i.formula != "—", f"{i.codigo}: disponível mas sem fórmula"
        assert i.granularidade != "—", f"{i.codigo}: disponível mas sem granularidade"
        assert i.periodicidade != "—", f"{i.codigo}: disponível mas sem periodicidade"


# Os conceitos que o §12 manda diferenciar, com o que esperamos do sistema hoje.
_ESPERADO = {
    "saldo_bancario": True,
    "saldo_conciliado": True,
    "saldo_bloqueado": True,
    "saldo_contabil": False,
    "disponibilidade_financeira": True,
    "disponibilidade_orcamentaria": True,
    "recursos_vinculados": True,
    "comprometido": True,
    "restos_a_pagar": False,
    "solicitacao": True,
    "autorizacao": True,
    "reserva_orcamentaria": False,
    "empenho": True,
    "liquidacao": True,
    "ordem_pagamento": True,
    "pagamento": True,
}


def test_cobre_os_conceitos_que_o_brief_manda_distinguir():
    codigos = {i.codigo for i in cat.listar()}
    faltando = set(_ESPERADO) - codigos
    assert not faltando, f"conceitos do §12 fora do catálogo: {sorted(faltando)}"


def test_o_que_nao_existe_esta_marcado_como_nao_existindo():
    """Ficha indisponível apresentada como disponível vira promessa."""
    por_codigo = {i.codigo: i for i in cat.listar()}
    for codigo, esperado in _ESPERADO.items():
        assert por_codigo[codigo].disponivel is esperado, (
            f"{codigo}: disponibilidade declarada não bate com o que o sistema tem")


def test_indisponivel_explica_o_motivo():
    for i in cat.listar():
        if i.disponivel:
            continue
        texto = i.restricoes.upper()
        assert "NÃO EXISTE" in texto or "NÃO HÁ" in texto, (
            f"{i.codigo}: marcado como indisponível, mas não diz por quê")


def test_codigos_sao_unicos():
    codigos = [i.codigo for i in cat.listar()]
    assert len(codigos) == len(set(codigos))


def test_reserva_orcamentaria_avisa_sobre_a_palavra_reserva():
    """O módulo usa 'reserva' para a reserva FINANCEIRA da conta pagadora.
    Sem este aviso, quem lê 'reserva' no sistema pensa em dotação."""
    ficha = {i.codigo: i for i in cat.listar()}["reserva_orcamentaria"]
    texto = (ficha.restricoes + ficha.nao_confundir).lower()
    assert "financeira" in texto and "conta pagadora" in texto


def test_comprometido_explica_a_nao_soma_dos_estados():
    """A armadilha do §12: autorizado, empenhado e liquidado coexistem e não
    podem ser somados."""
    ficha = {i.codigo: i for i in cat.listar()}["comprometido"]
    assert "não soma" in ficha.restricoes.lower()


def test_ordenacao_agrupa_e_poe_indisponivel_no_fim_do_grupo():
    itens = cat.listar()
    grupos_vistos: list[str] = []
    for i in itens:
        if not grupos_vistos or grupos_vistos[-1] != i.grupo:
            assert i.grupo not in grupos_vistos, f"grupo {i.grupo} aparece partido na lista"
            grupos_vistos.append(i.grupo)
    # Dentro de cada grupo, nenhum disponível vem depois de um indisponível.
    for grupo in grupos_vistos:
        do_grupo = [i.disponivel for i in itens if i.grupo == grupo]
        assert do_grupo == sorted(do_grupo, reverse=True), (
            f"{grupo}: indicador existente listado depois de um que não existe")


@pytest.mark.parametrize("codigo", ["disponibilidade_financeira", "disponibilidade_orcamentaria"])
def test_as_duas_disponibilidades_apontam_uma_para_a_outra(codigo):
    """É o par que mais confunde: dinheiro em conta versus dotação."""
    ficha = {i.codigo: i for i in cat.listar()}[codigo]
    assert "orçamentária" in ficha.nao_confundir.lower() or \
           "financeira" in ficha.nao_confundir.lower()

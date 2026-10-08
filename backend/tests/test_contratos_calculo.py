"""Contratos G1 — o cálculo de valor e vigência (`services.contratos.calcular`).

Função pura: estes testes não tocam o banco. Cada caso é uma linha da tabela do
§2.4 do spec (docs/superpowers/specs/2026-10-08-contratos-g1-modulo-e-contrato-design.md).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services import contratos as svc
from app.services.contratos import ContratoError, calcular, validar_combinacao_aditivo

HOJE = date(2026, 6, 1)


def _contrato(valor="100000.00", fim=date(2026, 12, 31), situacao="VIGENTE", reforma=False):
    return SimpleNamespace(
        valor_total=Decimal(valor), vigencia_fim=fim, situacao=situacao, reforma=reforma)


def _aditivo(tipo, valor="0", nova=None, situacao="VIGENTE", excluido=False):
    return SimpleNamespace(
        tipo=tipo, valor=Decimal(valor), nova_vigencia_fim=nova, situacao=situacao,
        excluido=excluido)


def _apostila(tipo, delta=None, excluido=False):
    return SimpleNamespace(
        tipo=tipo, valor_delta=None if delta is None else Decimal(delta), excluido=excluido)


def test_contrato_sem_atos_devolve_os_originais():
    c = calcular(_contrato(), [], [], hoje=HOJE)
    assert c.valor_inicial == Decimal("100000.00")
    assert c.valor_inicial_atualizado == Decimal("100000.00")
    assert c.valor_atualizado == Decimal("100000.00")
    assert c.vigencia_fim_atual == date(2026, 12, 31)
    assert c.percentual_acrescimo == Decimal("0.00")
    assert c.acima_do_limite is False
    assert c.dias_para_vencer == (date(2026, 12, 31) - HOJE).days


def test_acrescimo_soma_e_supressao_subtrai():
    c = calcular(_contrato(), [_aditivo("AA", "10000"), _aditivo("AR", "4000")], [], hoje=HOJE)
    assert c.acrescimos == Decimal("10000")
    assert c.supressoes == Decimal("4000")
    assert c.valor_atualizado == Decimal("106000.00")


def test_acrescimo_e_supressao_nao_se_compensam_no_limite():
    """30% de acréscimo com 20% de supressão dá líquido de 10% — e mesmo assim
    estoura: cada um é medido sozinho contra os 25% (decisão Q5 do spec)."""
    c = calcular(_contrato(), [_aditivo("AA", "30000"), _aditivo("AR", "20000")], [], hoje=HOJE)
    assert c.percentual_acrescimo == Decimal("30.00")
    assert c.percentual_supressao == Decimal("20.00")
    assert c.valor_atualizado == Decimal("110000.00")
    assert c.acima_do_limite is True


def test_exatamente_no_limite_nao_estoura():
    c = calcular(_contrato(), [_aditivo("AA", "25000")], [], hoje=HOJE)
    assert c.percentual_acrescimo == Decimal("25.00")
    assert c.acima_do_limite is False


def test_um_centavo_acima_do_limite_estoura():
    c = calcular(_contrato(), [_aditivo("AA", "25010")], [], hoje=HOJE)
    assert c.percentual_acrescimo == Decimal("25.01")
    assert c.acima_do_limite is True


def test_reforma_tem_limite_de_50_so_para_acrescimo():
    acrescimo = calcular(_contrato(reforma=True), [_aditivo("AA", "40000")], [], hoje=HOJE)
    assert acrescimo.limite_acrescimo == Decimal("50")
    assert acrescimo.acima_do_limite is False

    supressao = calcular(_contrato(reforma=True), [_aditivo("AR", "40000")], [], hoje=HOJE)
    assert supressao.limite_supressao == Decimal("25")
    assert supressao.acima_do_limite is True


def test_renovacao_soma_ao_valor_e_nao_conta_no_limite():
    c = calcular(
        _contrato(), [_aditivo("RE", "100000", nova=date(2027, 12, 31))], [], hoje=HOJE)
    assert c.renovacoes == Decimal("100000")
    assert c.valor_atualizado == Decimal("200000.00")
    assert c.percentual_acrescimo == Decimal("0.00")
    assert c.acima_do_limite is False
    assert c.vigencia_fim_atual == date(2027, 12, 31)


def test_apostila_de_reajuste_entra_na_base_e_nao_no_numerador():
    """Art. 125: o limite é sobre o valor inicial ATUALIZADO. Com reajuste de
    10%, um acréscimo de 27.500 é exatamente 25% — sem o reajuste seria 27,5%."""
    c = calcular(
        _contrato(), [_aditivo("AA", "27500")], [_apostila("REAJUSTE", "10000")], hoje=HOJE)
    assert c.valor_inicial_atualizado == Decimal("110000.00")
    assert c.percentual_acrescimo == Decimal("25.00")
    assert c.acima_do_limite is False
    assert c.valor_atualizado == Decimal("137500.00")


def test_apostila_sem_valor_nao_altera_nada():
    c = calcular(_contrato(), [], [_apostila("RAZAO_SOCIAL"), _apostila("DOTACAO")], hoje=HOJE)
    assert c.valor_atualizado == Decimal("100000.00")


def test_rascunho_anulado_e_excluido_ficam_fora_da_conta():
    aditivos = [
        _aditivo("AA", "50000", situacao="RASCUNHO"),
        _aditivo("AA", "50000", situacao="ANULADO"),
        _aditivo("AA", "50000", excluido=True),
        _aditivo("AP", nova=date(2030, 1, 1), situacao="RASCUNHO"),
    ]
    c = calcular(_contrato(), aditivos, [_apostila("REAJUSTE", "9999", excluido=True)], hoje=HOJE)
    assert c.valor_atualizado == Decimal("100000.00")
    assert c.vigencia_fim_atual == date(2026, 12, 31)


def test_vigencia_atual_e_a_maior_data_entre_os_aditivos():
    aditivos = [
        _aditivo("AP", nova=date(2027, 6, 30)),
        _aditivo("PA", "1000", nova=date(2028, 6, 30)),
        _aditivo("AA", "1000"),
    ]
    c = calcular(_contrato(), aditivos, [], hoje=HOJE)
    assert c.vigencia_fim_atual == date(2028, 6, 30)


def test_dias_para_vencer_negativo_quando_vencido_e_none_fora_de_vigente():
    vencido = calcular(_contrato(fim=date(2026, 5, 1)), [], [], hoje=HOJE)
    assert vencido.dias_para_vencer == -31

    for situacao in ("RASCUNHO", "ENCERRADO", "RESCINDIDO"):
        c = calcular(_contrato(situacao=situacao), [], [], hoje=HOJE)
        assert c.dias_para_vencer is None, situacao


@pytest.mark.parametrize("tipo, valor, nova", [
    ("AA", "10", None),
    ("AR", "10", None),
    ("AP", "0", date(2027, 1, 1)),
    ("PA", "10", date(2027, 1, 1)),
    ("PR", "10", date(2027, 1, 1)),
    ("RE", "10", date(2027, 1, 1)),
])
def test_combinacoes_validas_de_aditivo(tipo, valor, nova):
    validar_combinacao_aditivo(tipo, Decimal(valor), nova)


@pytest.mark.parametrize("tipo, valor, nova", [
    ("AA", "0", None),                    # acréscimo sem valor
    ("AR", "0", None),                    # redução sem valor
    ("AA", "10", date(2027, 1, 1)),       # acréscimo puro com data
    ("AP", "10", date(2027, 1, 1)),       # prazo puro com valor
    ("AP", "0", None),                    # prazo sem data
    ("PA", "10", None),                   # prazo e acréscimo sem data
    ("PA", "0", date(2027, 1, 1)),        # prazo e acréscimo sem valor
    ("RE", "0", date(2027, 1, 1)),        # renovação sem valor
])
def test_combinacoes_invalidas_de_aditivo_sao_422(tipo, valor, nova):
    with pytest.raises(ContratoError) as exc:
        validar_combinacao_aditivo(tipo, Decimal(valor), nova)
    assert exc.value.status_code == 422


def test_os_conjuntos_de_tipo_cobrem_os_seis_codigos_do_sim_sem_sobra():
    """Controle contra verde por vacuidade: se alguém acrescentar um sétimo
    tipo e esquecer de classificá-lo, ele não soma, não subtrai e não renova —
    o valor do contrato sai errado em silêncio."""
    from app.schemas.contratos import TIPOS_ADITIVO

    com_valor = svc.TIPOS_ACRESCIMO | svc.TIPOS_SUPRESSAO | svc.TIPOS_RENOVACAO
    assert com_valor | {"AP"} == set(TIPOS_ADITIVO)
    assert not (svc.TIPOS_ACRESCIMO & svc.TIPOS_SUPRESSAO)
    assert svc.TIPOS_COM_PRAZO == {"AP", "PA", "PR", "RE"}

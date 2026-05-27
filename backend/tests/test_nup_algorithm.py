"""Testes do algoritmo NUP (Decreto 8.539/2015) — Mod-11 puro, sem DB.

Cobre:
- ``calcular_dv_unitario`` (regra `resto == 10 → 0` é a sutileza crítica)
- ``calcular_dvs_nup`` (15 dígitos + 2 DVs)
- ``formatar_nup`` (validações de input)
- ``parsear_nup`` / ``validar_nup`` (round-trip e detecção de adulteração)
"""
from __future__ import annotations

import pytest

from app.services.nup import (
    NupError,
    calcular_dv_unitario,
    calcular_dvs_nup,
    formatar_nup,
    parsear_nup,
    validar_nup,
)


# -------- calcular_dv_unitario --------


class TestCalcularDvUnitario:
    def test_zero_unico(self):
        assert calcular_dv_unitario("0") == 0

    def test_um_digito(self):
        # "1" → 1*2 = 2, resto 2
        assert calcular_dv_unitario("1") == 2

    def test_resto_10_vira_0(self):
        """Regra Mod-11: quando ``soma % 11 == 10``, retorna 0 (não pode
        usar dígito 10). Sem isso a integração federal rejeita o NUP."""
        # "5" → 5*2 = 10 → resto 10 → returns 0
        assert calcular_dv_unitario("5") == 0
        # "05" → 0*3 + 5*2 = 10 → resto 10 → returns 0
        assert calcular_dv_unitario("05") == 0

    def test_quinze_zeros(self):
        assert calcular_dv_unitario("0" * 15) == 0

    def test_rejeita_nao_digito(self):
        with pytest.raises(NupError):
            calcular_dv_unitario("12a")

    def test_pesos_ciclicos(self):
        """9 dígitos exatos preenchem 1 ciclo completo de pesos. O 10º
        repete o peso 2, validando que o ciclo de fato volta."""
        # "111111111" (9×1): soma = 1*(2+3+4+5+6+7+8+9+2) = 46, resto 46%11=2
        assert calcular_dv_unitario("111111111") == 2
        # "1111111111" (10×1): soma = 46 + 1*3 = 49, resto 49%11=5
        # Aqui o décimo dígito da direita usa pesos[1]=3 (índice 9 % 8 = 1).
        assert calcular_dv_unitario("1111111111") == 5


# -------- calcular_dvs_nup --------


class TestCalcularDvsNup:
    def test_quinze_zeros_da_dois_zeros(self):
        # Tudo zero: soma 0 → dv1 0; com dv1 anexado ainda tudo zero → dv2 0
        assert calcular_dvs_nup("0" * 15) == "00"

    def test_exige_quinze_digitos(self):
        with pytest.raises(NupError):
            calcular_dvs_nup("1" * 14)
        with pytest.raises(NupError):
            calcular_dvs_nup("1" * 16)

    def test_rejeita_nao_digitos(self):
        with pytest.raises(NupError):
            calcular_dvs_nup("12345678901234a")


# -------- formatar_nup --------


class TestFormatarNup:
    def test_formato_correto(self):
        nup = formatar_nup("99001", 1, 2026)
        # NNNNN.NNNNNN/AAAA-DD
        assert nup.startswith("99001.000001/2026-")
        assert len(nup) == len("99001.000001/2026-00")

    def test_zero_pad_sequencial(self):
        nup = formatar_nup("99001", 42, 2026)
        assert "000042" in nup

    def test_rejeita_codigo_orgao_invalido(self):
        with pytest.raises(NupError):
            formatar_nup("9900", 1, 2026)  # 4 dígitos
        with pytest.raises(NupError):
            formatar_nup("990010", 1, 2026)  # 6 dígitos
        with pytest.raises(NupError):
            formatar_nup("99a01", 1, 2026)  # letra
        with pytest.raises(NupError):
            formatar_nup("", 1, 2026)

    def test_rejeita_sequencial_fora_range(self):
        with pytest.raises(NupError):
            formatar_nup("99001", 0, 2026)
        with pytest.raises(NupError):
            formatar_nup("99001", 1_000_000, 2026)
        with pytest.raises(NupError):
            formatar_nup("99001", -5, 2026)

    def test_rejeita_ano_invalido(self):
        with pytest.raises(NupError):
            formatar_nup("99001", 1, 999)
        with pytest.raises(NupError):
            formatar_nup("99001", 1, 10_000)


# -------- parsear_nup --------


class TestParsearNup:
    def test_round_trip(self):
        nup = formatar_nup("99001", 42, 2026)
        codigo, seq, ano, dvs = parsear_nup(nup)
        assert codigo == "99001"
        assert seq == 42
        assert ano == 2026
        assert len(dvs) == 2 and dvs.isdigit()

    def test_rejeita_sem_dvs(self):
        with pytest.raises(NupError):
            parsear_nup("99001.000001/2026")

    def test_rejeita_separadores_errados(self):
        with pytest.raises(NupError):
            parsear_nup("99001-000001/2026-00")  # - no lugar do .
        with pytest.raises(NupError):
            parsear_nup("99001.000001-2026-00")  # - no lugar da /

    def test_rejeita_string_vazia(self):
        with pytest.raises(NupError):
            parsear_nup("")


# -------- validar_nup --------


class TestValidarNup:
    def test_aceita_gerado(self):
        for seq in (1, 42, 999_999):
            nup = formatar_nup("99001", seq, 2026)
            assert validar_nup(nup) is True, f"esperava True para {nup}"

    def test_rejeita_adulteracao_sequencial(self):
        """Cliente troca sequencial mantendo DV original — DV recalculado
        difere, validar_nup retorna False."""
        nup = formatar_nup("99001", 5, 2026)
        prefix, dv = nup.rsplit("-", 1)
        # 99001.000005/2026 → 99001.000006/2026, mesmo DV
        head = prefix.replace("000005", "000006")
        adulterado = f"{head}-{dv}"
        assert validar_nup(adulterado) is False

    def test_rejeita_adulteracao_codigo_orgao(self):
        nup = formatar_nup("99001", 1, 2026)
        # troca 99001 por 99002, mantém DV
        prefix, dv = nup.rsplit("-", 1)
        head = prefix.replace("99001", "99002", 1)
        adulterado = f"{head}-{dv}"
        assert validar_nup(adulterado) is False

    def test_rejeita_dv_alterado(self):
        nup = formatar_nup("99001", 1, 2026)
        prefix, dv = nup.rsplit("-", 1)
        # incrementa DV1 — se já era 9 vai pra 10 quebrando o len, então
        # usamos transformação que sempre muda: trocar primeiro dígito do DV
        novo_dv = ("1" if dv[0] == "0" else "0") + dv[1]
        adulterado = f"{prefix}-{novo_dv}"
        assert validar_nup(adulterado) is False

    def test_rejeita_formato_errado(self):
        assert validar_nup("not a nup") is False
        assert validar_nup("") is False
        assert validar_nup("99001.000001/2026") is False  # sem DV

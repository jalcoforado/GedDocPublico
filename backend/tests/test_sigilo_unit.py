"""Sigilo gradual — testes unitários dos helpers puros (sem DB).

Cobre ranking dos níveis, credencial → níveis acessíveis, controle de acesso,
prazos legais da LAI, resolução do nível na abertura e aritmética de prazo.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.sigilo import (
    CREDENCIAL_DEFAULT,
    GRAUS_SIGILO_LEGAL,
    NIVEIS,
    NIVEL_RANK,
    PRAZO_MAX_ANOS,
    SigiloError,
    _add_anos,
    exige_tci,
    is_nivel_valido,
    niveis_permitidos,
    pode_acessar,
    resolver_nivel_criacao,
)


def test_niveis_ordem_e_ranks():
    assert NIVEIS == ("ostensivo", "interno", "reservado", "secreto", "ultrassecreto")
    assert NIVEL_RANK["ostensivo"] == 0
    assert NIVEL_RANK["ultrassecreto"] == 4
    # rank crescente == sensibilidade crescente
    assert NIVEL_RANK["reservado"] < NIVEL_RANK["secreto"] < NIVEL_RANK["ultrassecreto"]


def test_is_nivel_valido():
    assert is_nivel_valido("reservado")
    assert not is_nivel_valido("confidencial")
    assert not is_nivel_valido("")


def test_exige_tci():
    assert GRAUS_SIGILO_LEGAL == {"reservado", "secreto", "ultrassecreto"}
    assert exige_tci("reservado")
    assert exige_tci("ultrassecreto")
    assert not exige_tci("ostensivo")
    assert not exige_tci("interno")


def test_prazo_max_anos_lai():
    # LAI art. 24 §1º
    assert PRAZO_MAX_ANOS["reservado"] == 5
    assert PRAZO_MAX_ANOS["secreto"] == 15
    assert PRAZO_MAX_ANOS["ultrassecreto"] == 25
    assert PRAZO_MAX_ANOS["ostensivo"] is None
    assert PRAZO_MAX_ANOS["interno"] is None


def test_niveis_permitidos_por_credencial():
    assert niveis_permitidos("ostensivo") == ["ostensivo"]
    assert niveis_permitidos("interno") == ["ostensivo", "interno"]
    assert niveis_permitidos("secreto") == [
        "ostensivo",
        "interno",
        "reservado",
        "secreto",
    ]
    assert niveis_permitidos("ultrassecreto") == list(NIVEIS)


def test_niveis_permitidos_credencial_invalida_usa_default():
    assert niveis_permitidos("inexistente") == niveis_permitidos(CREDENCIAL_DEFAULT)


def test_pode_acessar_respeita_rank():
    # credencial interno alcança ostensivo+interno, não os graus de sigilo legal
    assert pode_acessar("interno", "ostensivo")
    assert pode_acessar("interno", "interno")
    assert not pode_acessar("interno", "reservado")
    assert not pode_acessar("interno", "ultrassecreto")
    # credencial mais alta alcança as mais baixas
    assert pode_acessar("secreto", "reservado")
    assert not pode_acessar("secreto", "ultrassecreto")


def test_pode_acessar_super_usuario_ignora():
    assert pode_acessar("ostensivo", "ultrassecreto", is_super=True)


def test_resolver_nivel_criacao_deriva_de_publico():
    # cliente legado: só manda publico
    assert resolver_nivel_criacao("ostensivo", publico=True) == "ostensivo"
    assert resolver_nivel_criacao("ostensivo", publico=False) == "interno"


def test_resolver_nivel_criacao_nivel_tem_precedencia():
    # cliente novo manda nivel != ostensivo → ignora publico
    assert resolver_nivel_criacao("interno", publico=True) == "interno"


def test_resolver_nivel_criacao_rejeita_sigilo_legal():
    # abertura não aceita grau de sigilo legal (precisa TCI via classificação)
    for nivel in ("reservado", "secreto", "ultrassecreto"):
        with pytest.raises(SigiloError, match="TCI|classifica"):
            resolver_nivel_criacao(nivel, publico=True)


def test_resolver_nivel_criacao_rejeita_invalido():
    with pytest.raises(SigiloError, match="inválido"):
        resolver_nivel_criacao("confidencial", publico=True)


def test_add_anos_normal():
    assert _add_anos(date(2026, 5, 28), 5) == date(2031, 5, 28)


def test_add_anos_bissexto():
    # 29/02 + 1 ano cai em ano não-bissexto → 28/02
    assert _add_anos(date(2024, 2, 29), 1) == date(2025, 2, 28)

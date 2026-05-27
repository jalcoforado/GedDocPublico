"""Tokenização do serviço de Temporalidade — unit puro, sem DB.

Cobre o algoritmo que normaliza texto pra match com palavras-chave do CCD:
- ``_strip_accents`` (NFD + remove combining marks)
- ``_tokenize`` (lowercase + sem acento + sem stopword + len ≥ 3)
- ``_iter_class_terms`` (tokens da classe: nome + palavras_chave CSV)
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.services.temporalidade import (
    _iter_class_terms,
    _strip_accents,
    _tokenize,
)


# -------- _strip_accents --------


class TestStripAccents:
    def test_palavra_com_cedilha_e_til(self):
        assert _strip_accents("Aquisição") == "Aquisicao"

    def test_palavra_com_acento_agudo(self):
        assert _strip_accents("Petição") == "Peticao"

    def test_palavra_sem_acento_passa_intacta(self):
        assert _strip_accents("processo") == "processo"

    def test_string_vazia(self):
        assert _strip_accents("") == ""

    def test_so_acentos(self):
        # NFD decompõe e remove marks → fica vazio
        assert _strip_accents("á é í ó ú").replace(" ", "") == "aeiou"


# -------- _tokenize --------


class TestTokenize:
    def test_string_vazia_da_set_vazio(self):
        assert _tokenize("") == set()

    def test_palavra_unica(self):
        assert _tokenize("processo") == {"processo"}

    def test_normaliza_lowercase(self):
        assert _tokenize("PROCESSO") == {"processo"}

    def test_normaliza_acentos(self):
        # "Aquisição" → "aquisicao"
        assert "aquisicao" in _tokenize("Aquisição")

    def test_remove_stopwords(self):
        # 'de', 'do', 'em', 'para' devem sair
        tokens = _tokenize("Aquisição de equipamentos para o setor")
        assert "de" not in tokens
        assert "para" not in tokens
        assert "aquisicao" in tokens
        assert "equipamentos" in tokens
        assert "setor" in tokens

    def test_remove_tokens_curtos(self):
        # 'ab' tem 2 chars → fora; 'abc' tem 3 → fica
        tokens = _tokenize("ab abc abcd")
        assert "ab" not in tokens
        assert "abc" in tokens
        assert "abcd" in tokens

    def test_separa_por_pontuacao(self):
        tokens = _tokenize("casa, escola.urbano!")
        assert tokens == {"casa", "escola", "urbano"}

    def test_set_sem_duplicatas(self):
        assert _tokenize("processo processo processo") == {"processo"}

    def test_numeros_contam_como_alnum(self):
        # isalnum() inclui dígitos
        tokens = _tokenize("doc123 ano2026")
        assert "doc123" in tokens
        assert "ano2026" in tokens

    def test_palavra_so_com_underscore_excluida(self):
        # _ não é alnum → quebra; resto avalia
        tokens = _tokenize("foo_bar")
        assert "foo" in tokens
        assert "bar" in tokens
        assert "foo_bar" not in tokens

    def test_stopword_acentuada_normalizada(self):
        # _STOPWORDS_PT tem "que" (sem acento). _tokenize normaliza antes
        # de comparar — "que" do input vira "que" e é descartado.
        assert "que" not in _tokenize("documento que arquivar")


# -------- _iter_class_terms --------


class TestIterClassTerms:
    def _classe(self, nome: str, palavras_chave: str | None) -> MagicMock:
        c = MagicMock()
        c.nome = nome
        c.palavras_chave = palavras_chave
        return c

    def test_so_nome(self):
        c = self._classe("Administração", None)
        tokens = set(_iter_class_terms(c))
        assert "administracao" in tokens

    def test_nome_mais_palavras_chave_csv(self):
        c = self._classe(
            "Aquisição",
            "licitacao, contrato, fornecedor",
        )
        tokens = set(_iter_class_terms(c))
        assert "aquisicao" in tokens
        assert "licitacao" in tokens
        assert "contrato" in tokens
        assert "fornecedor" in tokens

    def test_palavras_chave_vazia(self):
        c = self._classe("Finanças", "")
        tokens = set(_iter_class_terms(c))
        assert tokens == {"financas"}

    def test_palavras_chave_com_espacos_extras(self):
        c = self._classe("X", "  alfa  ,   beta  ,gama  ")
        tokens = set(_iter_class_terms(c))
        # 'x' tem 1 char → descartado por _tokenize (len<3)
        assert "alfa" in tokens
        assert "beta" in tokens
        assert "gama" in tokens

    def test_palavras_chave_multi_palavra(self):
        """Cada entrada CSV pode ter várias palavras separadas por espaço."""
        c = self._classe(
            "RH",
            "folha de pagamento, ferias trabalhador",
        )
        tokens = set(_iter_class_terms(c))
        # 'rh' descartado (len<3)
        assert "folha" in tokens
        assert "pagamento" in tokens
        # 'de' é stopword
        assert "de" not in tokens
        assert "ferias" in tokens
        assert "trabalhador" in tokens

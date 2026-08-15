"""Guarda de `avaliar_sistema` — o eixo `APP_NAME` × `utils.sistema`.

Por que uma função pura e um teste de tabela, e não um teste com banco: o
defeito que ela procura **não existe no ambiente de quem escreve o teste**. O
dev local tem uma linha só de `utils.sistema`, alinhada com `APP_NAME`; um teste
que leia o banco passaria verde aqui para sempre, sem nunca exercitar nenhum dos
casos ruins. É a mesma armadilha que o CLAUDE.md registra sobre a suíte inteira
ter exercitado só super-usuário.

O cenário que motivou isto foi medido na VPS em 2026-08-14: duas linhas em
`utils.sistema` (`aprimora` id 2 com **zero** transações, `sistemas` id 3 com
25), um grupo `Administradores` em cada e o mesmo `admin@local.test` nos dois.
Hoje o runtime roda em `sistemas` e está certo. Trocar `APP_NAME` para
`aprimora` não daria 403 em tela nenhuma: daria um super-usuário com catálogo
VAZIO — todas as telas somem e nada vai para o log.
"""
from __future__ import annotations

from app.cli.diagnostico_permissoes import avaliar_sistema

# O estado saudável: uma linha, casando com APP_NAME, com catálogo.
SAUDAVEL = [(1, "sistemas", 25)]

# O estado real da VPS em 2026-08-14.
VPS_2026_08_14 = [(2, "aprimora", 0), (3, "sistemas", 25)]


def test_estado_saudavel_nao_reclama() -> None:
    assert avaliar_sistema(SAUDAVEL, "sistemas") == []


def test_linha_orfa_e_apontada_mas_nao_confundida_com_quebra() -> None:
    """A VPS de hoje: correta em execução, com uma linha órfã ao lado."""
    problemas = avaliar_sistema(VPS_2026_08_14, "sistemas")
    assert len(problemas) == 1
    assert "fora do APP_NAME ativo" in problemas[0]
    assert "id 2" in problemas[0] and "`aprimora`" in problemas[0]


def test_app_name_apontando_para_sistema_sem_transacoes() -> None:
    """O cenário caro: SU com catálogo vazio, sem erro em lugar nenhum."""
    problemas = avaliar_sistema(VPS_2026_08_14, "aprimora")
    assert any("NENHUMA linha em `utils.sistema_transacao`" in p for p in problemas)


def test_app_name_sem_correspondencia() -> None:
    problemas = avaliar_sistema(SAUDAVEL, "aprimora")
    assert len(problemas) == 1
    assert "não casa com nenhuma linha" in problemas[0]
    # A mensagem tem de dizer o que EXISTE — sem isso ela não encurta nada.
    assert "`sistemas`" in problemas[0]


def test_app_name_ambiguo() -> None:
    """Duas linhas com o mesmo `app`: o RBAC escolhe uma, e não se sabe qual."""
    problemas = avaliar_sistema([(1, "sistemas", 25), (2, "sistemas", 3)], "sistemas")
    assert any("casa com 2 linhas" in p for p in problemas)


def test_catalogo_vazio_no_unico_sistema() -> None:
    """Controle: o aviso de catálogo vazio não depende de haver linha órfã."""
    problemas = avaliar_sistema([(1, "sistemas", 0)], "sistemas")
    assert len(problemas) == 1
    assert "NENHUMA linha" in problemas[0]

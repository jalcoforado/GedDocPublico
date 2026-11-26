"""A busca por texto das solicitações tem índice (migration 0134).

`_filtro_debitos` busca com `ILIKE '%termo%'`, que só aproveita índice trigram.
Os testes conferem que os quatro índices existem com a classe de operadores
certa e que o Postgres consegue de fato usá-los para o padrão que a aplicação
emite — índice criado com a classe errada existe e não serve para nada.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

ESPERADOS = {
    "ix_debito_descricao_trgm": ("debito", "descricao"),
    "ix_debito_numero_nf_trgm": ("debito", "numero_nf"),
    "ix_debito_numero_ne_trgm": ("debito", "numero_ne"),
    "ix_fornecedor_nome_trgm": ("fornecedor", "nome"),
}


@pytest.mark.asyncio
async def test_os_quatro_indices_trigram_existem(admin_session):
    rows = (await admin_session.execute(text(
        "SELECT indexname, tablename, indexdef FROM pg_indexes "
        "WHERE schemaname = 'pagamentos' AND indexname = ANY(:nomes)"),
        {"nomes": list(ESPERADOS)})).all()
    achados = {r[0]: (r[1], r[2]) for r in rows}
    assert set(achados) == set(ESPERADOS)
    for nome, (tabela, coluna) in ESPERADOS.items():
        tabela_real, definicao = achados[nome]
        assert tabela_real == tabela
        assert "USING gin" in definicao
        assert f"{coluna} " in definicao and "gin_trgm_ops" in definicao


@pytest.mark.asyncio
@pytest.mark.parametrize("tabela,coluna,indice", [
    ("pagamentos.debito", "descricao", "ix_debito_descricao_trgm"),
    ("pagamentos.debito", "numero_nf", "ix_debito_numero_nf_trgm"),
    ("pagamentos.debito", "numero_ne", "ix_debito_numero_ne_trgm"),
    ("pagamentos.fornecedor", "nome", "ix_fornecedor_nome_trgm"),
])
async def test_o_ilike_da_busca_consegue_usar_o_indice(admin_session, tabela, coluna, indice):
    """Com varredura sequencial desligada, o plano tem de escolher o índice.
    Em tabela pequena o planejador prefere varrer; desligar é o jeito de
    perguntar "dá para usar?" sem depender do volume de dados do banco."""
    await admin_session.execute(text("SET LOCAL enable_seqscan = off"))
    plano = (await admin_session.execute(text(
        f"EXPLAIN SELECT id FROM {tabela} WHERE {coluna} ILIKE :p ESCAPE '\\'"),
        {"p": "%extintor%"})).scalars().all()
    assert any(indice in linha for linha in plano), "\n".join(plano)

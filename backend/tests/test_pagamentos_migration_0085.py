"""A migration 0085 e o mapeamento do §4.5 da spec.

O que este arquivo protege não é a migration em si (o CI já a roda em banco
limpo) e sim o CONTRATO: toda combinação que o backfill produz tem de ser
válida nas três dimensões, e o `status` derivado dela tem de bater com o
`status` que a linha já tinha. Se não bater, o backfill perdeu informação.

Os testes de mapa rodam sobre `_migration.MAPA_BACKFILL`, importado de verdade
do arquivo da migration (via `importlib`, não uma segunda cópia colada aqui).
Antes desta correção, `MAPA` era uma TERCEIRA transcrição do §4.5, e o teste
só comparava contra si mesmo — editar `MAPA_BACKFILL` na migration sem editar
este arquivo passava verde com dado backfilled errado.
`test_mapa_do_teste_bate_com_a_migration` é o que fecha esse buraco.
"""
import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from app.services import pagamentos_estados as est

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic" / "versions" / "0085_pagamentos_tres_dimensoes.py"
)


def _carregar_migration_0085():
    spec = importlib.util.spec_from_file_location(
        "aprimora_migration_0085", _MIGRATION_PATH
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


_migration = _carregar_migration_0085()

# Transcrição independente do §4.5 da spec — existe para o teste abaixo
# comparar contra `_migration.MAPA_BACKFILL` de verdade, e não contra si
# mesma. Mudou na spec, muda aqui E na migration; o teste reprova se as duas
# cópias divergirem.
MAPA = {
    "RASCUNHO":               ("RASCUNHO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "EM_VALIDACAO":           ("AGUARDANDO_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "DEVOLVIDO":              ("AJUSTE_VALIDACAO", "NAO_REGISTRADA", "NAO_INICIADA"),
    "VALIDADO":               ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "ENVIADO_SECRETARIO":     ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AGUARDANDO_AUTORIZACAO": ("AGUARDANDO_AUTORIDADE", "REGISTRADA", "NAO_INICIADA"),
    "AUTORIZADO":             ("AUTORIZADA", "ELEGIVEL", "NAO_INICIADA"),
    "ENVIADO_TESOURARIA":     ("AUTORIZADA", "ELEGIVEL", "PROGRAMADA"),
    "EM_PROCESSAMENTO":       ("AUTORIZADA", "ELEGIVEL", "EM_PROCESSAMENTO"),
    "PAGO_PARCIAL":           ("AUTORIZADA", "ELEGIVEL", "PAGA_PARCIAL"),
    "PAGO":                   ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "CONCILIADO":             ("AUTORIZADA", "CONCLUIDA", "PAGA"),
    "REJEITADO":              ("REJEITADA_GESTOR", "NAO_REGISTRADA", "NAO_INICIADA"),
    "SUSPENSO":               ("AJUSTE_VALIDACAO", "BLOQUEADA", "NAO_INICIADA"),
    "CANCELADO":              ("CANCELADA", "RETIRADA", "CANCELADA"),
    "ESTORNADO":              ("AUTORIZADA", "ELEGIVEL", "ESTORNADA"),
}


def test_mapa_do_teste_bate_com_a_migration():
    """Sem esta asserção, os testes abaixo validariam uma cópia isolada do
    mapa — verde mesmo que `MAPA_BACKFILL` da migration 0085 divergisse."""
    assert MAPA == _migration.MAPA_BACKFILL


def test_mapa_cobre_os_dezesseis_status_legados():
    from app.schemas.pagamentos import StatusDebito
    legados = set(StatusDebito.__args__)
    assert set(_migration.MAPA_BACKFILL) == legados


def test_toda_combinacao_do_mapa_e_valida():
    for legado, (tram, fila, pag) in _migration.MAPA_BACKFILL.items():
        assert tram in est.TRAMITACAO, legado
        assert fila in est.FILA, legado
        assert pag in est.PAGAMENTO, legado


def test_backfill_nao_perde_informacao():
    """O status derivado do trio tem de reproduzir o status de origem.

    As três exceções são deliberadas e estão registradas na spec §4.5:
    VALIDADO e AGUARDANDO_AUTORIZACAO colapsam em ENVIADO_SECRETARIO (os três
    significavam 'na fila da autoridade'), e CONCILIADO colapsa em PAGO (a
    conciliação vira atributo da parcela).
    """
    colapsos = {"VALIDADO": "ENVIADO_SECRETARIO",
                "AGUARDANDO_AUTORIZACAO": "ENVIADO_SECRETARIO",
                "CONCILIADO": "PAGO"}
    for legado, (tram, fila, pag) in _migration.MAPA_BACKFILL.items():
        esperado = colapsos.get(legado, legado)
        assert est.status_legado(tram, fila, pag) == esperado, legado


@pytest.mark.asyncio
async def test_colunas_existem_e_sao_not_null(admin_session):
    sql = text("""
        SELECT column_name, is_nullable FROM information_schema.columns
        WHERE table_schema = 'pagamentos' AND table_name = 'debito'
          AND column_name IN ('situacao_tramitacao','situacao_fila',
                              'situacao_pagamento','id_unidade','versao','lock_version')
    """)
    achadas = {r[0]: r[1] for r in (await admin_session.execute(sql)).all()}
    assert len(achadas) == 6, f"faltam colunas: {achadas}"
    for coluna, nulavel in achadas.items():
        assert nulavel == "NO", f"{coluna} deveria ser NOT NULL"


@pytest.mark.asyncio
async def test_transacao_pagamento_gerir_existe(admin_session):
    row = (await admin_session.execute(text(
        "SELECT codigo FROM utils.transacao WHERE codigo = 'pagamento_gerir'"
    ))).first()
    assert row is not None, "a migration 0085 deve criar a transação pagamento_gerir"

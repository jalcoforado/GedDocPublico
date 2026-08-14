"""Guardas do reparo de GRANTs (`app.cli.reparar_grants`).

O reparo funciona porque faz duas coisas na ordem certa: aplica o GRANT-cobertor
nos schemas de baseline e, logo em seguida, reafirma **todas** as revogações que
as migrations declararam. A segunda metade é o que torna a primeira segura de
repetir — e é também a que apodrece sozinha: uma migration futura que revogue
mais alguma coisa de `aprimora_app` não tem como saber que existe uma lista
paralela num CLI.

Se as duas listas divergirem, o reparo passa a **reabrir** privilégio que uma
migration de segurança fechou, e não haveria sintoma: o banco simplesmente
voltaria a um estado mais permissivo, em silêncio, na próxima vez que alguém
rodasse o comando para consertar outra coisa. Estes dois testes existem só para
isso.

`test_lista_do_cli_cobre_as_migrations` compara declaração com declaração —
falha assim que uma migration nova entra. `test_banco_esta_no_estado_declarado`
compara declaração com o BANCO — falha quando o ambiente derivou, que é o
defeito original que motivou o CLI.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from app.cli.reparar_grants import APP, REVOGACOES, SCHEMAS_BASELINE
from app.services.tenant_config import COLUNAS_MUNICIPAIS_DE_TENANT

_VERSOES = Path(__file__).resolve().parents[1] / "alembic" / "versions"

#: Migrations que revogam privilégio de `aprimora_app` por meio de uma lista
#: `_REVOGACOES` importável. A 0080 não entra aqui porque não usa essa forma:
#: ela troca `UPDATE` de tabela por `UPDATE` de coluna, e quem guarda a
#: correspondência dela com o código é `test_grant_por_coluna_tenant.py`.
_MIGRATIONS_COM_REVOGACOES = ("0076", "0079")


def _carrega_migration(prefixo: str):
    (caminho,) = sorted(_VERSOES.glob(f"{prefixo}_*.py"))
    spec = importlib.util.spec_from_file_location(f"_mig_{prefixo}", caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _privilegios(texto: str) -> set[str]:
    """`"UPDATE, DELETE"` -> `{"UPDATE", "DELETE"}`; `"ALL"` -> os quatro."""
    itens = {p.strip().upper() for p in texto.split(",") if p.strip()}
    if "ALL" in itens:
        return {"SELECT", "INSERT", "UPDATE", "DELETE"}
    return itens


def test_lista_do_cli_cobre_as_migrations() -> None:
    """Tudo que uma migration revoga de `aprimora_app` está no CLI."""
    do_cli: dict[str, set[str]] = {}
    for objeto, privilegios, _razao in REVOGACOES:
        do_cli.setdefault(objeto, set()).update(_privilegios(privilegios))
    # A 0080 revoga `UPDATE` de tabela em `tenant` fora da lista, num statement
    # solto — o CLI faz o mesmo, e o teste precisa saber disso para não acusar
    # falso negativo.
    do_cli.setdefault("aprimora_py.tenant", set()).add("UPDATE")

    faltando: list[str] = []
    for prefixo in _MIGRATIONS_COM_REVOGACOES:
        modulo = _carrega_migration(prefixo)
        for objeto, revogar, _restaurar, _razao in modulo._REVOGACOES:
            ausentes = _privilegios(revogar) - do_cli.get(objeto, set())
            if ausentes:
                faltando.append(f"{prefixo}: {objeto} — {sorted(ausentes)}")

    assert not faltando, (
        "A migration revoga privilégio que `app.cli.reparar_grants` não reafirma. "
        "Rodar o reparo devolveria a `aprimora_app` o que a migration fechou:\n  "
        + "\n  ".join(faltando)
    )


def test_toda_revogacao_tem_razao_escrita() -> None:
    """Sem razão ninguém julga depois se a revogação continua correta."""
    for objeto, privilegios, razao in REVOGACOES:
        assert len(razao) > 20, f"{objeto} ({privilegios}) sem razão utilizável"


@pytest.mark.asyncio
async def test_banco_esta_no_estado_declarado(admin_session) -> None:
    """Toda tabela do baseline tem DML para `aprimora_app`, menos as declaradas.

    Este é o teste que teria gritado no dia em que o banco local derivou, em vez
    de deixar ~21 testes de RLS vermelhos com `permission denied` e a causa
    espalhada por cinco arquivos.
    """
    esperado_sem: dict[str, set[str]] = {}
    for objeto, privilegios, _razao in REVOGACOES:
        esperado_sem.setdefault(objeto, set()).update(_privilegios(privilegios))
    esperado_sem.setdefault("aprimora_py.tenant", set()).add("UPDATE")

    linhas = await admin_session.execute(
        text(
            """
            SELECT c.relnamespace::regnamespace::text || '.' || c.relname AS objeto,
                   has_table_privilege(:papel, c.oid, 'SELECT') AS s,
                   has_table_privilege(:papel, c.oid, 'INSERT') AS i,
                   has_table_privilege(:papel, c.oid, 'UPDATE') AS u,
                   has_table_privilege(:papel, c.oid, 'DELETE') AS d
            FROM pg_class c
            WHERE c.relkind = 'r'
              AND c.relnamespace::regnamespace::text = ANY(:schemas)
              AND c.relname <> 'alembic_version'
            """
        ),
        {"papel": APP, "schemas": list(SCHEMAS_BASELINE)},
    )

    divergencias: list[str] = []
    for objeto, s, i, u, d in linhas:
        tem = {p for p, v in (("SELECT", s), ("INSERT", i), ("UPDATE", u), ("DELETE", d)) if v}
        deveria = {"SELECT", "INSERT", "UPDATE", "DELETE"} - esperado_sem.get(objeto, set())
        if tem != deveria:
            divergencias.append(
                f"{objeto}: tem {sorted(tem)}, esperado {sorted(deveria)}"
            )

    assert not divergencias, (
        "O banco não está no estado de grants declarado.\n"
        "Deriva de ambiente conserta-se com "
        "`python -m app.cli.reparar_grants --aplicar`; se a divergência vier de "
        "migration nova, atualize REVOGACOES no CLI.\n  "
        + "\n  ".join(sorted(divergencias))
    )


@pytest.mark.asyncio
async def test_update_em_tenant_continua_por_coluna(admin_session) -> None:
    """O reparo não pode devolver `UPDATE` de TABELA em `tenant` (0080).

    Controle de vacuidade do teste acima: `has_table_privilege(...,'UPDATE')` é
    `false` tanto quando o grant por coluna está certo quanto quando não existe
    grant nenhum. Sem conferir as colunas, a linha de `tenant` passaria verde num
    banco onde o município perdeu a configuração institucional inteira.
    """
    for coluna in sorted(COLUNAS_MUNICIPAIS_DE_TENANT):
        pode = await admin_session.scalar(
            text(
                "SELECT has_column_privilege(:papel, 'aprimora_py.tenant', :col, 'UPDATE')"
            ),
            {"papel": APP, "col": coluna},
        )
        assert pode, f"aprimora_app perdeu UPDATE na coluna municipal `{coluna}`"

    for coluna in ("ativo", "plano", "slug"):
        pode = await admin_session.scalar(
            text(
                "SELECT has_column_privilege(:papel, 'aprimora_py.tenant', :col, 'UPDATE')"
            ),
            {"papel": APP, "col": coluna},
        )
        assert not pode, f"aprimora_app voltou a poder gravar `{coluna}` em tenant"

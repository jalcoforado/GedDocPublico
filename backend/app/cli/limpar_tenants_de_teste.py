"""Apaga tenants deixados para trás pela suíte num banco de DESENVOLVIMENTO.

## O que motivou (item 1.1.6 do backlog)

Medido em 2026-08-14 no dev local: `aprimora_py.tenant` com **4.033** linhas.
Uma é `sobral`; as outras **4.032** casam o padrão de slug de teste e nasceram
entre 07/08 e 14/08 — **uma semana** de execuções da suíte.

Não é a fixture `two_tenants`, que apaga no teardown. São os ~69 arquivos de
teste que chamam `provisionar_tenant` por conta própria e não desfazem. Um teste
que cria tenant e não limpa **nunca fica vermelho** — só fica caro. Por isso
durou meses sem ninguém ver.

O CI não sofre: banco novo a cada run. Quem sofre é banco de dev de vida longa,
que é justamente onde ninguém olha.

## Por que `session_replication_role`, e não uma ordem de DELETE

`aprimora_py.tenant` recebe **97 chaves estrangeiras**, e **95 delas são
`NO ACTION`** — só uma é `ON DELETE CASCADE`. Apagar um tenant "na ordem certa"
exigiria ordenar topologicamente 96 tabelas que também se referenciam entre si,
e essa ordem envelheceria a cada migration nova. `SET session_replication_role
= replica` desliga a checagem de FK **na sessão**, dentro da transação, e o
problema de ordenação simplesmente deixa de existir.

Isso pede o papel dono do banco (`ged_user`), o mesmo que os CLIs
administrativos já usam. Não é concessão nova de privilégio, e não mexe em RLS.

## As barreiras, porque isto apaga dado

1. **Só slug de teste.** O alvo tem de casar `PADRAO_SLUG_DE_TESTE` — prefixo
   mais 8 hexadecimais, a convenção que o `CLAUDE.md` exige dos testes. O que
   não casa é **preservado e listado por nome** no relatório, para que a
   classificação seja conferível a olho antes do `--apagar`.
2. **Nomes reservados nunca entram**, mesmo que casassem o padrão.
3. **`--dry-run` é o comportamento padrão.** Apagar exige `--apagar`.
4. **Uma transação só.** Erro no meio não deixa meio-tenant.

Uso::

    docker exec aprimora-py-backend python -m app.cli.limpar_tenants_de_teste
    docker exec aprimora-py-backend python -m app.cli.limpar_tenants_de_teste --apagar
"""
from __future__ import annotations

import argparse
import asyncio
import re

from sqlalchemy import text

from ..database_admin import AdminSessionLocal, descartar_engine_admin

#: Prefixo curto + `uuid4().hex[:8]`, com ou sem hífen — a convenção de slug de
#: teste do `CLAUDE.md` (`e2e-`, `sec1-`, `p52-`, `alv`, …). O sufixo de 8
#: hexadecimais é o que distingue "gerado por teste" de "cadastrado por gente".
PADRAO_SLUG_DE_TESTE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-?[0-9a-f]{8}$")

#: Nunca apagados, aconteça o que acontecer com o padrão acima.
SLUGS_RESERVADOS = frozenset({"sobral", "default", "demo", "admin", "plataforma"})


def eh_tenant_de_teste(slug: str) -> bool:
    """Classificador puro — a parte que precisa de teste, e a que decide tudo."""
    if slug in SLUGS_RESERVADOS:
        return False
    return bool(PADRAO_SLUG_DE_TESTE.match(slug))


_TENANTS = text("SELECT id, slug FROM aprimora_py.tenant ORDER BY id")

_TABELAS_COM_TENANT = text(
    """
    SELECT c.table_schema, c.table_name
    FROM information_schema.columns c
    JOIN pg_class pc ON pc.relname = c.table_name
    JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = c.table_schema
    WHERE c.column_name = 'tenant_id'
      AND pc.relkind = 'r'
      AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
      AND NOT (c.table_schema = 'aprimora_py' AND c.table_name = 'tenant')
    ORDER BY 1, 2
    """
)


async def _main(apagar: bool) -> int:
    async with AdminSessionLocal() as db:
        linhas = [(int(r[0]), str(r[1])) for r in await db.execute(_TENANTS)]
        alvos = [(tid, slug) for tid, slug in linhas if eh_tenant_de_teste(slug)]
        preservados = [slug for _tid, slug in linhas if not eh_tenant_de_teste(slug)]

        print(f"Tenants no banco: {len(linhas)}")
        print(f"  preservados: {len(preservados)} — {', '.join(sorted(preservados)) or '(nenhum)'}")
        print(f"  de teste:    {len(alvos)}")

        if not alvos:
            print("\nNada a fazer.")
            return 0

        if not apagar:
            amostra = ", ".join(slug for _tid, slug in alvos[:8])
            print(f"\nAmostra: {amostra}{' …' if len(alvos) > 8 else ''}")
            print("Nada foi apagado (modo relatório). Rode com --apagar.")
            return 0

        ids = [tid for tid, _slug in alvos]
        tabelas = [(str(r[0]), str(r[1])) for r in await db.execute(_TABELAS_COM_TENANT)]

        # Desliga a checagem de FK NESTA sessão. Ver o docstring: 95 das 97 FKs
        # para `tenant` são NO ACTION, e ordenar 96 tabelas topologicamente seria
        # uma lista que envelhece a cada migration.
        await db.execute(text("SET session_replication_role = replica"))
        apagadas = 0
        for schema, tabela in tabelas:
            res = await db.execute(
                text(f"DELETE FROM {schema}.{tabela} WHERE tenant_id = ANY(:ids)"),
                {"ids": ids},
            )
            apagadas += res.rowcount or 0
        res = await db.execute(
            text("DELETE FROM aprimora_py.tenant WHERE id = ANY(:ids)"), {"ids": ids}
        )
        await db.execute(text("SET session_replication_role = origin"))
        await db.commit()

        print(
            f"\nApagados {res.rowcount} tenant(s) e {apagadas} linha(s) "
            f"dependentes em {len(tabelas)} tabela(s)."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Apaga tenants de teste deixados pela suíte. Sem --apagar, só relata."
        )
    )
    parser.add_argument(
        "--apagar",
        action="store_true",
        help="Executa a limpeza. Sem esta flag o comando só relata.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_main(args.apagar))
    finally:
        asyncio.run(descartar_engine_admin())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Repara os GRANTs de baseline de `aprimora_app` num banco JÁ EXISTENTE.

Por que isto precisa existir
----------------------------

O `scripts/bootstrap-db.sh` só roda o GRANT-cobertor
(`GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES ...`) quando ele mesmo
carregou o dump na mesma execução (`SCHEMA_LOADED=0`). O `else` que pula o
cobertor está **certo** e foi decidido em SEC-01A: rodá-lo de novo desfaria em
silêncio os `REVOKE` das migrations 0076/0079/0080 e devolveria a
`aprimora_app` escrita em `platform_principal`, `platform_audit_log`, no
catálogo de módulos e na trilha de auditoria.

A consequência não pretendida é que **um banco criado antes de o passo 3b
existir nunca recebe o cobertor, e re-rodar o bootstrap não conserta** — por
decisão, não por bug. Ele fica sem a DML de baseline em `protocolos.*`,
`utils.*` e na parte municipal de `aprimora_py.*`, para sempre.

O sintoma é insidioso porque não é o de uma quebra: a suíte fica com ~21
testes vermelhos **só na máquina**, todos com `permission denied for table X`
sob `aprimora_app`, enquanto o CI — que sempre parte de banco novo — fica
verde. Depois de conviver com isso alguns dias, o vermelho vira paisagem, e é
exatamente nele que uma quebra real de RLS se esconderia sem ser notada.

Medido em 2026-08-13, antes de escrever este CLI:

    ambiente   protocolos      utils        aprimora_py
    local      81/86 sem DML   86/86        17/18
    VPS        0/86            0/86          6/18  ← as 6 revogadas de propósito

Ou seja: **a VPS está no estado correto e o problema é do dev local.** Isso
importa para calibrar a urgência — não é bloqueio do `SEC-RLS-ROLLOUT`, é
higiene de ambiente. Mas importa também na direção oposta: o motivo de
ninguém ter tropeçado nisso em produção é o achado **F-12**, o runtime conecta
como `ged_user` (`BYPASSRLS`), e portanto **nenhum destes grants é exercitado
hoje fora dos testes**. No dia em que `APP_DATABASE_URL` for definida, um
ambiente com esta deriva não degrada: para de funcionar inteiro.

O que este CLI faz
------------------

Reproduz o estado final do CI num banco existente, em **uma transação**:

1. o cobertor nos quatro schemas de baseline;
2. logo em seguida, a reafirmação de **todas** as revogações declaradas pelas
   migrations — a lista abaixo espelha 0076 §5, 0079 e 0080.

A ordem é a mesma do CI (cobertor primeiro, revogação depois) e o passo 2 é o
que torna o passo 1 seguro de repetir. Se a lista de revogações do repositório
crescer e esta aqui não acompanhar, o reparo passa a reabrir privilégio — por
isso `tests/test_guarda_reparar_grants.py` compara as duas.

Requer a credencial **dona** das tabelas (`ged_user`). Com
`MIGRATOR_DATABASE_URL` definida — que o CLAUDE.md proíbe — o `GRANT` falha
com `must be owner of table`, e a transação inteira volta atrás em vez de
deixar o banco meio reparado.

Uso::

    docker exec aprimora-py-backend python -m app.cli.reparar_grants           # relatório
    docker exec aprimora-py-backend python -m app.cli.reparar_grants --aplicar
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import text

from ..database_admin import AdminSessionLocal, descartar_engine_admin
from ..services.tenant_config import COLUNAS_MUNICIPAIS_DE_TENANT

APP = "aprimora_app"
S = "aprimora_py"

#: Os schemas que o dump de baseline traz. `pagamentos`, `frota` e
#: `transporte_regulado` nascem nas migrations e concedem os próprios grants —
#: incluí-los aqui não seria errado, seria redundante e mascararia migration
#: futura que esquecesse o `GRANT` do boilerplate.
SCHEMAS_BASELINE: tuple[str, ...] = ("protocolos", "utils", "aprimora_py", "public")

#: (objeto, privilégios, razão). Espelha `_REVOGACOES` da 0076 e da 0079, mais
#: as duas tabelas de plataforma da 0076 §4. A razão é obrigatória pelo mesmo
#: motivo que lá: sem ela ninguém julga depois se a revogação continua correta.
REVOGACOES: tuple[tuple[str, str, str], ...] = (
    (f"{S}.platform_principal", "ALL", "tabela de plataforma — só aprimora_platform escreve (ADR-016 §2.3); não tem RLS, o grant é a única barreira"),
    (f"{S}.platform_audit_log", "ALL", "trilha autoritativa de plataforma, append-only e fora da RLS municipal"),
    (f"{S}.tenant", "INSERT, DELETE", "criar município é ato de plataforma (0079); apagar não é operação de runtime nenhum (0076)"),
    (f"{S}.tenant_modulo", "INSERT, UPDATE, DELETE", "contratar e descontratar é entitlement — operação de plataforma (0076, 0079)"),
    (f"{S}.audit_log", "UPDATE, DELETE", "trilha append-only: o município grava e lê, nunca altera nem apaga"),
    (f"{S}.modulo", "INSERT, UPDATE, DELETE", "catálogo global do produto; a 0073 concede só SELECT"),
    (f"{S}.modulo_transacao", "INSERT, UPDATE, DELETE", "mesma razão de `modulo`"),
)

#: Sequences de plataforma — revogadas junto, senão o `USAGE` sobrevive ao
#: `REVOKE ALL` da tabela e um `INSERT` futuro deixa de ser barrado pelo motivo
#: que se esperava.
SEQUENCES_REVOGADAS: tuple[str, ...] = (
    "platform_principal_id_seq",
    "platform_audit_log_id_seq",
)


def _sql_reparo() -> list[str]:
    """Os statements do reparo, na ordem. Separado para o teste poder lê-los."""
    stmts: list[str] = []
    for schema in SCHEMAS_BASELINE:
        stmts.append(f"GRANT USAGE ON SCHEMA {schema} TO {APP}")
        stmts.append(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {schema} TO {APP}"
        )
        stmts.append(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {schema} TO {APP}"
        )
    for objeto, privilegios, _razao in REVOGACOES:
        stmts.append(f"REVOKE {privilegios} ON {objeto} FROM {APP}")
    for seq in SEQUENCES_REVOGADAS:
        stmts.append(f"REVOKE ALL ON SEQUENCE {S}.{seq} FROM {APP}")

    # 0080 (SEC-RLS-00D): `UPDATE` em `tenant` é POR COLUNA. O cobertor acima
    # devolveu o de tabela, que é o mais amplo dos dois e tornaria o grant por
    # coluna decorativo — o mesmo modo de falhar em silêncio que a própria 0080
    # documenta. Revogar antes de conceder não é higiene, é o que faz a linha
    # seguinte significar alguma coisa.
    stmts.append(f"REVOKE UPDATE ON {S}.tenant FROM {APP}")
    colunas = ", ".join(sorted(COLUNAS_MUNICIPAIS_DE_TENANT))
    stmts.append(f"GRANT UPDATE ({colunas}) ON {S}.tenant TO {APP}")
    return stmts


_CONTAGEM = text(
    """
    SELECT c.relnamespace::regnamespace::text AS schema,
           count(*) FILTER (WHERE NOT has_table_privilege(:papel, c.oid, 'INSERT')) AS sem_dml,
           count(*) AS total
    FROM pg_class c
    WHERE c.relkind = 'r'
      AND c.relnamespace::regnamespace::text = ANY(:schemas)
    GROUP BY 1
    ORDER BY 1
    """
)


async def _retrato(db) -> list[tuple[str, int, int]]:
    linhas = await db.execute(
        _CONTAGEM, {"papel": APP, "schemas": list(SCHEMAS_BASELINE)}
    )
    return [tuple(linha) for linha in linhas]


def _imprime(titulo: str, retrato: list[tuple[str, int, int]]) -> None:
    print(f"\n{titulo}")
    for schema, sem_dml, total in retrato:
        marca = "  " if sem_dml == 0 else "!!"
        print(f"  {marca} {schema:<22} {sem_dml:>3} de {total:>3} sem INSERT para {APP}")


async def _main(aplicar: bool) -> int:
    async with AdminSessionLocal() as db:
        antes = await _retrato(db)
        _imprime("Antes:", antes)

        if not aplicar:
            print(
                "\nNada foi alterado (modo relatório). Rode com --aplicar para reparar."
            )
            print("Statements que seriam executados:")
            for stmt in _sql_reparo():
                print(f"  {stmt}")
            return 0

        # Uma transação só: `must be owner of table` no meio do caminho volta
        # tudo atrás em vez de deixar o cobertor aplicado e as revogações não —
        # que é o único estado pior do que a deriva original.
        for stmt in _sql_reparo():
            await db.execute(text(stmt))
        await db.commit()

        depois = await _retrato(db)
        _imprime("Depois:", depois)
        print(
            "\nOK. O que continua sem INSERT em aprimora_py são as tabelas "
            "revogadas de propósito — ver REVOGACOES neste módulo."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repara os GRANTs de baseline de aprimora_app num banco existente."
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Executa o reparo. Sem esta flag o comando só relata.",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(_main(args.aplicar))
    finally:
        asyncio.run(descartar_engine_admin())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""Backup / restore por tenant — Fase 34.

Uso:
    # Lista contagem de linhas por tabela do tenant
    docker exec aprimora-py-backend python -m app.cli.backup stats --tenant sobral

    # Gera um SQL com INSERTs de tudo do tenant (idempotent restore via DELETEs prefixos)
    docker exec aprimora-py-backend python -m app.cli.backup export --tenant sobral

    # Exporta + valida que o SQL parseia + reportar contagem
    docker exec aprimora-py-backend python -m app.cli.backup dr-drill --tenant sobral

O export gera UM arquivo SQL standalone:
  - SET session_replication_role = 'replica';  -- pula FK durante restore
  - INSERT INTO aprimora_py.tenant (...) VALUES (...);
  - DELETE FROM <tabela> WHERE tenant_id = <id>;  -- idempotente
  - INSERT INTO <tabela> ...;  (uma por linha)
  - SELECT setval(<sequence>, max(id));  -- para próximas inserções não colidirem
  - SET session_replication_role = 'origin';

Para restaurar em outro DB:
  psql -U ged_user -d destino -f backup_sobral_2026-05-23T17-30.sql

**Papel do restore (SEC-RLS-00B, inventário §8.2):** o arquivo gerado emite
`SET session_replication_role = 'replica'`, que **exige SUPERUSER**. O restore
é, portanto, operação de DBA — não de `aprimora_migrator` e muito menos de
`aprimora_app`. O EXPORT, esse sim, roda no papel administrativo, e é o que
esta CLI faz.

**ISTO NÃO É O BACKUP DO SISTEMA.** É exportação de UM tenant, para migrar ou
clonar. A lista `TENANTED_TABLES` abaixo tem **26 tabelas**, congeladas na Fase
34; o banco tem hoje **55 com `tenant_id`**. Ficam de fora, entre outras, as de
transporte regulado, pagamentos, minuta, notificação, workflow e `audit_log` —
e ficam de fora **em silêncio**, porque a lista é literal e não deriva do
schema. Para backup de verdade: `scripts/backup-aprimora.sh` e a seção "Backup
da máquina (VPS)" do RUNBOOK.

Tabelas: 26 tenanted (na ordem topológica das FKs) + a tabela `tenant` raiz.

Catálogos globais (utils.estado, utils.cidade, etc) NÃO entram — o destino
precisa tê-los populados separadamente (`utils.estado` é IBGE-fixed).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
# SEC-RLS-00B: operação ADMINISTRATIVA, não de runtime. A conexão vem de
# `MIGRATOR_DATABASE_URL` (papel `aprimora_migrator`) quando definida, e de
# `DATABASE_URL` enquanto não estiver — ver `app/database_admin.py`.
from ..database_admin import AdminSessionLocal


# Ordem topológica das tabelas tenanted — pais antes de filhos.
# Mesma lista do migration 0004 + 0006.
TENANTED_TABLES: list[tuple[str, str]] = [
    # protocolos (catálogos primeiro)
    ("protocolos", "tipo_manifestante"),
    ("protocolos", "tipo_processo"),
    ("protocolos", "tipo_anexo"),
    ("protocolos", "assunto"),
    ("protocolos", "assunto_tipo_processo_tipo_anexo"),
    ("protocolos", "manifestante"),
    ("protocolos", "processo"),
    ("protocolos", "movimentacao"),
    ("protocolos", "encaminhamento"),
    ("protocolos", "despacho"),
    ("protocolos", "arquivamento"),
    ("protocolos", "anexo"),
    ("protocolos", "anexo_processo"),
    ("protocolos", "solicitacao_assinatura"),
    ("protocolos", "usuario_assinatura"),
    ("protocolos", "assinatura_anexo"),
    # utils
    ("utils", "tipo_unidade_trabalho"),
    ("utils", "unidade_trabalho"),
    ("utils", "grupo"),
    ("utils", "grupo_transacao"),
    ("utils", "usuario"),
    ("utils", "usuario_externo"),
    ("utils", "usuario_grupo"),
    ("utils", "usuario_unidade_trabalho"),
    ("utils", "endereco"),
    # aprimora_py
    ("aprimora_py", "job"),
]


async def _resolve_tenant(db: AsyncSession, slug: str) -> tuple[int, str]:
    row = (
        await db.execute(
            text(
                "SELECT id, nome FROM aprimora_py.tenant WHERE slug = :s"
            ),
            {"s": slug},
        )
    ).first()
    if row is None:
        raise SystemExit(f"[ERRO] tenant slug='{slug}' não encontrado")
    return row[0], row[1]


@asynccontextmanager
async def _sessao_do_tenant(tenant_id: int) -> AsyncIterator[AsyncSession]:
    """Sessão com `app.tenant_id` instalado — e a PROVA de que foi instalado.

    Era daqui que vinha o pior item do inventário (§8.2): `_stats` e `_export`
    abriam `SessionLocal()` cru, sem contexto de tenant. Sob papel sujeito a
    RLS, TODO `SELECT ... WHERE tenant_id = :t` devolve zero linhas **sem
    erro** — o `stats` reporta o tenant vazio e o `export` grava um arquivo de
    backup sintaticamente válido e sem dados. O sintoma só aparece no restore,
    meses depois e longe da causa.

    O `raise` abaixo é controle positivo, não paranoia: sem ele, este helper
    "funcionaria" mesmo que alguém quebrasse o listener `after_begin` de
    `app/database.py`, e voltaríamos exatamente ao arquivo vazio — agora com um
    helper que parece resolver o problema.
    """
    async with AdminSessionLocal(tenant_id=tenant_id) as db:
        guc = (
            await db.execute(text("SELECT current_setting('app.tenant_id', true)"))
        ).scalar()
        if str(guc or "") != str(tenant_id):
            raise SystemExit(
                f"[ERRO] contexto de tenant NAO instalado na sessao: "
                f"app.tenant_id={guc!r}, esperado {str(tenant_id)!r}. "
                "Sob RLS isso produziria backup VAZIO sem erro nenhum — "
                "abortando antes de gravar arquivo."
            )
        yield db


async def _count_rows(db: AsyncSession, tenant_id: int) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for schema, table in TENANTED_TABLES:
        r = await db.execute(
            text(f'SELECT COUNT(*) FROM "{schema}"."{table}" WHERE tenant_id = :t'),
            {"t": tenant_id},
        )
        rows.append((schema, table, int(r.scalar() or 0)))
    return rows


async def _stats(args: argparse.Namespace) -> int:
    # Duas sessões, e a ordem importa: `aprimora_py.tenant` NÃO tem RLS e é
    # onde o slug vira id; só depois de saber o id dá para abrir a sessão COM
    # contexto de tenant, que é a que enxerga as 26 tabelas tenanted.
    async with AdminSessionLocal() as db:
        tid, nome = await _resolve_tenant(db, args.tenant)
    async with _sessao_do_tenant(tid) as db:
        print(f"Tenant: id={tid}  slug={args.tenant}  nome={nome}")
        print(f"{'Schema.Tabela':50}  {'Linhas':>10}")
        print("-" * 65)
        total = 0
        for schema, table, n in await _count_rows(db, tid):
            print(f"{(schema + '.' + table):50}  {n:10}")
            total += n
        print("-" * 65)
        print(f"{'TOTAL':50}  {total:10}")
    return 0


def _sql_value(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        return "'" + v.isoformat() + "'"
    if isinstance(v, bytes):
        return "decode('" + v.hex() + "', 'hex')"
    if isinstance(v, dict) or isinstance(v, list):
        import json

        s = json.dumps(v, ensure_ascii=False, default=str).replace("'", "''")
        return f"'{s}'::jsonb"
    s = str(v).replace("'", "''")
    return f"'{s}'"


async def _dump_table(
    db: AsyncSession, schema: str, table: str, tenant_id: int
) -> tuple[int, list[str]]:
    """Devolve (qty_rows, lista de statements SQL para INSERT no destino)."""
    # Lê colunas em ordem
    cols_rows = (
        await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t "
                "ORDER BY ordinal_position"
            ),
            {"s": schema, "t": table},
        )
    ).all()
    cols = [c[0] for c in cols_rows]
    if not cols:
        return 0, []

    cols_sql = ", ".join('"' + c + '"' for c in cols)
    rows = (
        await db.execute(
            text(
                f'SELECT {cols_sql} FROM "{schema}"."{table}" WHERE tenant_id = :t'
            ),
            {"t": tenant_id},
        )
    ).all()

    stmts: list[str] = []
    if not rows:
        return 0, stmts

    col_list = ", ".join(f'"{c}"' for c in cols)
    for r in rows:
        values = ", ".join(_sql_value(v) for v in r)
        stmts.append(
            f'INSERT INTO "{schema}"."{table}" ({col_list}) VALUES ({values});'
        )
    return len(rows), stmts


async def _dump_tenant_row(db: AsyncSession, tenant_id: int) -> list[str]:
    """Dump da própria linha de aprimora_py.tenant."""
    cols_rows = (
        await db.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'aprimora_py' AND table_name = 'tenant' "
                "ORDER BY ordinal_position"
            )
        )
    ).all()
    cols = [c[0] for c in cols_rows]
    cols_sql = ", ".join('"' + c + '"' for c in cols)
    row = (
        await db.execute(
            text(
                f"SELECT {cols_sql} FROM aprimora_py.tenant WHERE id = :t"
            ),
            {"t": tenant_id},
        )
    ).first()
    if row is None:
        return []
    col_list = ", ".join(f'"{c}"' for c in cols)
    values = ", ".join(_sql_value(v) for v in row)
    return [
        f"-- aprimora_py.tenant (registro do tenant)\n"
        f"DELETE FROM aprimora_py.tenant WHERE id = {tenant_id};\n"
        f"INSERT INTO aprimora_py.tenant ({col_list}) VALUES ({values});"
    ]


async def _dump_sequences(db: AsyncSession) -> list[str]:
    """Gera SELECT setval(<seq>, COALESCE(MAX(id), 1)) para cada PK sequencial
    das tabelas envolvidas. Importante para que próximos INSERTs no destino
    não colidam com IDs já gravados.
    """
    stmts: list[str] = []
    for schema, table in TENANTED_TABLES:
        stmt = text(
            f"SELECT pg_get_serial_sequence('\"{schema}\".\"{table}\"', 'id')"
        )
        seq = (await db.execute(stmt)).scalar()
        if seq:
            stmts.append(
                f"SELECT setval('{seq}', "
                f'(SELECT COALESCE(MAX(id), 1) FROM "{schema}"."{table}"));'
            )
    # tenant table também
    seq_tenant = (
        await db.execute(
            text("SELECT pg_get_serial_sequence('aprimora_py.tenant', 'id')")
        )
    ).scalar()
    if seq_tenant:
        stmts.append(
            f"SELECT setval('{seq_tenant}', "
            f"(SELECT COALESCE(MAX(id), 1) FROM aprimora_py.tenant));"
        )
    return stmts


async def _export(args: argparse.Namespace) -> int:
    async with AdminSessionLocal() as db:
        tid, nome = await _resolve_tenant(db, args.tenant)
    async with _sessao_do_tenant(tid) as db:
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        settings = get_settings()
        out_dir = Path(args.out_dir or f"{settings.tenants_storage_root}/{args.tenant}/backups")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"backup_{args.tenant}_{ts}.sql"

        lines: list[str] = [
            f"-- Aprimora backup — tenant '{args.tenant}' (id={tid}) — gerado em {ts} UTC",
            f"-- Nome: {nome}",
            "-- Para restaurar:  psql -U ged_user -d <destino> -f <arquivo>",
            "",
            "BEGIN;",
            "SET session_replication_role = 'replica';  -- pula FK checks",
            "",
        ]

        # 1. Registro do tenant
        lines += await _dump_tenant_row(db, tid)

        total_rows = 0
        # 2. DELETEs idempotentes (na ordem INVERSA — filhos primeiro)
        lines.append("\n-- DELETEs idempotentes (ordem inversa: filhos antes de pais)")
        for schema, table in reversed(TENANTED_TABLES):
            lines.append(
                f'DELETE FROM "{schema}"."{table}" WHERE tenant_id = {tid};'
            )

        # 3. INSERTs (ordem topológica)
        lines.append("\n-- INSERTs (ordem topológica)")
        for schema, table in TENANTED_TABLES:
            qty, stmts = await _dump_table(db, schema, table, tid)
            if qty > 0:
                lines.append(f"\n-- {schema}.{table} ({qty} linha(s))")
                lines.extend(stmts)
                total_rows += qty

        # 4. setval das sequences
        lines.append("\n-- setval para alinhar sequences com max(id)")
        lines.extend(await _dump_sequences(db))

        lines += [
            "",
            "SET session_replication_role = 'origin';",
            "COMMIT;",
            f"-- Total de linhas exportadas: {total_rows}",
        ]

        # ERRO BARULHENTO É REQUISITO, não refinamento. Um backup de zero
        # linhas é sintaticamente válido, passa no `dr-drill` e só se revela
        # inútil no dia do restore. As duas causas plausíveis são contexto de
        # tenant ausente (que o `_sessao_do_tenant` já barra) e grant faltando —
        # e nenhuma das duas se anuncia sozinha. Gravar o arquivo antes de
        # abortar seria pior: ele ficaria no disco parecendo um backup.
        if total_rows == 0 and not getattr(args, "permitir_vazio", False):
            raise SystemExit(
                f"[ERRO] export do tenant '{args.tenant}' (id={tid}) resultou em "
                "ZERO linhas nas tabelas tenanted, e NENHUM arquivo foi gravado. "
                "Tenant recém-provisionado de fato pode estar vazio: nesse caso, "
                "repita com --permitir-vazio. Caso contrário, suspeite de grant "
                "faltando para o papel administrativo."
            )

        out_file.write_text("\n".join(lines), encoding="utf-8")
        size_kb = out_file.stat().st_size / 1024
        print(f"[ok] backup gerado: {out_file}")
        print(f"     tamanho: {size_kb:.1f} KB")
        print(f"     linhas totais: {total_rows}")
        return 0


async def _dr_drill(args: argparse.Namespace) -> int:
    """Export + parse-check + sanity. Não restaura em DB real (só valida o SQL)."""
    rc = await _export(args)
    if rc != 0:
        return rc
    # Valida que o SQL é parseable (statements terminam com `;` ou comentário)
    settings = get_settings()
    backups_dir = Path(args.out_dir or f"{settings.tenants_storage_root}/{args.tenant}/backups")
    latest = max(backups_dir.glob(f"backup_{args.tenant}_*.sql"), key=lambda p: p.stat().st_mtime)
    content = latest.read_text(encoding="utf-8")
    stmts = [s.strip() for s in content.split(";") if s.strip() and not s.strip().startswith("--")]
    print(f"[ok] parsed {len(stmts)} SQL statements")
    if "BEGIN" not in content or "COMMIT" not in content:
        print("[WARN] arquivo sem BEGIN/COMMIT — restore não será atômico")
        return 1
    if "SET session_replication_role = 'replica'" not in content:
        print("[WARN] arquivo sem desligar FKs — restore vai falhar em filhas antes de pais")
        return 1
    print(f"[ok] DR drill PASS — {latest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli.backup", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_stats = sub.add_parser("stats", help="Conta linhas por tabela de um tenant")
    p_stats.add_argument("--tenant", required=True, help="slug do tenant")
    p_stats.set_defaults(fn=_stats)

    p_exp = sub.add_parser("export", help="Gera SQL standalone com dados do tenant")
    p_exp.add_argument("--tenant", required=True, help="slug do tenant")
    p_exp.add_argument("--out-dir", help="Pasta de saída (default: tenants_storage_root/<slug>/backups)")
    p_exp.add_argument(
        "--permitir-vazio",
        action="store_true",
        help="Grava o arquivo mesmo com zero linhas (tenant recém-provisionado)",
    )
    p_exp.set_defaults(fn=_export)

    p_drill = sub.add_parser("dr-drill", help="Export + parse-check (sanity)")
    p_drill.add_argument("--tenant", required=True, help="slug do tenant")
    p_drill.add_argument("--out-dir", help="Pasta de saída (default: tenants_storage_root/<slug>/backups)")
    p_drill.add_argument(
        "--permitir-vazio",
        action="store_true",
        help="Grava o arquivo mesmo com zero linhas (tenant recém-provisionado)",
    )
    p_drill.set_defaults(fn=_dr_drill)

    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())

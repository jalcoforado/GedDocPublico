"""Diagnóstico de permissões por grupo — item 1.0.7 do backlog.

Uso:
    docker exec aprimora-py-backend python -m app.cli.diagnostico_permissoes \\
        --tenant sobral

    # todos os tenants
    docker exec aprimora-py-backend python -m app.cli.diagnostico_permissoes

## Que problema isto resolve

A migration `0074` criou 9 transações (`processo`, `usuario`, `catalogo`,
`assunto`, `manifestante`, `cidade`, `endereco`, `workflow`,
`unidadeTrabalho`) e a fatia F1 gateou 13 endpoints sobre elas. **Nenhuma tem
linha em `utils.grupo_transacao`** — e hoje isso não afeta ninguém, porque
`is_super_usuario` é `nivel.valor == 0`, o ramo de super-usuário lê
`utils.sistema_transacao` e não `grupo_transacao`, e **não existe nenhum grupo
não-SU** (medido na VPS em 2026-08-11: 0 grupos não-SU, e o catálogo
`utils.nivel` só tem `Super Usuario=0`).

O problema aparece no dia em que o primeiro grupo Operacional for criado: quem
o cria concede as transações que conhece, não sabe das 9 da `0074`, e **13
endpoints passam a devolver 403 para aquele grupo sem que nada explique por
quê**. O sintoma é "a tela sumiu para o pessoal do setor X" — a distância entre
esse sintoma e a causa é o que esta CLI encurta.

## O que ela NÃO faz, e é deliberado

**Não concede nada.** Conceder em bloco *abriria* acesso em vez de preservar: as
9 transações são novas, nenhum grupo as tinha, e dar todas a um Operacional lhe
daria poder de excluir processo — que ele nunca teve. Decidir quem passa a poder
o quê, código por código e ação por ação, é política de acesso e decisão do dono
do produto, não de uma migration nem desta CLI. Ver o item 1.0.7 do backlog.

Isto aqui é um espelho, não uma ferramenta de escrita: mostra o que falta, e
quem decide continua sendo quem decide.
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database_admin import AdminSessionLocal

# As 9 da 0074. Não é a lista de "tudo que existe" — é a lista das que a F1
# introduziu e que, por serem novas, nenhum grupo pré-existente podia ter.
TRANSACOES_0074 = (
    "processo",
    "usuario",
    "catalogo",
    "assunto",
    "manifestante",
    "cidade",
    "endereco",
    "workflow",
    "unidadeTrabalho",
)


async def _tenants(db: AsyncSession, slug: str | None) -> list[tuple[int, str]]:
    if slug:
        linhas = (
            await db.execute(
                text(
                    "SELECT id, slug FROM aprimora_py.tenant "
                    "WHERE slug = :s"
                ),
                {"s": slug},
            )
        ).all()
        if not linhas:
            print(f"[erro] tenant '{slug}' não encontrado.", file=sys.stderr)
            raise SystemExit(2)
        return [(int(r[0]), str(r[1])) for r in linhas]
    linhas = (
        await db.execute(
            text(
                "SELECT id, slug FROM aprimora_py.tenant "
                "ORDER BY slug"
            )
        )
    ).all()
    return [(int(r[0]), str(r[1])) for r in linhas]


async def _niveis(db: AsyncSession) -> list[tuple[str, int]]:
    linhas = (
        await db.execute(
            text(
                "SELECT nivel, valor FROM utils.nivel "
                "WHERE excluido = false ORDER BY valor"
            )
        )
    ).all()
    return [(str(r[0]), int(r[1])) for r in linhas]


async def _grupos(db: AsyncSession, tenant_id: int) -> list[tuple[int, str, int]]:
    """Grupos do tenant com o VALOR do nível — 0 é super-usuário."""
    linhas = (
        await db.execute(
            text(
                "SELECT g.id, g.grupo, n.valor "
                "  FROM utils.grupo g "
                "  JOIN utils.nivel n ON n.id = g.id_nivel "
                " WHERE g.tenant_id = :t AND g.excluido = false "
                " ORDER BY n.valor, g.grupo"
            ),
            {"t": tenant_id},
        )
    ).all()
    return [(int(r[0]), str(r[1]), int(r[2])) for r in linhas]


async def _concedidas(db: AsyncSession, grupo_id: int) -> set[str]:
    linhas = (
        await db.execute(
            text(
                "SELECT t.codigo "
                "  FROM utils.grupo_transacao gt "
                "  JOIN utils.transacao t ON t.id = gt.id_transacao "
                " WHERE gt.id_grupo = :g AND gt.excluido = false"
            ),
            {"g": grupo_id},
        )
    ).all()
    return {str(r[0]) for r in linhas}


async def diagnosticar(slug: str | None) -> int:
    """Imprime o relatório. Devolve o código de saída.

    A sessão é aberta DUAS vezes de propósito: sem tenant para o que é global
    (`utils.nivel`, `aprimora_py.tenant` — sem RLS), e uma por tenant com
    `AdminSessionLocal(tenant_id)` para o que é tenanted (`utils.grupo`,
    `utils.grupo_transacao`). Sem a GUC, um papel NOBYPASSRLS lê **zero
    grupos** e o relatório diz "nenhum grupo" com grupos no banco — o pior
    resultado possível numa ferramenta de diagnóstico. A primeira versão desta
    CLI tinha esse defeito e passava no banco de dev porque lá ela conectava
    como `ged_user`; só o CI, onde `MIGRATOR_DATABASE_URL` aponta mesmo para
    `aprimora_migrator`, reprovou.
    """
    async with AdminSessionLocal() as db:
        niveis = await _niveis(db)
        tem_nao_su = any(valor != 0 for _, valor in niveis)

        print("=" * 68)
        print("Diagnóstico de permissões por grupo (item 1.0.7)")
        print("=" * 68)
        print()
        print("Níveis no catálogo (`utils.nivel`):")
        for nome, valor in niveis:
            marca = "  ← super-usuário" if valor == 0 else ""
            print(f"  - {nome} (valor {valor}){marca}")
        if not tem_nao_su:
            print()
            print(
                "  ⚠ Só existe o nível de super-usuário. Nenhum grupo pode ser\n"
                "    não-SU antes de alguém criar um nível com valor <> 0 —\n"
                "    é o passo ANTES de escolher transações, e é fácil esquecer\n"
                "    que ele existe."
            )
        print()

        alvos = await _tenants(db, slug)

    achou_lacuna = False
    for tenant_id, tenant_slug in alvos:
        # Sessão POR TENANT, com a GUC instalada — ver o docstring acima.
        async with AdminSessionLocal(tenant_id) as db_t:
            grupos = await _grupos(db_t, tenant_id)
            print(f"Tenant `{tenant_slug}` — {len(grupos)} grupo(s)")
            if not grupos:
                print("  (nenhum grupo)")
                print()
                continue

            for grupo_id, nome, valor in grupos:
                if valor == 0:
                    print(
                        f"  • {nome} (nível {valor}) — SUPER-USUÁRIO: "
                        "passa por `sistema_transacao`, não por `grupo_transacao`. "
                        "Nada a conferir."
                    )
                    continue

                concedidas = await _concedidas(db_t, grupo_id)
                faltando = [c for c in TRANSACOES_0074 if c not in concedidas]
                if faltando:
                    achou_lacuna = True
                    print(f"  • {nome} (nível {valor}) — NÃO-SU")
                    print(
                        f"    Faltam {len(faltando)} das 9 transações da 0074: "
                        + ", ".join(faltando)
                    )
                    print(
                        "    Efeito: os endpoints gateados nesses códigos devolvem "
                        "403 para este grupo."
                    )
                else:
                    print(
                        f"  • {nome} (nível {valor}) — NÃO-SU: tem as 9 da 0074."
                    )
            print()

    if achou_lacuna:
        print(
            "Há grupo não-SU sem as transações da 0074. Isso NÃO é\n"
            "necessariamente erro — pode ser exatamente a política desejada.\n"
            "Conceder é decisão de quem define o acesso; esta CLI só mostra."
        )
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Mostra, por grupo não-super-usuário, quais das 9 transações da "
            "migration 0074 não estão concedidas. Não concede nada."
        )
    )
    p.add_argument(
        "--tenant",
        help="slug do tenant. Omitido, percorre todos.",
        default=None,
    )
    args = p.parse_args()

    # `AdminSessionLocal` e não `SessionLocal`: CLI administrativa usa o papel
    # do migrator por convenção do projeto (ver `app/database_admin.py` e a
    # seção de papéis de banco no CLAUDE.md). O papel da API não tem o que
    # precisa aqui e não deve ser usado por CLI.
    raise SystemExit(asyncio.run(diagnosticar(args.tenant)))


if __name__ == "__main__":
    main()

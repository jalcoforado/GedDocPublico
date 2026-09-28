"""Script para remover o sistema órfão 'aprimora' e seus grupos atrelados (Item 1.0 do backlog).

Uso (dry-run):
    docker exec aprimora-py-backend python -m app.cli.limpar_sistema_orfao

Uso (apagar de fato):
    docker exec aprimora-py-backend python -m app.cli.limpar_sistema_orfao --apagar
"""
import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..database_admin import AdminSessionLocal


async def limpar_sistema_aprimora(db: AsyncSession, apagar: bool) -> None:
    # 1. Encontrar o id do sistema "aprimora"
    result = await db.execute(text("SELECT id FROM utils.sistema WHERE app = 'aprimora'"))
    row = result.first()
    if not row:
        print("Sistema 'aprimora' não encontrado. Nada a fazer.")
        return
    id_sistema = row[0]
    print(f"Sistema 'aprimora' encontrado com id: {id_sistema}")

    # 2. Encontrar os grupos associados
    result_grupos = await db.execute(
        text("SELECT id, grupo FROM utils.grupo WHERE id_sistema = :sid"),
        {"sid": id_sistema}
    )
    grupos = result_grupos.all()
    print(f"Encontrados {len(grupos)} grupo(s) associado(s) ao sistema:")
    for g in grupos:
        print(f"  - id {g[0]}: {g[1]}")
    
    ids_grupos = [g[0] for g in grupos]

    if not apagar:
        print("\n[DRY RUN] O que seria apagado:")
        print(" - Linhas em utils.grupo_transacao associadas aos grupos acima")
        print(" - Linhas em utils.usuario_grupo associadas aos grupos acima")
        print(f" - {len(grupos)} linha(s) em utils.grupo (id_sistema = {id_sistema})")
        print(f" - Linhas em utils.sistema_transacao para o id_sistema = {id_sistema}")
        print(f" - 1 linha em utils.sistema (id = {id_sistema})")
        print("\nRode com --apagar para efetivar.")
        return

    print("\nExecutando exclusões...")
    
    if ids_grupos:
        # Excluir dependências dos grupos
        await db.execute(
            text("DELETE FROM utils.grupo_transacao WHERE id_grupo = ANY(:gids)"),
            {"gids": ids_grupos}
        )
        await db.execute(
            text("DELETE FROM utils.usuario_grupo WHERE id_grupo = ANY(:gids)"),
            {"gids": ids_grupos}
        )
        
        # Excluir os grupos
        await db.execute(
            text("DELETE FROM utils.grupo WHERE id_sistema = :sid"),
            {"sid": id_sistema}
        )

    # Excluir sistema_transacao
    await db.execute(
        text("DELETE FROM utils.sistema_transacao WHERE id_sistema = :sid"),
        {"sid": id_sistema}
    )

    # Excluir o sistema
    await db.execute(
        text("DELETE FROM utils.sistema WHERE id = :sid"),
        {"sid": id_sistema}
    )

    await db.commit()
    print("Limpeza concluída com sucesso.")


async def main() -> None:
    p = argparse.ArgumentParser(description="Limpa o sistema órfão 'aprimora' e grupos associados.")
    p.add_argument("--apagar", action="store_true", help="Efetua a exclusão no banco (padrão é dry-run).")
    args = p.parse_args()

    async with AdminSessionLocal() as db:
        await limpar_sistema_aprimora(db, apagar=args.apagar)


if __name__ == "__main__":
    asyncio.run(main())

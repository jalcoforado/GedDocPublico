"""Mirrors Positiv\\Usuario::permissions() in aprimora/app/models/Usuario.php.

Rules:
- Find the user's groups for the current APP (filter usuario_grupo + grupo.sistema.app == APP).
- The user's "highest level" is the group with the lowest `nivel.valor` (0 = Super Usuário).
- If isSU: return all transactions of the user's sistema (via sistema_transacao) with full perms.
- Otherwise: union of grupo_transacao across the user's groups for this APP.

Módulo não contratado: transações de módulo que o tenant não contratou são
descartadas de `items` e listadas em `codigos_bloqueados` — para QUALQUER
usuário, inclusive super-usuário. Contratação é ato de plataforma, não de
permissão; por isso o gate correspondente em `auth/perms.py` roda antes do
bypass de SU, não depois.
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import (
    Grupo,
    GrupoTransacao,
    Nivel,
    Sistema,
    SistemaTransacao,
    Transacao,
    UsuarioGrupo,
)
from .modulos import codigos_bloqueados


@dataclass
class PermItem:
    codigo: str
    transacao: str
    inserir: bool
    atualizar: bool
    excluir: bool


@dataclass
class UserPermissions:
    is_super_usuario: bool
    nivel_valor: int | None
    items: list[PermItem]
    # Códigos de transação de módulo não contratado pelo tenant. Vive aqui
    # para que `require_permission` possa barrar ANTES do bypass de
    # super-usuário, sem pagar uma segunda consulta.
    codigos_bloqueados: frozenset[str] = frozenset()


async def load_permissions(
    db: AsyncSession, usuario_id: int, *, tenant_id: int
) -> UserPermissions:
    settings = get_settings()
    app = settings.app_name

    # Set RLS context for this transaction
    from sqlalchemy import text
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))

    grupos_stmt = (
        select(Grupo, Nivel, Sistema)
        .join(UsuarioGrupo, UsuarioGrupo.id_grupo == Grupo.id)
        .join(Nivel, Nivel.id == Grupo.id_nivel)
        .join(Sistema, Sistema.id == Grupo.id_sistema)
        .where(
            UsuarioGrupo.id_usuario == usuario_id,
            UsuarioGrupo.tenant_id == tenant_id,
            UsuarioGrupo.excluido.is_(False),
            UsuarioGrupo.ativo.is_(True),
            Grupo.tenant_id == tenant_id,
            Grupo.excluido.is_(False),
            Sistema.excluido.is_(False),
            Sistema.app == app,
        )
    )
    rows = (await db.execute(grupos_stmt)).all()

    if not rows:
        bloqueados = await codigos_bloqueados(db, tenant_id)
        return UserPermissions(
            is_super_usuario=False,
            nivel_valor=None,
            items=[],
            codigos_bloqueados=frozenset(bloqueados),
        )

    rows.sort(key=lambda r: r[1].valor)
    higher_grupo, higher_nivel, higher_sistema = rows[0]
    is_su = higher_nivel.valor == 0

    if is_su:
        stmt = (
            select(Transacao)
            .join(SistemaTransacao, SistemaTransacao.id_transacao == Transacao.id)
            .where(
                SistemaTransacao.id_sistema == higher_sistema.id,
                SistemaTransacao.excluido.is_(False),
                Transacao.excluido.is_(False),
            )
        )
        transacoes = (await db.execute(stmt)).scalars().all()
        items = [
            PermItem(
                codigo=t.codigo,
                transacao=t.transacao,
                inserir=True,
                atualizar=True,
                excluir=True,
            )
            for t in transacoes
        ]
    else:
        grupo_ids = [g.id for g, _, _ in rows]
        stmt = (
            select(Transacao, GrupoTransacao)
            .join(GrupoTransacao, GrupoTransacao.id_transacao == Transacao.id)
            .where(
                GrupoTransacao.id_grupo.in_(grupo_ids),
                GrupoTransacao.tenant_id == tenant_id,
                GrupoTransacao.excluido.is_(False),
                Transacao.excluido.is_(False),
            )
        )
        merged: dict[str, PermItem] = {}
        for transacao, gt in (await db.execute(stmt)).all():
            existing = merged.get(transacao.codigo)
            if existing:
                existing.inserir = existing.inserir or gt.inserir
                existing.atualizar = existing.atualizar or gt.atualizar
                existing.excluir = existing.excluir or gt.excluir
            else:
                merged[transacao.codigo] = PermItem(
                    codigo=transacao.codigo,
                    transacao=transacao.transacao,
                    inserir=gt.inserir,
                    atualizar=gt.atualizar,
                    excluir=gt.excluir,
                )
        items = sorted(merged.values(), key=lambda p: p.codigo)

    bloqueados = await codigos_bloqueados(db, tenant_id)
    if bloqueados:
        items = [p for p in items if p.codigo not in bloqueados]

    return UserPermissions(
        is_super_usuario=is_su,
        nivel_valor=higher_nivel.valor,
        items=items,
        codigos_bloqueados=frozenset(bloqueados),
    )

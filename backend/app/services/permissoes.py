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

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import (
    Grupo,
    GrupoTransacao,
    Nivel,
    Sistema,
    SistemaTransacao,
    Transacao,
    Usuario,
    UsuarioGrupo,
    UsuarioUnidadeTrabalho,
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
    db: AsyncSession,
    usuario_id: int,
    *,
    tenant_id: int,
    id_unidade_contexto: int | None = None,
) -> UserPermissions:
    """`id_unidade_contexto` é a lotação ATIVA da sessão (E1, benchmark SUiTE).

    Vínculo `UsuarioGrupo` com `id_unidade_trabalho` nulo é global (conta
    sempre); com a coluna preenchida, só conta quando bater com
    `id_unidade_contexto`. É união dos dois eixos, não interseção — decidido
    em `docs/superpowers/plans/2026-09-16-aproveitamento-suite.md` §6 Q1.
    `id_unidade_contexto=None` (default) devolve só o que sempre existiu:
    nenhuma chamada existente precisa mudar para continuar byte a byte igual.
    """
    settings = get_settings()
    app = settings.app_name

    # Set RLS context for this transaction
    from sqlalchemy import text
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))

    if id_unidade_contexto is not None:
        escopo_lotacao = or_(
            UsuarioGrupo.id_unidade_trabalho.is_(None),
            UsuarioGrupo.id_unidade_trabalho == id_unidade_contexto,
        )
    else:
        escopo_lotacao = UsuarioGrupo.id_unidade_trabalho.is_(None)

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
            escopo_lotacao,
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


@dataclass
class LotacaoItem:
    id: int
    nome: str
    principal: bool


async def listar_lotacoes(
    db: AsyncSession, *, tenant_id: int, usuario: Usuario
) -> list[LotacaoItem]:
    """Lotação principal + secundárias do usuário — o par que a captura 38 do
    SUiTE mostra (E1, benchmark SUiTE). Alimenta o seletor de contexto ativo
    ("alterar setor"): `POST /auth/lotacao-ativa` só aceita trocar para uma
    lotação desta lista.

    `usuario.id_unidade_trabalho` é a principal (fixa, cadastral);
    `utils.usuario_unidade_trabalho` são as secundárias (N:N, já existente —
    não duplicada aqui). Unidade excluída/de outro tenant nunca aparece.
    """
    from ..models import UnidadeTrabalho

    ids_ordem: list[tuple[int, bool]] = []
    if usuario.id_unidade_trabalho is not None:
        ids_ordem.append((usuario.id_unidade_trabalho, True))

    secundarias_stmt = select(UsuarioUnidadeTrabalho.id_unidade_trabalho).where(
        UsuarioUnidadeTrabalho.id_usuario == usuario.id,
        UsuarioUnidadeTrabalho.tenant_id == tenant_id,
        UsuarioUnidadeTrabalho.excluido.is_(False),
    )
    for uid in (await db.execute(secundarias_stmt)).scalars().all():
        if uid != usuario.id_unidade_trabalho:
            ids_ordem.append((uid, False))

    if not ids_ordem:
        return []

    nomes_stmt = select(UnidadeTrabalho.id, UnidadeTrabalho.unidade_trabalho).where(
        UnidadeTrabalho.id.in_([uid for uid, _ in ids_ordem]),
        UnidadeTrabalho.tenant_id == tenant_id,
        UnidadeTrabalho.excluido.is_(False),
    )
    nomes = dict((await db.execute(nomes_stmt)).all())

    return [
        LotacaoItem(id=uid, nome=nomes[uid], principal=principal)
        for uid, principal in ids_ordem
        if uid in nomes
    ]

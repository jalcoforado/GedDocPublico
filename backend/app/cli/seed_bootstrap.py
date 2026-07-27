"""Seed mínimo de bootstrap — sistema logável com todos os módulos.

Idempotente. Cria (get_or_create):
  1. Catálogo global: utils.sistema(app=settings.app_name) + utils.nivel(valor=0)
  2. Tenant Sobral (aprimora_py.tenant, id=1) — 0003 é pulada pelo baseline 0020
  3. Admin super-usuário admin@local.test (senha dev admin123)
  4. utils.grupo (nível 0, sistema do app_name) + utils.usuario_grupo (tenant 1)
  5. Segredo KEY_LOGIN_GLOBAL_JWT em utils.sistema_constante

Uso: docker exec aprimora-py-backend python -m app.cli.seed_bootstrap
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_password
from ..config import get_settings
from ..database import SessionLocal
from ..models import Grupo, Nivel, Sistema, Tenant, Usuario, UsuarioGrupo

APP = get_settings().app_name

ADMIN_EMAIL = "admin@local.test"
ADMIN_SENHA = "admin123"
TENANT_SLUG = "sobral"


async def _set_local_tenant(db: AsyncSession, tenant_id: int) -> None:
    await db.execute(text(f"SET LOCAL app.tenant_id = {int(tenant_id)}"))


async def seed(db: AsyncSession) -> dict:
    # 1. Catálogo global (sistema app=aprimora + nível 0). O stub
    # sistema_chamados.tipo_chamado (Task 1) deixa o trigger legado passar.
    sistema = (
        await db.execute(select(Sistema).where(Sistema.app == APP))
    ).scalars().first()
    if sistema is None:
        sistema = Sistema(sistema="Aprimora", app=APP, url="/", excluido=False)
        db.add(sistema)
        await db.flush()

    nivel = (
        await db.execute(select(Nivel).where(Nivel.valor == 0))
    ).scalars().first()
    if nivel is None:
        nivel = Nivel(nivel="Super Usuario", valor=0, excluido=False)
        db.add(nivel)
        await db.flush()

    # 2. Tenant Sobral
    tenant = (
        await db.execute(select(Tenant).where(Tenant.slug == TENANT_SLUG))
    ).scalars().first()
    if tenant is None:
        tenant = Tenant(
            slug=TENANT_SLUG,
            nome="Prefeitura de Sobral",
            plano="basico",
            ativo=True,
            # Tenant.criado_em é TIMESTAMP WITHOUT TIME ZONE — usar UTC naive
            # (aware quebra o insert asyncpg num DB fresco: "offset-naive and
            # offset-aware datetimes").
            criado_em=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(tenant)
        await db.flush()
    tenant_id = tenant.id

    await _set_local_tenant(db, tenant_id)

    # 3. Admin super-usuário
    usuario = (
        await db.execute(
            select(Usuario).where(
                Usuario.email == ADMIN_EMAIL, Usuario.tenant_id == tenant_id
            )
        )
    ).scalars().first()
    if usuario is None:
        usuario = Usuario(
            tenant_id=tenant_id,
            nome="Admin Sobral",
            email=ADMIN_EMAIL,
            senha="",
            senha_bcrypt=hash_password(ADMIN_SENHA),
            cpf="00000000000",
            ativo=True,
            excluido=False,
            app=APP,
            nivel_acesso_sigilo="interno",
            must_change_password=False,
        )
        db.add(usuario)
        await db.flush()

    # 4. Grupo SU + vínculo
    grupo = (
        await db.execute(
            select(Grupo).where(
                Grupo.tenant_id == tenant_id,
                Grupo.id_nivel == nivel.id,
                Grupo.id_sistema == sistema.id,
            )
        )
    ).scalars().first()
    if grupo is None:
        grupo = Grupo(
            id_nivel=nivel.id,
            id_sistema=sistema.id,
            grupo="Administradores",
            tenant_id=tenant_id,
            excluido=False,
        )
        db.add(grupo)
        await db.flush()

    vinculo = (
        await db.execute(
            select(UsuarioGrupo).where(
                UsuarioGrupo.id_usuario == usuario.id,
                UsuarioGrupo.id_grupo == grupo.id,
            )
        )
    ).scalars().first()
    if vinculo is None:
        db.add(
            UsuarioGrupo(
                id_usuario=usuario.id,
                id_grupo=grupo.id,
                tenant_id=tenant_id,
                ativo=True,
                excluido=False,
            )
        )

    # 5. Segredo JWT
    jwt_exists = (
        await db.execute(
            text(
                "SELECT 1 FROM utils.sistema_constante "
                "WHERE constante='KEY_LOGIN_GLOBAL_JWT' LIMIT 1"
            )
        )
    ).first()
    if jwt_exists is None:
        await db.execute(
            text(
                "INSERT INTO utils.sistema_constante (constante, valor_padrao, excluido) "
                "VALUES ('KEY_LOGIN_GLOBAL_JWT', :v, false)"
            ),
            {"v": secrets.token_urlsafe(48)},
        )

    return {"tenant_id": tenant_id, "usuario_id": usuario.id, "is_super": True}


async def _main() -> int:
    async with SessionLocal() as db:
        res = await seed(db)
        await db.commit()
    print(f"[seed_bootstrap] OK: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

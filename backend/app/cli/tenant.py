"""CLI para administração de tenants — Fase 15.

Uso:
    docker exec aprimora-py-backend python -m app.cli.tenant create \\
        --slug fortaleza --nome "Prefeitura de Fortaleza" \\
        --cnpj 07954605000160 --cor "#0055aa"

    docker exec aprimora-py-backend python -m app.cli.tenant list

    docker exec aprimora-py-backend python -m app.cli.tenant deactivate fortaleza
    docker exec aprimora-py-backend python -m app.cli.tenant activate fortaleza

Endpoint admin (`POST /api/v2/tenants`) fica para fase futura — onboarding hoje
é manual via dev. Cria-se tenant + super-usuário admin do tenant + unidade
proprietária default + tipos catálogo mínimos.
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.password import hash_md5, hash_password
from ..database import SessionLocal
from ..models import (
    Acao,
    Grupo,
    Nivel,
    Sistema,
    Tenant,
    TipoManifestante,
    TipoUnidadeTrabalho,
    UnidadeTrabalho,
    Usuario,
    UsuarioGrupo,
)


async def _create(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        # Verifica unicidade do slug
        existe = (
            await db.execute(select(Tenant).where(Tenant.slug == args.slug))
        ).scalar_one_or_none()
        if existe is not None:
            print(f"[ERRO] Slug '{args.slug}' já existe (tenant id={existe.id})")
            return 1

        # Cria tenant
        tenant = Tenant(
            slug=args.slug,
            nome=args.nome,
            cnpj=args.cnpj,
            id_cidade=args.id_cidade,
            plano=args.plano,
            cor_primaria=args.cor,
            logo_url=args.logo,
            ativo=True,
            criado_em=datetime.utcnow(),
        )
        db.add(tenant)
        await db.flush()
        print(f"[ok] tenant criado: id={tenant.id} slug={tenant.slug}")

        # Cria tipo unidade default + unidade
        tu = TipoUnidadeTrabalho(
            tenant_id=tenant.id, tipo_unidade_trabalho="Secretaria", codigo="SEC"
        )
        db.add(tu)
        await db.flush()
        unidade = UnidadeTrabalho(
            tenant_id=tenant.id,
            unidade_trabalho="Protocolo Geral",
            sigla="PG",
            id_tipo_unidade_trabalho=tu.id,
        )
        db.add(unidade)
        await db.flush()
        print(f"[ok] unidade default: id={unidade.id} 'Protocolo Geral'")

        # Cria tipo manifestante default
        tm = TipoManifestante(
            tenant_id=tenant.id,
            tipo_manifestante="Pessoa Física",
            id_categoria=1,
            ativo=True,
        )
        db.add(tm)
        await db.flush()
        print(f"[ok] tipo manifestante default: id={tm.id}")

        # Cria super-usuário admin
        senha_plain = args.senha or secrets.token_urlsafe(12)
        usuario = Usuario(
            tenant_id=tenant.id,
            nome=args.admin_nome,
            email=args.admin_email,
            cpf=args.admin_cpf,
            senha=hash_md5(senha_plain),
            senha_bcrypt=hash_password(senha_plain),
            id_unidade_trabalho=unidade.id,
            ativo=True,
            excluido=False,
            cargo="Administrador",
            app="sistemas",
        )
        db.add(usuario)
        await db.flush()
        print(f"[ok] usuário admin: id={usuario.id} email={usuario.email}")

        # Cria grupo Super Usuário (nivel.valor=0) atrelado ao usuário
        nivel_su = (
            await db.execute(select(Nivel).where(Nivel.valor == 0).limit(1))
        ).scalar_one_or_none()
        sistema_app = (
            await db.execute(select(Sistema).where(Sistema.app == "sistemas").limit(1))
        ).scalar_one_or_none()
        if nivel_su and sistema_app:
            grupo_su = Grupo(
                tenant_id=tenant.id,
                id_nivel=nivel_su.id,
                id_sistema=sistema_app.id,
                grupo="Super Usuário",
                excluido=False,
            )
            db.add(grupo_su)
            await db.flush()
            db.add(
                UsuarioGrupo(
                    tenant_id=tenant.id,
                    id_usuario=usuario.id,
                    id_grupo=grupo_su.id,
                    ativo=True,
                    excluido=False,
                    app="sistemas",
                )
            )
            await db.flush()
            print(f"[ok] grupo SU + vínculo")
        else:
            print(f"[warn] não foi possível atrelar nível SU (nivel ou sistema 'sistemas' não encontrados)")

        await db.commit()

        print()
        print("=" * 60)
        print(f"TENANT CRIADO COM SUCESSO")
        print("=" * 60)
        print(f"  ID:           {tenant.id}")
        print(f"  Slug:         {tenant.slug}")
        print(f"  Subdomain:    {tenant.slug}.aprimora.app (prod) / {tenant.slug}.aprimora.local (dev)")
        print(f"  Admin email:  {usuario.email}")
        print(f"  Admin senha:  {senha_plain}")
        print(f"  CNPJ:         {tenant.cnpj or '(não informado)'}")
        print(f"  Plano:        {tenant.plano}")
        print(f"  Cor:          {tenant.cor_primaria or '(default)'}")
        print("=" * 60)
        return 0


async def _list(_: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        rows = (
            await db.execute(
                select(Tenant).order_by(Tenant.id)
            )
        ).scalars().all()
        print(f"{'ID':4}  {'Slug':20}  {'Nome':40}  {'Plano':14}  {'Ativo'}")
        print("-" * 92)
        for t in rows:
            print(
                f"{t.id:4}  {t.slug:20}  {t.nome[:40]:40}  "
                f"{t.plano:14}  {'sim' if t.ativo else 'NÃO'}"
            )
        return 0


async def _set_active(args: argparse.Namespace, active: bool) -> int:
    async with SessionLocal() as db:
        tenant = (
            await db.execute(select(Tenant).where(Tenant.slug == args.slug))
        ).scalar_one_or_none()
        if tenant is None:
            print(f"[ERRO] tenant '{args.slug}' não encontrado")
            return 1
        tenant.ativo = active
        tenant.atualizado_em = datetime.utcnow()
        await db.commit()
        print(f"[ok] tenant {args.slug}: ativo={active}")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli.tenant", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create", help="Cria um novo tenant + admin inicial")
    p_create.add_argument("--slug", required=True, help="ex.: fortaleza")
    p_create.add_argument("--nome", required=True, help='ex.: "Prefeitura de Fortaleza"')
    p_create.add_argument("--cnpj", help="CNPJ sem formatação (14 dígitos)")
    p_create.add_argument("--id-cidade", type=int, help="ID da cidade em utils.cidade")
    p_create.add_argument("--plano", default="basico", choices=["basico", "profissional", "enterprise"])
    p_create.add_argument("--cor", help="Cor primária #RRGGBB para branding")
    p_create.add_argument("--logo", help="URL do logo para branding")
    p_create.add_argument("--admin-nome", default="Administrador")
    p_create.add_argument("--admin-email", required=True, help="Email do super-usuário inicial")
    p_create.add_argument("--admin-cpf", required=True, help="CPF do super-usuário (11 dígitos)")
    p_create.add_argument("--senha", help="Senha do admin (gerada se omitido)")
    p_create.set_defaults(fn=_create)

    p_list = sub.add_parser("list", help="Lista tenants existentes")
    p_list.set_defaults(fn=_list)

    p_deact = sub.add_parser("deactivate", help="Desativa um tenant (impede login)")
    p_deact.add_argument("slug")
    p_deact.set_defaults(fn=lambda a: _set_active(a, False))

    p_act = sub.add_parser("activate", help="Reativa um tenant")
    p_act.add_argument("slug")
    p_act.set_defaults(fn=lambda a: _set_active(a, True))

    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())

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
import sys
from datetime import datetime

from sqlalchemy import select

from ..database import SessionLocal
from ..models import Tenant
from ..services.provisioning_tenant import ProvisioningError, provisionar_tenant


async def _create(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        try:
            tenant, senha_plain = await provisionar_tenant(
                db,
                slug=args.slug,
                nome=args.nome,
                cnpj=args.cnpj,
                id_cidade=args.id_cidade,
                plano=args.plano,
                cor_primaria=args.cor,
                logo_url=args.logo,
                admin_email=args.admin_email,
                admin_nome=args.admin_nome,
                admin_cpf=args.admin_cpf,
                senha=args.senha,
                modulos=(
                    [s.strip() for s in args.modulos.split(",") if s.strip()]
                    if args.modulos is not None
                    else None
                ),
            )
        except ProvisioningError as e:
            print(f"[ERRO] {e}")
            return 1

    print()
    print("=" * 60)
    print("TENANT CRIADO COM SUCESSO")
    print("=" * 60)
    print(f"  ID:           {tenant.id}")
    print(f"  Slug:         {tenant.slug}")
    print(f"  Subdomain:    {tenant.slug}.aprimora.app (prod) / {tenant.slug}.aprimora.local (dev)")
    print(f"  Admin email:  {args.admin_email}")
    print(f"  Admin senha:  {senha_plain}   <-- exibida só agora; troque após o 1º acesso")
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
    p_create.add_argument(
        "--modulos",
        default=None,
        help="Lista separada por vírgula (ex.: protocolo,frota). Default: todos.",
    )
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

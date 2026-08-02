"""CLI para administração de tenants — Fase 15.

Uso:
    docker exec aprimora-py-backend python -m app.cli.tenant create \\
        --slug fortaleza --nome "Prefeitura de Fortaleza" \\
        --cnpj 07954605000160 --cor "#0055aa"

    docker exec aprimora-py-backend python -m app.cli.tenant list

    docker exec aprimora-py-backend python -m app.cli.tenant deactivate fortaleza
    docker exec aprimora-py-backend python -m app.cli.tenant activate fortaleza

    # provisionamento que ficou pelo meio (tenant inerte) — ver `retomar`
    docker exec aprimora-py-backend python -m app.cli.tenant retomar \\
        --slug fortaleza --admin-email admin@fortaleza.gov.br --admin-cpf 12345678901

Endpoint admin (`POST /api/v2/tenants`) fica para fase futura — onboarding hoje
é manual via dev. Cria-se tenant + super-usuário admin do tenant + unidade
proprietária default + tipos catálogo mínimos.

Desde `SEC-RLS-00C` o provisionamento são **dois atos** com papéis de banco
distintos (ver `services/provisioning_tenant.py`). Esta CLI abre a sessão de
plataforma por `PLATFORM_DB_URL` quando ela existe; quando não existe, avisa e
segue com a credencial administrativa desta CLI para os dois atos — o que só
funciona porque essa credencial é administrativa. Sob `aprimora_app` o ato de
plataforma falha alto com `permission denied`, e é assim que tem de ser.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import SessionLocal
from ..database_plataforma import (
    descartar_engines_plataforma,
    sessao_plataforma,
)
from ..models import Tenant
from ..services.provisioning_tenant import (
    ProvisioningError,
    provisionar_tenant,
    retomar_provisionamento,
)


@asynccontextmanager
async def _sessao_do_ato_de_plataforma() -> AsyncIterator[AsyncSession | None]:
    """Sessão do papel `aprimora_platform`, ou `None` quando não configurada.

    `None` faz o serviço rodar os três atos na mesma sessão. **Não é contorno
    da fronteira**: a fronteira é o `GRANT`, e depois da 0079 `aprimora_app` não
    tem `INSERT` em `tenant`/`tenant_modulo` — cair aqui com a credencial da API
    dá `permission denied` na hora. O aviso existe para que a ausência da
    configuração seja uma escolha visível, e não um silêncio.
    """
    if get_settings().platform_db_url.strip():
        async with sessao_plataforma() as sessao:
            try:
                yield sessao
            finally:
                await descartar_engines_plataforma()
        return
    print(
        "[aviso] PLATFORM_DB_URL não configurada: o ato de PLATAFORMA vai rodar "
        "na mesma credencial administrativa desta CLI, e não em "
        "`aprimora_platform`. Configure-a para separar os papéis "
        "(docs/runbooks/platform-operator-bootstrap.md §1)."
    )
    yield None


async def _create(args: argparse.Namespace) -> int:
    async with SessionLocal() as db, _sessao_do_ato_de_plataforma() as db_plat:
        try:
            tenant, senha_plain = await provisionar_tenant(
                db,
                db_plataforma=db_plat,
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


async def _retomar(args: argparse.Namespace) -> int:
    """Conclui um provisionamento que parou entre os dois atos.

    Cenário: o ato de plataforma comitou (o tenant existe) e o ato municipal
    falhou. O tenant ficou `ativo = false` — inerte, sem resolver por
    subdomínio. Isto reexecuta o ato municipal, que é idempotente, e ativa.

    **Recusa tenant que já foi provisionado** — a guarda é "tem algum usuário",
    não "está inativo", e a diferença é de segurança, não de estilo: município
    SUSPENSO de propósito (por `deactivate`, logo abaixo neste mesmo parser)
    também está inativo, e retomá-lo criaria nele um super-usuário novo e
    desfaria a suspensão. Ver `_exigir_provisionamento_nunca_concluido`.

    Para reativar município suspenso o comando é `activate`, que não toca em
    usuário nenhum — vale também quando só a ativação tiver falhado.
    """
    async with SessionLocal() as db, _sessao_do_ato_de_plataforma() as db_plat:
        try:
            tenant, senha_plain = await retomar_provisionamento(
                db,
                db_plataforma=db_plat,
                slug=args.slug,
                admin_email=args.admin_email,
                admin_nome=args.admin_nome,
                admin_cpf=args.admin_cpf,
                senha=args.senha,
            )
        except ProvisioningError as e:
            print(f"[ERRO] {e}")
            return 1

    print()
    print("=" * 60)
    print("PROVISIONAMENTO RETOMADO")
    print("=" * 60)
    print(f"  ID:           {tenant.id}")
    print(f"  Slug:         {tenant.slug}")
    print(f"  Ativo:        {'sim' if tenant.ativo else 'NÃO'}")
    print(f"  Admin email:  {args.admin_email}")
    if senha_plain is None:
        print("  Admin senha:  (o usuário já existia — senha PRESERVADA)")
    else:
        print(f"  Admin senha:  {senha_plain}   <-- exibida só agora")
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

    p_retomar = sub.add_parser(
        "retomar",
        help="Conclui provisionamento parado entre os dois atos (tenant inerte)",
    )
    p_retomar.add_argument("--slug", required=True, help="Slug do tenant inerte")
    p_retomar.add_argument("--admin-nome", default="Administrador")
    p_retomar.add_argument("--admin-email", required=True)
    p_retomar.add_argument("--admin-cpf", required=True)
    p_retomar.add_argument(
        "--senha",
        help="Senha do admin (gerada se omitido). Ignorada se o admin já existir.",
    )
    p_retomar.set_defaults(fn=_retomar)

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

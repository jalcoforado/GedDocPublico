"""CLI de bootstrap e operação do principal de plataforma — SEC-01A.

Contrato operacional: `docs/runbooks/platform-operator-bootstrap.md`. Os
comandos e as flags abaixo são exatamente os que o runbook documenta — divergir
quebraria copiar-e-colar durante incidente, que é quando esta CLI é usada.

    # bootstrap / concessão (runbook §2 e §3)
    python -m app.cli.platform_principal criar \\
        --issuer "<iss>" --subject "<sub>" \\
        --display-label "<e-mail, apenas rótulo>" \\
        --reason "bootstrap inicial — <ticket>" \\
        --approved-by "<quem testemunhou>"

    # revogação (runbook §4)
    python -m app.cli.platform_principal revogar \\
        --issuer "<iss>" --subject "<sub>" \\
        --reason "<motivo>" --revoked-by "<quem>"

    # break-glass (runbook §5)
    python -m app.cli.platform_principal break-glass \\
        --principal "<id>" --minutes 60 --reason "<incidente>" \\
        --approved-by "<pessoa 1>" --approved-by "<pessoa 2>"
    python -m app.cli.platform_principal break-glass encerrar --principal "<id>"

**Flags em inglês, mensagens em pt-BR** (decisão D-c do brief): as flags são
termos do protocolo OIDC e do contrato do runbook; o resto segue a convenção do
repositório.

**Por que não `SessionLocal`.** `database.SessionLocal` usa o engine municipal
(`DATABASE_URL`, hoje `ged_user`/SUPERUSER). O runbook §2 passo 5 é explícito:
se o papel `aprimora_platform` não existir, **parar e aplicar a migration**, não
contornar com `ged_user`. Por isso esta CLI abre a conexão por `PLATFORM_DB_URL`
e falha com instrução quando ela não existe.

Nenhum operador real entra em código ou seed (ADR §10, Q-2): a lista de
principals é construída por esta CLI, ambiente a ambiente.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta

from sqlalchemy import select

from ..config import get_settings
from ..database_plataforma import descartar_engines_plataforma, sessao_plataforma
from ..models import PlatformAuditLog, PlatformPrincipal

# ADR §2.8: a janela de break-glass é de 60 minutos e não é renovável.
MINUTOS_MAXIMOS_BREAK_GLASS = 60


def _erro(mensagem: str) -> int:
    print(f"[ERRO] {mensagem}")
    return 1


async def _trilha(
    db,
    *,
    principal: PlatformPrincipal,
    acao: str,
    detalhe: dict,
) -> None:
    """Toda mutação feita por CLI entra na trilha autoritativa. Operação de
    plataforma sem registro é pior do que operação recusada."""
    db.add(
        PlatformAuditLog(
            platform_principal_id=principal.id,
            issuer=principal.issuer,
            subject=principal.subject,
            acao=acao,
            tenant_alvo_id=None,
            detalhe=detalhe,
            correlation_id=None,
            criado_em=datetime.utcnow(),
        )
    )


async def _por_chave_natural(db, issuer: str, subject: str) -> PlatformPrincipal | None:
    return (
        await db.execute(
            select(PlatformPrincipal).where(
                PlatformPrincipal.issuer == issuer,
                PlatformPrincipal.subject == subject,
            )
        )
    ).scalar_one_or_none()


async def _criar(args: argparse.Namespace) -> int:
    agora = datetime.utcnow()
    async with sessao_plataforma() as db:
        if await _por_chave_natural(db, args.issuer, args.subject) is not None:
            return _erro(
                f"já existe principal para ({args.issuer}, {args.subject}). "
                "Para reativar um revogado, revise o caso no controle de mudanças "
                "antes — reativação silenciosa apaga o motivo da revogação."
            )
        principal = PlatformPrincipal(
            issuer=args.issuer,
            subject=args.subject,
            display_label=args.display_label,
            # Principal de break-glass nasce INATIVO e é ativado só pelo
            # subcomando `break-glass`, com dupla aprovação (ADR §2.8).
            ativo=not args.break_glass,
            break_glass=args.break_glass,
            valid_from=agora,
            valid_until=None,
            concedido_em=agora,
            concedido_por=args.approved_by,
            motivo_concessao=args.reason,
            criado_em=agora,
        )
        db.add(principal)
        await db.flush()
        await _trilha(
            db,
            principal=principal,
            acao="principal.criado",
            detalhe={
                "display_label": args.display_label,
                "aprovado_por": args.approved_by,
                "motivo": args.reason,
                "break_glass": args.break_glass,
            },
        )
        await db.commit()
        estado = "INATIVO (break-glass, ativar por comando)" if args.break_glass else "ativo"
        print(f"[ok] principal {principal.id} criado — {estado}")
        print(f"     issuer:  {principal.issuer}")
        print(f"     subject: {principal.subject}")
        print(f"     rótulo:  {principal.display_label}  (não decide nada)")
    return 0


async def _revogar(args: argparse.Namespace) -> int:
    agora = datetime.utcnow()
    async with sessao_plataforma() as db:
        principal = await _por_chave_natural(db, args.issuer, args.subject)
        if principal is None:
            return _erro(f"nenhum principal para ({args.issuer}, {args.subject})")
        if principal.revogado_em is not None:
            return _erro(
                f"principal {principal.id} já foi revogado em {principal.revogado_em} "
                f"por {principal.revogado_por}"
            )
        principal.ativo = False
        principal.revogado_em = agora
        principal.revogado_por = args.revoked_by
        principal.motivo_revogacao = args.reason
        principal.atualizado_em = agora
        await _trilha(
            db,
            principal=principal,
            acao="principal.revogado",
            detalhe={"revogado_por": args.revoked_by, "motivo": args.reason},
        )
        await db.commit()
        print(f"[ok] principal {principal.id} revogado — acesso cortado a partir de agora.")
        print("     Próximos passos do runbook §4: remover do grupo do Workspace e,")
        print("     em desligamento, suspender a conta. Nessa ordem.")
    return 0


async def _break_glass(args: argparse.Namespace) -> int:
    agora = datetime.utcnow()
    async with sessao_plataforma() as db:
        principal = (
            await db.execute(
                select(PlatformPrincipal).where(PlatformPrincipal.id == args.principal)
            )
        ).scalar_one_or_none()
        if principal is None:
            return _erro(f"principal {args.principal} não encontrado")

        if args.acao == "encerrar":
            if not principal.ativo:
                return _erro(f"principal {principal.id} já está inativo")
            principal.ativo = False
            principal.valid_until = agora
            principal.atualizado_em = agora
            await _trilha(
                db, principal=principal, acao="break_glass.encerrado", detalhe={}
            )
            await db.commit()
            print(f"[ok] break-glass do principal {principal.id} encerrado em {agora} (UTC).")
            print("     Runbook §5.6: revisão obrigatória em até 48 h.")
            return 0

        # --- ativação ---
        if principal.revogado_em is not None:
            return _erro(
                f"principal {principal.id} está revogado; break-glass não ressuscita "
                "principal revogado."
            )
        aprovadores = [a.strip() for a in (args.approved_by or []) if a.strip()]
        if len(set(aprovadores)) < 2:
            return _erro(
                "break-glass exige DUPLA APROVAÇÃO: dois --approved-by distintos, "
                "nominalmente registrados (ADR §2.8, runbook §5)."
            )
        if args.minutes < 1 or args.minutes > MINUTOS_MAXIMOS_BREAK_GLASS:
            return _erro(
                f"--minutes precisa estar entre 1 e {MINUTOS_MAXIMOS_BREAK_GLASS}. "
                "A janela não é renovável: um segundo período exige nova dupla aprovação."
            )
        if principal.ativo and principal.valid_until is not None and principal.valid_until > agora:
            return _erro(
                f"principal {principal.id} já está em janela de break-glass até "
                f"{principal.valid_until} (UTC). A janela NÃO é renovável — encerre, "
                "registre a revisão e abra uma nova com aprovação nova."
            )

        principal.ativo = True
        principal.break_glass = True
        principal.valid_from = agora
        principal.valid_until = agora + timedelta(minutes=args.minutes)
        principal.atualizado_em = agora
        await _trilha(
            db,
            principal=principal,
            acao="break_glass.ativado",
            detalhe={
                "aprovadores": aprovadores,
                "motivo": args.reason,
                "minutos": args.minutes,
                "expira_em": principal.valid_until.isoformat(),
            },
        )
        await db.commit()
        print(f"[ok] break-glass ATIVO no principal {principal.id}")
        print(f"     expira em: {principal.valid_until} (UTC) — {args.minutes} min, não renovável")
        print(f"     aprovadores: {', '.join(aprovadores)}")
        print("     Alertar o canal de operação AGORA e registrar no runbook §5.")
    return 0


async def _listar(_: argparse.Namespace) -> int:
    async with sessao_plataforma() as db:
        linhas = (
            await db.execute(select(PlatformPrincipal).order_by(PlatformPrincipal.id))
        ).scalars().all()
        print(f"{'ID':>4}  {'Ativo':6}  {'BG':3}  {'Vigência até':20}  {'Rótulo':32}  Subject")
        print("-" * 110)
        for p in linhas:
            print(
                f"{p.id:>4}  {'sim' if p.ativo else 'NÃO':6}  "
                f"{'sim' if p.break_glass else '-':3}  "
                f"{str(p.valid_until or '-'):20}  {p.display_label[:32]:32}  {p.subject}"
            )
    return 0


async def _executar(args: argparse.Namespace) -> int:
    if not get_settings().platform_db_url.strip():
        return _erro(
            "PLATFORM_DB_URL não configurada. Esta CLI abre a conexão com o papel "
            "`aprimora_platform` de propósito e NÃO cai para `ged_user` — se a "
            "migration 0076 não foi aplicada, aplique-a (runbook §2, passo 5)."
        )
    try:
        return await args.fn(args)
    finally:
        await descartar_engines_plataforma()


def construir_parser() -> argparse.ArgumentParser:
    """Separado de `main()` para que o teste possa conferir as linhas de comando
    do runbook sem executar nada — a CLI é contrato operacional, e um flag
    renomeado quebra copiar-e-colar durante incidente."""
    parser = argparse.ArgumentParser(
        prog="app.cli.platform_principal",
        description="Bootstrap e operação do principal de plataforma (ADR-016).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_criar = sub.add_parser("criar", help="Cadastra um operador de plataforma")
    p_criar.add_argument("--issuer", required=True, help="`iss` do token, colhido do log da tentativa negada")
    p_criar.add_argument("--subject", required=True, help="`sub` do OIDC — opaco e estável")
    p_criar.add_argument("--display-label", required=True, help="Rótulo (e-mail). NÃO decide nada")
    p_criar.add_argument("--reason", required=True, help="Motivo da concessão (com ticket)")
    p_criar.add_argument("--approved-by", required=True, help="Quem aprovou/testemunhou")
    p_criar.add_argument(
        "--break-glass",
        action="store_true",
        help="Cria o principal de EMERGÊNCIA, inativo, para ativação futura por dupla aprovação",
    )
    p_criar.set_defaults(fn=_criar)

    p_rev = sub.add_parser("revogar", help="Revoga o acesso — efeito imediato")
    p_rev.add_argument("--issuer", required=True)
    p_rev.add_argument("--subject", required=True)
    p_rev.add_argument("--reason", required=True, help="Motivo da revogação")
    p_rev.add_argument("--revoked-by", required=True, help="Quem revogou")
    p_rev.set_defaults(fn=_revogar)

    p_bg = sub.add_parser(
        "break-glass",
        help="Ativa (default) ou encerra a janela de emergência de um principal",
    )
    # Posicional opcional: `break-glass --principal X ...` ativa; `break-glass
    # encerrar --principal X` encerra. É o que o runbook §5 escreveu, e o
    # runbook é o contrato.
    p_bg.add_argument("acao", nargs="?", default="ativar", choices=["ativar", "encerrar"])
    p_bg.add_argument("--principal", required=True, type=int, help="ID do principal de emergência")
    p_bg.add_argument("--minutes", type=int, default=MINUTOS_MAXIMOS_BREAK_GLASS)
    p_bg.add_argument("--reason", default="", help="Incidente que justifica")
    p_bg.add_argument(
        "--approved-by",
        action="append",
        help="Repetir DUAS vezes, com pessoas distintas (dupla aprovação)",
    )
    p_bg.set_defaults(fn=_break_glass)

    p_list = sub.add_parser("listar", help="Lista os principals cadastrados")
    p_list.set_defaults(fn=_listar)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = construir_parser().parse_args(argv)
    return asyncio.run(_executar(args))


if __name__ == "__main__":
    sys.exit(main())

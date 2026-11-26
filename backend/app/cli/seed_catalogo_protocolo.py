"""CLI — catálogo de tipos de processo e assuntos de uma prefeitura (SI-54).

Hoje um tenant novo nasce com um tipo ("Solicitação") e um assunto ("Demanda
Cidadã"), criados pelo `seed_demo`. Enquanto a prefeitura não traz o
levantamento dela, este seed cadastra uma lista SUGERIDA por IA de tipos e
assuntos comuns em prefeituras de pequeno e médio porte, no modelo do SEI
(grupo do SEI = tipo; especificação = assunto). Os dados e a origem deles
estão em `dados/catalogo_protocolo.json`; o documento da área é
`docs/catalogo-protocolo.md`.

Uso:
    docker exec aprimora-py-backend python -m app.cli.seed_catalogo_protocolo \\
        apply --tenant sobral --allow-non-demo

Decisões de projeto:
    - **Só cria o que falta.** Tipo e assunto são procurados pelo nome no
      tenant (ignorando os excluídos); achou, não mexe. Re-rodar não duplica.
    - **Nunca altera o que existe.** Não reativa, não renomeia, não move de
      tipo. Assunto desativado pelo admin continua desativado — mesma regra do
      `seed_bootstrap` para não ressuscitar descontratação.
    - **Assunto de mesmo nome sob OUTRO tipo é conflito, não movimento**: fica
      onde está e aparece no resumo. Movê-lo mudaria o tipo de processos já
      abertos, porque o processo guarda só o assunto.
    - **"Solicitação"/"Demanda Cidadã" ficam intactos** — processos e serviços
      da demonstração apontam para eles (decisão do SI-54).
    - **`acesso_restrito_sugerido` do JSON não é aplicado.** Tipo e assunto
      não carregam sigilo no sistema; a marca fica registrada para o card que
      vai tratar disso.
    - **Avisa acima de 200 assuntos no tenant**, o teto que a abertura de
      processo carrega (`frontend/lib/assuntos.ts`, `ASSUNTOS_PAGE_SIZE`):
      passou disso, o combo corta o resto sem avisar ninguém.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# SEC-RLS-00B: operação ADMINISTRATIVA, não de runtime — ver `app/database_admin.py`.
from ..database_admin import AdminSessionLocal as SessionLocal
from ..models import Assunto, Tenant, TipoProcesso

DADOS = Path(__file__).parent / "dados" / "catalogo_protocolo.json"

# Espelha `ASSUNTOS_PAGE_SIZE` do frontend e o `le=200` de `GET /assuntos`.
TETO_ASSUNTOS_NA_ABERTURA = 200


def carregar_dados() -> dict[str, Any]:
    return json.loads(DADOS.read_text(encoding="utf-8"))


async def aplicar_catalogo(
    db: AsyncSession, tenant_id: int, dados: dict[str, Any]
) -> dict[str, Any]:
    """Cria no tenant os tipos e assuntos de `dados` que ainda não existem.

    Não faz commit: quem chama decide (o CLI commita; o teste também)."""
    contagens: dict[str, Any] = {
        "tipos_criados": 0,
        "tipos_existentes": 0,
        "assuntos_criados": 0,
        "assuntos_existentes": 0,
        "conflitos": [],
    }
    for tipo in dados["tipos"]:
        id_tipo = (
            await db.execute(
                select(TipoProcesso.id).where(
                    TipoProcesso.tenant_id == tenant_id,
                    TipoProcesso.tipo_processo == tipo["nome"],
                    TipoProcesso.excluido.is_(False),
                )
            )
        ).scalars().first()
        if id_tipo is None:
            novo = TipoProcesso(
                tenant_id=tenant_id,
                tipo_processo=tipo["nome"],
                exige_processo_pai=False,
                ativo=True,
                excluido=False,
            )
            db.add(novo)
            await db.flush()
            id_tipo = novo.id
            contagens["tipos_criados"] += 1
        else:
            contagens["tipos_existentes"] += 1

        for assunto in tipo["assuntos"]:
            existente = (
                await db.execute(
                    select(Assunto.id, Assunto.id_tipo_processo).where(
                        Assunto.tenant_id == tenant_id,
                        Assunto.assunto == assunto["nome"],
                        Assunto.excluido.is_(False),
                    )
                )
            ).first()
            if existente is None:
                db.add(
                    Assunto(
                        tenant_id=tenant_id,
                        assunto=assunto["nome"],
                        id_tipo_processo=id_tipo,
                        exige_processo_pai=False,
                        ativo=True,
                        excluido=False,
                        nivel=1,
                    )
                )
                contagens["assuntos_criados"] += 1
            elif existente.id_tipo_processo != id_tipo:
                contagens["conflitos"].append(
                    f"'{assunto['nome']}' já existe sob outro tipo (assunto id={existente.id})"
                )
            else:
                contagens["assuntos_existentes"] += 1
    await db.flush()

    contagens["assuntos_no_tenant"] = (
        await db.execute(
            select(func.count(Assunto.id)).where(
                Assunto.tenant_id == tenant_id, Assunto.excluido.is_(False)
            )
        )
    ).scalar_one()
    return contagens


def _guard_tenant_slug(slug: str, allow_non_demo: bool) -> None:
    """Mesmo guard dos outros seeds: fora de um tenant `demo*`, exige o flag."""
    if not slug.startswith("demo") and not allow_non_demo:
        print(
            f"[seed_catalogo_protocolo] RECUSADO: tenant '{slug}' não começa com 'demo'.\n"
            f"  Use --allow-non-demo se a intenção é mesmo cadastrar neste tenant.",
            file=sys.stderr,
        )
        sys.exit(2)


async def _apply(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    async with SessionLocal() as db:
        tid = (
            await db.execute(select(Tenant.id).where(Tenant.slug == args.tenant))
        ).scalar_one_or_none()
        if tid is None:
            print(f"[seed_catalogo_protocolo] Tenant '{args.tenant}' não existe.", file=sys.stderr)
            return 3
        # O listener `after_begin` aplica `SET LOCAL app.tenant_id` a partir daqui.
        db.info["tenant_id"] = int(tid)
        contagens = await aplicar_catalogo(db, int(tid), carregar_dados())
        await db.commit()

    print()
    print("=" * 62)
    print(f"SEED CATÁLOGO DO PROTOCOLO — tenant '{args.tenant}' (id={tid})")
    print("=" * 62)
    for k in ("tipos_criados", "tipos_existentes", "assuntos_criados", "assuntos_existentes"):
        print(f"  {k}: {contagens[k]}")
    print(f"  assuntos no tenant (ativos e inativos): {contagens['assuntos_no_tenant']}")
    for c in contagens["conflitos"]:
        print(f"  CONFLITO (não mexido): {c}")
    if contagens["assuntos_no_tenant"] > TETO_ASSUNTOS_NA_ABERTURA:
        print(
            f"  AVISO: mais de {TETO_ASSUNTOS_NA_ABERTURA} assuntos — a abertura de "
            f"processo só carrega os primeiros {TETO_ASSUNTOS_NA_ABERTURA} (ordem alfabética)."
        )
    print("=" * 62)
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="app.cli.seed_catalogo_protocolo", description=__doc__
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_apply = sub.add_parser("apply", help="Cadastra o que falta (idempotente)")
    p_apply.add_argument("--tenant", required=True, help="slug do tenant alvo")
    p_apply.add_argument(
        "--allow-non-demo", action="store_true",
        help="destrava slugs que não começam com 'demo'",
    )
    p_apply.set_defaults(fn=_apply)
    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())

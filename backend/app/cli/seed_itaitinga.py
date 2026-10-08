"""CLI de apresentação — deixa o tenant com a cara da Prefeitura de Itaitinga/CE.

Complementa o `seed_demo` e o `seed_demo_operacional`, que criam os dados
fictícios (processos, débitos, frota, permissionários). Este aqui troca o que é
identidade e geografia pelo município real:

  1. **Identidade** — nome, sigla, CNPJ, endereço, contatos, cor e brasão
     (`/brand/itaitinga-brasao.png`, servido de `frontend/public/brand/`).
  2. **Estrutura administrativa real** — as 15 secretarias/órgãos e as unidades
     de saúde, escolares, socioassistenciais e culturais, com endereço e
     telefone. Fonte: site oficial da prefeitura; ver `dados/itaitinga.json`,
     que registra as páginas e a data da coleta.
  3. **Demo localizada** — destinos das solicitações de veículo, pontos de
     táxi/mototáxi com coordenadas e trajetos de GPS dos veículos demo.

Uso:
    docker exec aprimora-py-backend python -m app.cli.seed_demo \\
        apply --tenant sobral --allow-non-demo
    docker exec aprimora-py-backend python -m app.cli.seed_demo_operacional \\
        apply --tenant sobral --allow-non-demo
    docker exec aprimora-py-backend python -m app.cli.seed_itaitinga \\
        apply --tenant sobral --allow-non-demo [--parte identidade|unidades|demo|todas]

Decisões de projeto:
    - **Idempotente.** Unidade e ponto são get-or-create por nome/código;
      re-rodar só atualiza endereço/telefone e regrava os trajetos.
    - **Renomeia as unidades do `seed_demo` em vez de duplicá-las.** "Secretaria
      de Obras" vira a secretaria real equivalente, mantendo o id — processos,
      usuários e contratos demo continuam apontando para uma unidade que existe
      no município. Re-rodar o `seed_demo` DEPOIS recria os nomes fictícios; a
      ordem é a do bloco de uso acima.
    - **O que é real e o que não é.** Secretarias e unidades são reais. Pontos
      de táxi (`DEMO ...`), coordenadas dos pontos e trajetos são ILUSTRATIVOS:
      servem para o mapa ter o que mostrar, não descrevem a operação do
      município. Os trajetos seguem ruas reais (geometria do OSRM, gravada no
      JSON) e são datados em relação a `now()` — o mapa da frota mostra 24h,
      então rode `apply --parte demo` de novo no dia da apresentação.
    - **Passa pelos serviços onde há regra** (ponto, ocupação de vaga,
      telemetria); o resto é cadastro simples.
    - Endereço e telefone de unidade vão por SQL: as colunas existem em
      `utils.unidade_trabalho` (herança do legado), mas o ORM não as mapeia.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

# SEC-RLS-00B: operação ADMINISTRATIVA, não de runtime — ver `app/database_admin.py`.
from ..database_admin import AdminSessionLocal as SessionLocal
from ..models import (
    Permissionario,
    Ponto,
    Tenant,
    TipoUnidadeTrabalho,
    UnidadeTrabalho,
    Veiculo,
)
from ..schemas.frota_telemetria import PosicaoCreate, PosicoesLoteCreate
from ..schemas.transporte_regulado import PontoCreate, PontoOcuparInput
from ..services import frota_telemetria
from ..services import transporte_regulado as tr

DADOS = Path(__file__).parent / "dados" / "itaitinga.json"
PARTES = ("identidade", "unidades", "demo")

IDENTIDADE = {
    "nome": "Prefeitura de Itaitinga",
    "sigla": "PMI",
    "cnpj": "41.563.628/0001-82",
    # Tema do município (0131): azul do brasão nos botões e na barra lateral,
    # e o laranja do layout de apresentação como destaque — é ele que tinge o
    # painel da cidade no login.
    "cor_primaria": "#1B4F8F",
    "cor_destaque": "#E5451F",
    "cor_lateral": "#12305A",
    "logo_url": "/brand/itaitinga-brasao.png",
    "logo_login_url": "/brand/itaitinga-logo.png",
    # Serra de Itaitinga (as pedreiras), do Wikimedia Commons — CC BY-SA 3.0,
    # que exige o crédito abaixo. Origem e licença em
    # `frontend/public/brand/CREDITOS.md`. A foto do portal da cidade a
    # substitui quando a prefeitura a fornecer.
    "imagem_login_url": "/brand/itaitinga-serra.jpg",
    "imagem_login_credito": "Foto: Lourenco e Silva / Wikimedia Commons (CC BY-SA 3.0)",
    "email_institucional": "prefeito@itaitinga.ce.gov.br",
    "telefone_institucional": "(85) 3513-2002",
    "endereco": "Av. Cel. Virgílio Távora, 1710 - Centro, Itaitinga - CE, 61.880-000",
    "site_oficial": "https://www.itaitinga.ce.gov.br",
    "horario_atendimento": "Segunda a sexta, de 08h às 12h e de 13h às 17h",
    "texto_boas_vindas_portal": (
        "Bem-vindo ao portal de serviços da Prefeitura Municipal de Itaitinga."
    ),
}

# (nome do tipo, código) — o grupo do JSON aponta para o tipo e para a
# secretaria a que as unidades se subordinam.
TIPO_PREFEITURA = ("Prefeitura", "PREF")
RAIZ = {
    "nome": "Prefeitura Municipal de Itaitinga",
    "logradouro": "Av. Cel. Virgílio Távora",
    "numero": "1710",
    "bairro": "Centro",
    "cep": "61.880-000",
}
TIPO_SECRETARIA = ("Secretaria", "SEC")
TIPO_SETOR = ("Setor", "SET")
GRUPOS_UNIDADE = {
    "saude": (("Unidade de Saúde", "UBS"), "Secretaria Municipal de Saúde"),
    "educacao": (("Unidade Escolar", "ESC"), "Secretaria Municipal de Educação"),
    "assistencia": (
        ("Equipamento Socioassistencial", "SOC"),
        "Secretaria Municipal de Trabalho e Assistência Social",
    ),
    "cultura": (("Unidade Cultural", "CUL"), "Secretaria Municipal de Cultura e Turismo"),
}

# Unidades fictícias do `seed_demo` -> secretaria real equivalente (renomeia).
RENOMEAR_DEMO = {
    # As duas primeiras vêm do `provisionar_tenant`/bootstrap antigo (VPS).
    "Prefeitura": "Prefeitura Municipal de Itaitinga",
    "Secretaria de Planejamento e Gestão": "Secretaria Municipal de Finanças e Planejamento",
    "Secretaria de Obras": "Secretaria Municipal de Infraestrutura, Obras e Serviços Públicos",
    "Secretaria de Meio Ambiente": "Secretaria Municipal de Meio Ambiente e Controle Urbano",
    "Secretaria de Administração": "Secretaria Municipal de Administração",
}
# Setores do `seed_demo` que seguem existindo, agora subordinados a uma secretaria real.
SUBORDINAR_DEMO = {
    "Protocolo Geral": "Secretaria Municipal de Administração",
    "Departamento de Iluminação Pública": (
        "Secretaria Municipal de Infraestrutura, Obras e Serviços Públicos"
    ),
}

# Destinos do `seed_demo_operacional` (região de Sobral) -> localidades de Itaitinga.
DESTINOS = {
    "Distrito de Aprazível": "Distrito de Gereraú",
    "Zona rural — rota norte": "Zona rural — rota Jabuti/Carapió",
    "Sobral — Santa Casa": "Fortaleza — Hospital Geral (HGF)",
    "Açude Jaibaras": "Pedreiras do bairro Ancuri",
    "Centro administrativo": "Paço Municipal — Centro",
}

# (nome, codigo, tipo, logradouro, bairro, latitude, longitude, vagas) — ILUSTRATIVOS.
PONTOS = [
    ("DEMO Ponto da Praça da Matriz", "DEMO-TX-01", "taxi",
     "Praça da Matriz", "Centro", "-3.9690", "-38.5283", 4),
    ("DEMO Ponto do Paço Municipal", "DEMO-TX-02", "taxi",
     "Av. Cel. Virgílio Távora", "Centro", "-3.9712", "-38.5262", 3),
    ("DEMO Ponto do Mercado", "DEMO-MT-01", "mototaxi",
     "Rua do Mercado", "Centro", "-3.9678", "-38.5301", 6),
    ("DEMO Ponto do Hospital Municipal", "DEMO-MT-02", "mototaxi",
     None, "Centro", "-3.9725", "-38.5310", 4),
    ("DEMO Ponto de Gereraú", "DEMO-MT-03", "mototaxi",
     None, "Gereraú", "-3.9160", "-38.5340", 4),
    ("DEMO Ponto Escolar do Centro", "DEMO-ES-01", "transporte_escolar",
     None, "Centro", "-3.9655", "-38.5270", 2),
]
# (código do ponto, vaga, tipo_servico, índice entre os permissionários ativos do tipo)
OCUPACOES = [
    ("DEMO-TX-01", 1, "taxi", 0),
    ("DEMO-TX-02", 2, "taxi", 1),
    ("DEMO-MT-01", 1, "mototaxi", 0),
    ("DEMO-ES-01", 1, "transporte_escolar", 0),
]

# placa -> (minutos atrás em que o trajeto terminou, ignição ligada ao final)
TRAJETOS = {
    "DMO1A07": (4, True),
    "DMO1A01": (35, False),
    "DMO1A03": (12, False),
    "DMO1A04": (55, False),
    "DMO1A02": (90, False),
}
INTERVALO_POSICOES_S = 15


# ---------------------------------------------------------------------------
# Infra
# ---------------------------------------------------------------------------


def _guard_tenant_slug(slug: str, allow_non_demo: bool) -> None:
    """Mesmo guard do `seed_demo`: reescreve identidade e unidades do tenant,
    então exige o flag explícito fora de um tenant `demo*`."""
    if not slug.startswith("demo") and not allow_non_demo:
        print(
            f"[seed_itaitinga] RECUSADO: tenant '{slug}' não começa com 'demo'.\n"
            f"  Use --allow-non-demo se a intenção é mesmo reescrever este tenant.",
            file=sys.stderr,
        )
        sys.exit(2)


async def _tenant_id(db: AsyncSession, slug: str) -> int:
    tid = (
        await db.execute(select(Tenant.id).where(Tenant.slug == slug))
    ).scalar_one_or_none()
    if tid is None:
        print(f"[seed_itaitinga] Tenant '{slug}' não existe.", file=sys.stderr)
        sys.exit(3)
    return tid


def _sessao(tenant_id: int) -> AsyncSession:
    """Sessão com o tenant fixado em `info` — o listener `after_begin` reaplica
    `SET LOCAL app.tenant_id` a cada transação, inclusive depois dos commits
    que os serviços fazem por conta própria."""
    db = SessionLocal()
    db.info["tenant_id"] = int(tenant_id)
    return db


def _decodificar_polyline(codigo: str) -> list[tuple[float, float]]:
    """Polyline do Google/OSRM (precisão 5) -> [(lat, lon), ...]."""
    pontos: list[tuple[float, float]] = []
    i = lat = lon = 0
    while i < len(codigo):
        deltas = []
        for _ in range(2):
            resultado = deslocamento = 0
            while True:
                b = ord(codigo[i]) - 63
                i += 1
                resultado |= (b & 0x1F) << deslocamento
                deslocamento += 5
                if b < 0x20:
                    break
            deltas.append(~(resultado >> 1) if resultado & 1 else resultado >> 1)
        lat += deltas[0]
        lon += deltas[1]
        pontos.append((lat / 1e5, lon / 1e5))
    return pontos


# ---------------------------------------------------------------------------
# 1. Identidade
# ---------------------------------------------------------------------------


async def _aplicar_identidade(db: AsyncSession, tenant_id: int) -> dict[str, Any]:
    await db.execute(text(
        "INSERT INTO utils.estado (estado, uf) "
        "SELECT 'Ceará', 'CE' WHERE NOT EXISTS (SELECT 1 FROM utils.estado WHERE uf = 'CE')"
    ))
    await db.execute(text(
        "INSERT INTO utils.cidade (cidade, id_estado) "
        "SELECT 'Itaitinga', (SELECT min(id) FROM utils.estado WHERE uf = 'CE') "
        "WHERE NOT EXISTS (SELECT 1 FROM utils.cidade WHERE cidade = 'Itaitinga')"
    ))
    id_cidade = (await db.execute(
        text("SELECT min(id) FROM utils.cidade WHERE cidade = 'Itaitinga'")
    )).scalar_one()

    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one()
    for campo, valor in IDENTIDADE.items():
        setattr(tenant, campo, valor)
    tenant.id_cidade = id_cidade
    tenant.atualizado_em = datetime.utcnow()

    # O admin padrão nasceu como "Admin Sobral" (seed_bootstrap antigo, que é
    # get-or-create e por isso não renomeia quem já existe). O nome aparece no
    # canto da tela e nos históricos.
    renomeados = await db.execute(
        text(
            "UPDATE utils.usuario SET nome = 'Administrador' "
            "WHERE tenant_id = :t AND nome ILIKE '%sobral%'"
        ),
        {"t": tenant_id},
    )
    await db.commit()
    return {
        "tenant_nome": IDENTIDADE["nome"],
        "id_cidade": id_cidade,
        "usuarios_renomeados": renomeados.rowcount,
    }


# ---------------------------------------------------------------------------
# 2. Estrutura administrativa
# ---------------------------------------------------------------------------


async def _get_or_create_tipo(
    db: AsyncSession, tenant_id: int, nome: str, codigo: str
) -> int:
    tid = (await db.execute(
        select(TipoUnidadeTrabalho.id).where(
            TipoUnidadeTrabalho.tenant_id == tenant_id,
            func.lower(TipoUnidadeTrabalho.tipo_unidade_trabalho) == nome.lower(),
            TipoUnidadeTrabalho.excluido.is_(False),
        ).order_by(TipoUnidadeTrabalho.id).limit(1)
    )).scalar_one_or_none()
    if tid:
        return tid
    tipo = TipoUnidadeTrabalho(
        tenant_id=tenant_id, tipo_unidade_trabalho=nome, codigo=codigo
    )
    db.add(tipo)
    await db.flush()
    return tipo.id


async def _unidade_por_nome(
    db: AsyncSession, tenant_id: int, nome: str
) -> UnidadeTrabalho | None:
    return (await db.execute(
        select(UnidadeTrabalho).where(
            UnidadeTrabalho.tenant_id == tenant_id,
            func.lower(UnidadeTrabalho.unidade_trabalho) == nome.lower(),
            UnidadeTrabalho.excluido.is_(False),
        ).order_by(UnidadeTrabalho.id).limit(1)
    )).scalar_one_or_none()


async def _garantir_unidade(
    db: AsyncSession, tenant_id: int, dados: dict[str, Any], *,
    id_tipo: int, id_pai: int | None,
) -> tuple[int, bool]:
    unidade = await _unidade_por_nome(db, tenant_id, dados["nome"])
    criada = unidade is None
    if unidade is None:
        unidade = UnidadeTrabalho(
            tenant_id=tenant_id, unidade_trabalho=dados["nome"], excluido=False
        )
        db.add(unidade)
    unidade.id_tipo_unidade_trabalho = id_tipo
    unidade.id_unidade_pai = id_pai
    await db.flush()
    await db.execute(
        text(
            "UPDATE utils.unidade_trabalho SET logradouro = :logradouro, "
            "numero = :numero, bairro = :bairro, cep = :cep, telefone = :telefone "
            "WHERE id = :id"
        ),
        {
            "id": unidade.id,
            "logradouro": dados.get("logradouro"),
            "numero": dados.get("numero"),
            "bairro": dados.get("bairro"),
            "cep": dados.get("cep"),
            "telefone": dados.get("telefone"),
        },
    )
    return unidade.id, criada


async def _aplicar_unidades(db: AsyncSession, tenant_id: int) -> dict[str, Any]:
    dados = json.loads(DADOS.read_text(encoding="utf-8"))
    contagens = {"unidades_renomeadas": 0, "secretarias_criadas": 0, "unidades_criadas": 0}

    # Antes de tudo: senão o get-or-create abaixo criaria a secretaria real ao
    # lado da fictícia, e a renomeação depois colidiria com ela.
    for antigo, novo in RENOMEAR_DEMO.items():
        unidade = await _unidade_por_nome(db, tenant_id, antigo)
        if unidade is not None and await _unidade_por_nome(db, tenant_id, novo) is None:
            unidade.unidade_trabalho = novo
            unidade.sigla = None
            contagens["unidades_renomeadas"] += 1
    await db.flush()

    # Raiz do organograma: as secretarias se subordinam à Prefeitura.
    id_raiz, _ = await _garantir_unidade(
        db,
        tenant_id,
        {**RAIZ, "telefone": IDENTIDADE["telefone_institucional"]},
        id_tipo=await _get_or_create_tipo(db, tenant_id, *TIPO_PREFEITURA),
        id_pai=None,
    )

    id_tipo_sec = await _get_or_create_tipo(db, tenant_id, *TIPO_SECRETARIA)
    secretarias: dict[str, int] = {}
    for sec in dados["secretarias"]:
        uid, criada = await _garantir_unidade(
            db, tenant_id, sec, id_tipo=id_tipo_sec, id_pai=id_raiz
        )
        secretarias[sec["nome"]] = uid
        contagens["secretarias_criadas"] += int(criada)

    for grupo, ((tipo_nome, tipo_codigo), secretaria) in GRUPOS_UNIDADE.items():
        id_tipo = await _get_or_create_tipo(db, tenant_id, tipo_nome, tipo_codigo)
        for unidade in dados["unidades"][grupo]:
            _, criada = await _garantir_unidade(
                db, tenant_id, unidade, id_tipo=id_tipo, id_pai=secretarias[secretaria]
            )
            contagens["unidades_criadas"] += int(criada)

    id_tipo_setor = await _get_or_create_tipo(db, tenant_id, *TIPO_SETOR)
    for setor, secretaria in SUBORDINAR_DEMO.items():
        unidade = await _unidade_por_nome(db, tenant_id, setor)
        if unidade is not None:
            unidade.id_unidade_pai = secretarias[secretaria]
            unidade.id_tipo_unidade_trabalho = id_tipo_setor

    await db.commit()
    contagens["secretarias_total"] = len(secretarias)
    contagens["unidades_total"] = sum(len(v) for v in dados["unidades"].values())
    return contagens


# ---------------------------------------------------------------------------
# 3. Demo localizada
# ---------------------------------------------------------------------------


async def _aplicar_demo(db: AsyncSession, tenant_id: int) -> dict[str, Any]:
    contagens: dict[str, Any] = {}

    destinos = 0
    for antigo, novo in DESTINOS.items():
        r = await db.execute(
            text(
                "UPDATE frota.solicitacao_veiculo SET destino = :novo "
                "WHERE tenant_id = :t AND destino = :antigo AND finalidade LIKE 'DEMO %'"
            ),
            {"t": tenant_id, "antigo": antigo, "novo": novo},
        )
        destinos += r.rowcount
    await db.commit()
    contagens["destinos_localizados"] = destinos

    # --- Pontos regulados ---------------------------------------------------
    ids: dict[str, int] = {}
    criados = 0
    for nome, codigo, tipo, logradouro, bairro, lat, lon, vagas in PONTOS:
        existente = (await db.execute(
            select(Ponto.id).where(
                Ponto.tenant_id == tenant_id,
                Ponto.codigo == codigo,
                Ponto.excluido.is_(False),
            )
        )).scalar_one_or_none()
        if existente:
            ids[codigo] = existente
            continue
        ponto = await tr.criar_ponto(
            db,
            tenant_id=tenant_id,
            payload=PontoCreate(
                nome=nome, codigo=codigo, tipo_servico=tipo, logradouro=logradouro,
                bairro=bairro, cep="61880-000", latitude=lat, longitude=lon,
                vagas_total=vagas,
            ),
        )
        ids[codigo] = ponto.id
        await db.commit()
        criados += 1
    contagens["pontos_criados"] = criados

    ocupadas = 0
    for codigo, vaga, tipo, indice in OCUPACOES:
        permissionarios = (await db.execute(
            select(Permissionario.id).where(
                Permissionario.tenant_id == tenant_id,
                Permissionario.tipo_servico == tipo,
                Permissionario.situacao == "ativo",
                Permissionario.excluido.is_(False),
            ).order_by(Permissionario.id)
        )).scalars().all()
        if indice >= len(permissionarios):
            continue
        try:
            await tr.ocupar_vaga(
                db,
                tenant_id=tenant_id,
                ponto_id=ids[codigo],
                payload=PontoOcuparInput(
                    numero_vaga=vaga, id_permissionario=permissionarios[indice]
                ),
            )
            await db.commit()
            ocupadas += 1
        except HTTPException:
            # Vaga já ocupada ou permissionário já lotado: é a re-execução.
            await db.rollback()
    contagens["vagas_ocupadas_agora"] = ocupadas

    # --- Trajetos de GPS ----------------------------------------------------
    rotas = json.loads(DADOS.read_text(encoding="utf-8"))["rotas_polyline"]
    agora = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    rng = random.Random(7)
    posicoes = 0
    for placa, (minutos_atras, ligada_ao_final) in TRAJETOS.items():
        id_veiculo = (await db.execute(
            select(Veiculo.id).where(
                Veiculo.tenant_id == tenant_id,
                Veiculo.placa == placa,
                Veiculo.excluido.is_(False),
            )
        )).scalar_one_or_none()
        if id_veiculo is None:
            continue
        # Regrava: o trajeto é relativo a `now()`, e o da execução anterior
        # ficaria como um segundo percurso do mesmo veículo.
        await db.execute(
            text(
                "DELETE FROM frota.veiculo_posicao "
                "WHERE tenant_id = :t AND id_veiculo = :v"
            ),
            {"t": tenant_id, "v": id_veiculo},
        )
        await db.commit()
        pontos = _decodificar_polyline(rotas[placa])
        fim = agora - timedelta(minutes=minutos_atras)
        lote = [
            PosicaoCreate(
                data_hora=fim - timedelta(
                    seconds=INTERVALO_POSICOES_S * (len(pontos) - 1 - n)
                ),
                latitude=Decimal(str(lat)),
                longitude=Decimal(str(lon)),
                velocidade=(
                    Decimal("0") if n == len(pontos) - 1
                    else Decimal(rng.randint(22, 58))
                ),
                ignicao_ligada=ligada_ao_final if n == len(pontos) - 1 else True,
            )
            for n, (lat, lon) in enumerate(pontos)
        ]
        resultado = await frota_telemetria.registrar_posicoes(
            db,
            tenant_id=tenant_id,
            id_veiculo=id_veiculo,
            payload=PosicoesLoteCreate(posicoes=lote),
        )
        posicoes += resultado["registradas"]
    contagens["posicoes_gps"] = posicoes
    return contagens


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


async def _apply(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)
    selecionadas = PARTES if args.parte == "todas" else (args.parte,)
    executores = {
        "identidade": _aplicar_identidade,
        "unidades": _aplicar_unidades,
        "demo": _aplicar_demo,
    }
    contagens: dict[str, Any] = {}
    for parte in selecionadas:
        async with _sessao(tid) as db:
            contagens.update(await executores[parte](db, tid))

    print()
    print("=" * 62)
    print(f"SEED ITAITINGA APPLY — tenant '{args.tenant}' (id={tid})")
    print(f"partes: {', '.join(selecionadas)}")
    print("=" * 62)
    for k, v in contagens.items():
        print(f"  {k}: {v}")
    print("=" * 62)
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli.seed_itaitinga", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_apply = sub.add_parser("apply", help="Aplica os dados (idempotente)")
    p_apply.add_argument("--tenant", required=True, help="slug do tenant alvo")
    p_apply.add_argument(
        "--allow-non-demo", action="store_true",
        help="destrava slugs que não começam com 'demo'",
    )
    p_apply.add_argument(
        "--parte", choices=(*PARTES, "todas"), default="todas",
        help="limita a uma parte (padrão: todas)",
    )
    p_apply.set_defaults(fn=_apply)
    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())

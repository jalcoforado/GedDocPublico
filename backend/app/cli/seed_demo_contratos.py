"""CLI de seed demonstrativo do módulo Contratos (G1).

Uso:
    docker exec aprimora-py-backend python -m app.cli.seed_demo_contratos \\
        status --tenant sobral --allow-non-demo
    ... apply  --tenant sobral --allow-non-demo
    ... reset  --tenant sobral --allow-non-demo

Roda DEPOIS de `seed_bootstrap` (que liga a transação `contrato` ao módulo e ao
sistema) e, na apresentação como Itaitinga, depois de `seed_itaitinga` — os
contratos são distribuídos pelas unidades que o tenant tiver nesse momento.

Decisões de projeto:
    - **É um CLI próprio, e não mais um `--modulo` do `seed_demo_operacional`.**
      O desenho previa o segundo. Lá, `MODULOS` define o que é "todos" e é a
      condição do reset de usuários; acrescentar um quarto módulo mudaria o
      comportamento de um seed que já tem teste, por causa de um que ainda não
      tem. Os helpers de sessão e de guarda são reaproveitados de lá.
    - **Contrata o módulo no tenant alvo** (decisão Q4 do spec): a migration
      0131 não contrata ninguém, de propósito.
    - **Passa pelos serviços.** Cada contrato é criado em rascunho, assinado e
      aditado pelo mesmo caminho da tela — então situação, numeração, limite
      do art. 125 e cálculo saem coerentes, e um seed que quebre é sinal de
      regra quebrada.
    - **Datas relativas ao dia em que roda.** O painel mostra "vencendo em
      30/60/90/120 dias"; com data fixa ele estaria vazio (ou todo vencido) na
      semana seguinte. No dia da apresentação: `reset` e `apply`.
    - **Tudo fictício e marcado.** Números `DMC-…`, fornecedores com documento
      na faixa `98…`. Não usar nome nem CNPJ de empresa real do portal do
      município: é demonstração publicada em VPS.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select, text

from ..models import Contrato, Modulo, TenantModulo, UnidadeTrabalho
from .seed_demo_operacional import (
    SessionLocal,
    _executar_reset,
    _guard_tenant_slug,
    _sessao,
    _tenant_id,
)

PREFIXO = "DMC"
MODULO_SLUG = "contratos"

# (tipo_pessoa, documento, nome) — documento na faixa 98…, fora do `99%` que o
# reset de pagamentos apaga.
FORNECEDORES = [
    ("JURIDICA", "98.100.200/0001-11", "Serra Azul Engenharia e Construções Ltda (DEMO)"),
    ("JURIDICA", "98.300.400/0001-22", "Nutrivale Alimentação Escolar Ltda (DEMO)"),
    ("JURIDICA", "98.500.600/0001-33", "Rota Segura Transportes Ltda (DEMO)"),
    ("JURIDICA", "98.700.800/0001-44", "Posto Pedra Branca Combustíveis Ltda (DEMO)"),
    ("JURIDICA", "98.900.100/0001-55", "Vetor Sistemas e Tecnologia Ltda (DEMO)"),
    ("JURIDICA", "98.110.220/0001-66", "Farmavida Distribuidora Hospitalar Ltda (DEMO)"),
    ("JURIDICA", "98.330.440/0001-77", "Limpa Cidade Serviços Ambientais Ltda (DEMO)"),
    ("FISICA", "98811122233", "Maria das Graças Oliveira (locadora — DEMO)"),
]

JUSTIFICATIVA_LIMITE = (
    "DEMO — acréscimo acima do limite do art. 125 da Lei 14.133, amparado em fato "
    "superveniente registrado em parecer jurídico fictício."
)

# Cada contrato:
#   seq, fornecedor (índice), objeto, tipo_objeto (SIM), categoria, natureza,
#   valor, início (dias atrás), fim ORIGINAL (dias a partir de hoje), reforma,
#   destino ("VIGENTE" | "RASCUNHO" | "ENCERRADO" | "RESCINDIDO"),
#   atos — lista de:
#     ("AA"|"AR", valor, justificativa|None)
#     ("AP", nova_data_em_dias)
#     ("PA"|"PR"|"RE", valor, nova_data_em_dias)
#     ("REAJUSTE", delta, índice)
#     ("DOTACAO"|"RAZAO_SOCIAL", descrição)
# A ordem dos atos importa: cada nova data tem de ser posterior à vigência atual.
CONTRATOS: list[tuple] = [
    # --- vencendo: é o que o gestor abre o painel para ver -------------------
    (1, 1, "Fornecimento de gêneros alimentícios para a merenda escolar",
     "M", "BENS", "CONTINUO", "620000.00", 345, 18, False, "VIGENTE", []),
    (2, 2, "Transporte escolar da zona rural — 14 rotas",
     "J", "SERVICOS", "CONTINUO", "1480000.00", 320, 42, False, "VIGENTE",
     [("REAJUSTE", "71484.00", "IPCA 12 meses 4,83%")]),
    (3, 3, "Fornecimento de combustíveis para a frota municipal",
     "K", "BENS", "CONTINUO", "890000.00", 290, 75, False, "VIGENTE",
     [("AA", "204700.00", None)]),  # 23%: perto do limite, sem estourar
    (4, 7, "Locação de imóvel para funcionamento do CRAS",
     "I", "LOCACOES", "CONTINUO", "84000.00", 255, 108, False, "VIGENTE", []),
    # --- vencido sem decisão: o caso que a gestão quer evitar ----------------
    (5, 6, "Coleta e destinação de resíduos sólidos urbanos",
     "C", "SERVICOS", "CONTINUO", "2350000.00", 370, -6, False, "VIGENTE", []),
    # --- prorrogados e aditados: os seis tipos do SIM ------------------------
    (6, 4, "Licença e suporte do sistema de gestão tributária",
     "N", "SERVICOS", "CONTINUO", "216000.00", 400, -35, False, "VIGENTE",
     [("RE", "216000.00", 330), ("DOTACAO", "Empenho da dotação do novo exercício")]),
    (7, 5, "Aquisição de medicamentos da atenção básica",
     "G", "BENS", "ESCOPO", "540000.00", 200, 15, False, "VIGENTE",
     [("AP", 165)]),
    (8, 0, "Pavimentação em paralelepípedo — bairro Gereraú",
     "E", "OBRAS", "ESCOPO", "1260000.00", 240, 30, False, "VIGENTE",
     [("PA", "189000.00", 150)]),
    (9, 0, "Construção de quadra poliesportiva coberta",
     "E", "OBRAS", "ESCOPO", "980000.00", 210, 60, False, "VIGENTE",
     [("PR", "73500.00", 140)]),
    (10, 6, "Limpeza e conservação de prédios públicos",
     "H", "SERVICOS", "CONTINUO", "760000.00", 180, 185, False, "VIGENTE",
     [("AR", "91200.00", None)]),
    # --- os dois casos de limite ---------------------------------------------
    (11, 0, "Drenagem e recuperação de vias — distrito sede",
     "E", "OBRAS", "ESCOPO", "1500000.00", 160, 200, False, "VIGENTE",
     [("AA", "450000.00", JUSTIFICATIVA_LIMITE)]),  # 30%: acima, com justificativa
    (12, 0, "Reforma da Unidade Básica de Saúde do Centro",
     "E", "OBRAS", "ESCOPO", "640000.00", 150, 120, True, "VIGENTE",
     [("AA", "256000.00", None)]),  # 40% em reforma: dentro dos 50%
    # --- contratos correntes, sem ato ----------------------------------------
    (13, 4, "Manutenção de computadores e rede lógica",
     "N", "SERVICOS", "CONTINUO", "132000.00", 120, 245, False, "VIGENTE", []),
    (14, 3, "Fornecimento de lubrificantes e peças para veículos",
     "K", "BENS", "CONTINUO", "168000.00", 95, 270, False, "VIGENTE", []),
    (15, 1, "Aquisição de material de consumo de escritório",
     "P", "BENS", "ESCOPO", "74000.00", 70, 110, False, "VIGENTE",
     [("RAZAO_SOCIAL", "Alteração da denominação social da contratada")]),
    (16, 2, "Locação de veículos para a Secretaria de Saúde",
     "L", "LOCACOES", "CONTINUO", "312000.00", 50, 315, False, "VIGENTE", []),
    # --- encerrado, rescindido e rascunhos -----------------------------------
    (17, 5, "Aquisição de equipamentos hospitalares",
     "R", "BENS", "ESCOPO", "410000.00", 300, -40, False, "ENCERRADO", []),
    (18, 6, "Roçagem e capina de terrenos públicos",
     "O", "SERVICOS", "ESCOPO", "195000.00", 220, 90, False, "RESCINDIDO", []),
    (19, 4, "Implantação de sistema de gestão de frotas",
     "N", "SERVICOS", "CONTINUO", "98000.00", 0, 365, False, "RASCUNHO", []),
    (20, 0, "Ampliação do Centro de Educação Infantil",
     "E", "OBRAS", "ESCOPO", "870000.00", 0, 240, False, "RASCUNHO", []),
]

RESET = [
    ("apostilas", f"""
        DELETE FROM pagamentos.contrato_apostila WHERE tenant_id = :t
          AND id_contrato IN (SELECT id FROM pagamentos.contrato
                              WHERE tenant_id = :t AND numero LIKE '{PREFIXO}-%')"""),
    ("aditivos", f"""
        DELETE FROM pagamentos.contrato_aditivo WHERE tenant_id = :t
          AND id_contrato IN (SELECT id FROM pagamentos.contrato
                              WHERE tenant_id = :t AND numero LIKE '{PREFIXO}-%')"""),
    ("contratos", f"""
        DELETE FROM pagamentos.contrato WHERE tenant_id = :t
          AND numero LIKE '{PREFIXO}-%'"""),
    ("fornecedor_historico", """
        DELETE FROM pagamentos.fornecedor_situacao_historico WHERE tenant_id = :t
          AND id_fornecedor IN (SELECT id FROM pagamentos.fornecedor
                                WHERE tenant_id = :t AND cnpj_cpf LIKE '98%')"""),
    ("fornecedores", """
        DELETE FROM pagamentos.fornecedor WHERE tenant_id = :t
          AND cnpj_cpf LIKE '98%'"""),
]


def _numero(seq: int, ano: int) -> str:
    """`DMC-001/2026` — 12 caracteres, dentro dos 15 do SIM."""
    return f"{PREFIXO}-{seq:03d}/{ano}"


def _numero_aditivo(seq: int, ordem: int, ano: int) -> str:
    """`DMC-001A1/2026` — 14 caracteres. Contrato e aditivo dividem a numeração
    do exercício no SIM, então o aditivo não pode repetir o número do contrato."""
    return f"{PREFIXO}-{seq:03d}A{ordem}/{ano}"


async def _contratar_modulo(tenant_id: int) -> bool:
    """Garante a contratação do módulo `contratos`. Devolve True se mexeu.

    Insere/reativa só ESTA linha, em vez de chamar `modulos.contratar`, que
    reconcilia a lista inteira e descontrataria o que não fosse repassado.
    """
    async with SessionLocal() as db:
        modulo = (await db.execute(
            select(Modulo).where(Modulo.slug == MODULO_SLUG))).scalar_one_or_none()
        if modulo is None:
            print(
                "[seed_demo_contratos] Módulo 'contratos' não está no catálogo. "
                "Rode `alembic upgrade head` (migration 0131).", file=sys.stderr)
            sys.exit(5)
        vinculo = (await db.execute(select(TenantModulo).where(
            TenantModulo.tenant_id == tenant_id,
            TenantModulo.id_modulo == modulo.id))).scalars().first()
        if vinculo is None:
            db.add(TenantModulo(tenant_id=tenant_id, id_modulo=modulo.id))
        elif vinculo.excluido or not vinculo.ativo:
            vinculo.excluido = False
            vinculo.ativo = True
        else:
            return False
        await db.commit()
        return True


async def _unidades(db, tenant_id: int) -> list[int]:
    ids = list((await db.execute(
        select(UnidadeTrabalho.id).where(
            UnidadeTrabalho.tenant_id == tenant_id, UnidadeTrabalho.excluido.is_(False))
        .order_by(UnidadeTrabalho.id))).scalars().all())
    if not ids:
        print(
            "[seed_demo_contratos] Tenant sem unidade de trabalho. Rode antes: "
            "python -m app.cli.seed_demo apply --tenant <slug> --allow-non-demo",
            file=sys.stderr)
        sys.exit(4)
    return ids


async def _aplicar_atos(db, svc, schemas, *, tenant_id: int, contrato_id: int, seq: int,
                        atos: list[tuple], inicio: date, hoje: date,
                        contagens: dict[str, int]) -> None:
    """Registra os atos em ordem, espaçados entre o início do contrato e ontem."""
    ordem_aditivo = 0
    total = len(atos)
    janela = max((hoje - inicio).days - 1, 1)
    for i, ato in enumerate(atos, 1):
        quando = inicio + timedelta(days=max(janela * i // (total + 1), 1))
        tipo = ato[0]
        if tipo in ("REAJUSTE", "DOTACAO", "RAZAO_SOCIAL"):
            com_valor = tipo == "REAJUSTE"
            await svc.criar_apostila(
                db, tenant_id=tenant_id, contrato_id=contrato_id, usuario_id=None, hoje=hoje,
                payload=schemas.ApostilaCreate(
                    tipo=tipo, data=quando,
                    valor_delta=Decimal(ato[1]) if com_valor else None,
                    indice=ato[2] if com_valor else None,
                    descricao=("DEMO — reajuste anual previsto em contrato" if com_valor
                               else f"DEMO — {ato[1]}")))
            contagens["apostilas"] += 1
            continue

        ordem_aditivo += 1
        valor, nova, justificativa = Decimal("0"), None, None
        if tipo in ("AA", "AR"):
            valor, justificativa = Decimal(ato[1]), ato[2]
        elif tipo == "AP":
            nova = hoje + timedelta(days=ato[1])
        else:  # PA, PR, RE
            valor, nova = Decimal(ato[1]), hoje + timedelta(days=ato[2])
        aditivo = await svc.criar_aditivo(
            db, tenant_id=tenant_id, contrato_id=contrato_id, usuario_id=None,
            payload=schemas.AditivoCreate(
                numero=_numero_aditivo(seq, ordem_aditivo, quando.year), tipo=tipo,
                data_assinatura=quando, valor=valor, nova_vigencia_fim=nova,
                justificativa=justificativa))
        await svc.assinar_aditivo(
            db, tenant_id=tenant_id, contrato_id=contrato_id, aditivo_id=aditivo.id, hoje=hoje)
        contagens["aditivos"] += 1


async def _apply(args: argparse.Namespace) -> int:
    from ..schemas import contratos as schemas
    from ..schemas.pagamentos import FornecedorCreate
    from ..services import contratos as svc
    from ..services import pagamentos_cadastros as cad_svc

    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)

    contagens: dict[str, int] = {
        "modulo_contratado_agora": int(await _contratar_modulo(tid)),
        "fornecedores": 0, "contratos": 0, "aditivos": 0, "apostilas": 0,
        "ja_existiam": 0,
    }
    hoje = date.today()
    # O service só usa o usuário para o sigilo do processo vinculado, e nenhum
    # contrato de demonstração vincula processo.
    usuario = SimpleNamespace(id=None, nivel_acesso_sigilo="ostensivo")

    async with _sessao(tid) as db:
        unidades = await _unidades(db, tid)

        fornecedores: list[int] = []
        existentes = {f.cnpj_cpf: f.id for f in await cad_svc.listar_fornecedores(db, tenant_id=tid)}
        for tipo, doc, nome in FORNECEDORES:
            if doc in existentes:
                fornecedores.append(existentes[doc])
                continue
            f = await cad_svc.criar_fornecedor(
                db, tenant_id=tid,
                payload=FornecedorCreate(tipo_pessoa=tipo, cnpj_cpf=doc, nome=nome))
            fornecedores.append(f.id)
            contagens["fornecedores"] += 1

        ja = set((await db.execute(select(Contrato.numero).where(
            Contrato.tenant_id == tid, Contrato.excluido.is_(False),
            Contrato.numero.like(f"{PREFIXO}-%")))).scalars().all())

        for (seq, forn, objeto, tipo_objeto, categoria, natureza, valor, inicio_atras,
             fim_em, reforma, destino, atos) in CONTRATOS:
            inicio = hoje - timedelta(days=inicio_atras)
            numero = _numero(seq, inicio.year)
            # Idempotência pelo SEQUENCIAL, não pelo número inteiro: o ano do
            # número muda se o seed rodar de novo depois da virada do exercício.
            if any(n.startswith(f"{PREFIXO}-{seq:03d}/") for n in ja):
                contagens["ja_existiam"] += 1
                continue
            c = await svc.criar(db, tenant_id=tid, usuario=usuario, payload=schemas.ContratoCreate(
                numero=numero, id_fornecedor=fornecedores[forn],
                id_unidade=unidades[(seq - 1) % len(unidades)], objeto=f"DEMO — {objeto}",
                vigencia_inicio=inicio, vigencia_fim=hoje + timedelta(days=fim_em),
                valor_total=Decimal(valor), categoria=categoria, data_celebracao=inicio,
                tipo_objeto=tipo_objeto, natureza_duracao=natureza, reforma=reforma,
                processo_numero=f"{inicio.year}.{seq:02d}.01DEMO"))
            contagens["contratos"] += 1
            if destino == "RASCUNHO":
                continue
            await svc.assinar(db, tenant_id=tid, contrato_id=c.id)
            await _aplicar_atos(
                db, svc, schemas, tenant_id=tid, contrato_id=c.id, seq=seq, atos=atos,
                inicio=inicio, hoje=hoje, contagens=contagens)
            if destino == "ENCERRADO":
                await svc.encerrar(
                    db, tenant_id=tid, contrato_id=c.id,
                    data_encerramento=hoje + timedelta(days=fim_em))
            elif destino == "RESCINDIDO":
                await svc.rescindir(
                    db, tenant_id=tid, contrato_id=c.id,
                    data_encerramento=hoje - timedelta(days=30),
                    motivo="DEMO — inexecução parcial reiterada, após notificações.")

    _resumo("APPLY", args.tenant, tid, contagens)
    return 0


async def _reset(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    contagens: dict[str, int] = {}
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)
    async with _sessao(tid) as db:
        await _executar_reset(db, tid, RESET, contagens)
        await db.commit()
    # A contratação do módulo NÃO é desfeita: descontratar é decisão do
    # operador, na aba Módulos, e não efeito colateral de limpar demonstração.
    _resumo("RESET", args.tenant, tid, contagens)
    return 0


async def _status(args: argparse.Namespace) -> int:
    _guard_tenant_slug(args.tenant, allow_non_demo=True)  # status não muda nada
    async with SessionLocal() as db:
        tid = await _tenant_id(db, args.tenant)
        contratado = (await db.execute(text("""
            SELECT count(*) FROM aprimora_py.tenant_modulo tm
              JOIN aprimora_py.modulo m ON m.id = tm.id_modulo
             WHERE tm.tenant_id = :t AND m.slug = :s AND tm.excluido = false AND tm.ativo
        """), {"t": tid, "s": MODULO_SLUG})).scalar_one()
    consultas = [
        ("Contratos demo", f"SELECT count(*) FROM pagamentos.contrato WHERE tenant_id=:t "
                           f"AND numero LIKE '{PREFIXO}-%' AND excluido=false"),
        ("  vigentes", f"SELECT count(*) FROM pagamentos.contrato WHERE tenant_id=:t "
                       f"AND numero LIKE '{PREFIXO}-%' AND excluido=false "
                       "AND situacao='VIGENTE'"),
        ("Aditivos demo", f"SELECT count(*) FROM pagamentos.contrato_aditivo a "
                          "JOIN pagamentos.contrato c ON c.id = a.id_contrato "
                          f"WHERE a.tenant_id=:t AND c.numero LIKE '{PREFIXO}-%' "
                          "AND a.excluido=false"),
        ("Apostilas demo", f"SELECT count(*) FROM pagamentos.contrato_apostila p "
                           "JOIN pagamentos.contrato c ON c.id = p.id_contrato "
                           f"WHERE p.tenant_id=:t AND c.numero LIKE '{PREFIXO}-%' "
                           "AND p.excluido=false"),
        ("Fornecedores demo", "SELECT count(*) FROM pagamentos.fornecedor "
                              "WHERE tenant_id=:t AND cnpj_cpf LIKE '98%' AND excluido=false"),
    ]
    contagens: dict[str, Any] = {"Módulo contratado": "sim" if contratado else "NÃO"}
    async with _sessao(tid) as db:
        for rotulo, sql in consultas:
            contagens[rotulo] = (await db.execute(text(sql), {"t": tid})).scalar_one()
    _resumo("STATUS", args.tenant, tid, contagens)
    return 0


def _resumo(acao: str, slug: str, tid: int, contagens: dict[str, Any]) -> None:
    print()
    print("=" * 62)
    print(f"SEED CONTRATOS {acao} — tenant '{slug}' (id={tid})")
    print("=" * 62)
    for k, v in contagens.items():
        print(f"  {k}: {v}")
    print("=" * 62)
    if acao == "APPLY":
        print()
        print("Datas relativas a hoje. No dia da apresentação: reset e apply de novo.")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli.seed_demo_contratos", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for nome, ajuda, fn in (
        ("status", "Mostra o que já existe", _status),
        ("apply", "Cria os dados (idempotente por contrato)", _apply),
        ("reset", "Remove os dados demo do módulo", _reset),
    ):
        p = sub.add_parser(nome, help=ajuda)
        p.add_argument("--tenant", required=True, help="slug do tenant alvo")
        p.add_argument(
            "--allow-non-demo", action="store_true",
            help="destrava slugs que não começam com 'demo'")
        p.set_defaults(fn=fn)
    args = parser.parse_args(argv)
    return asyncio.run(args.fn(args))


if __name__ == "__main__":
    sys.exit(main())

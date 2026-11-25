"""Seed de HISTÓRICO do módulo Despesa — meses anteriores já executados.

Os painéis do módulo leem séries temporais: evolução mensal, despesa por
secretaria/fornecedor/contrato no período, ritmo semanal, envelhecimento da
fila e execução orçamentária. Num banco recém-semeado tudo nasce hoje, e os
gráficos ficam com uma barra só — tecnicamente corretos e visualmente inúteis.

Este seed preenche o passado:

- **N meses de despesas EXECUTADAS** (autorizadas, pagas, com movimentação de
  saída datada no mês), espalhadas por unidade, fornecedor, natureza, fonte e
  contrato — é o que dá volume aos cinco gráficos de composição.
- **Trilha retroagida** (`CRIADO` e `AUTORIZADO` em `debito_historico`), para o
  gráfico de ritmo semanal ter entradas e autorizações ao longo do tempo.
- **Despesas em tramitação com idades escalonadas** (3, 6, 12, 25 e 50 dias),
  para as cinco faixas do gráfico de envelhecimento aparecerem preenchidas.
- **Parcelas a vencer** em +5, +12, +25, +50 e +80 dias, para as cinco janelas
  da previsão financeira (7/15/30/60/90) saírem do zero.
- **Vínculo com dotação e `valor_empenhado`** quando houver dotação do
  exercício, para a execução orçamentária ter percentual.

## O que este seed NÃO faz

Não passa pelos serviços de domínio: eles carimbam `criado_em = agora` e
aplicam o rito, e nenhum dos dois permite datar no passado. Aqui a escrita é
direta no modelo, com as datas explícitas — é o preço de ter histórico, e é
por isso que este arquivo **não é** um atalho para criar despesa de verdade.
Para exercitar o fluxo real, use o `seed_demo_operacional`.

Não inventa fornecedor, natureza, fonte nem conta: reusa os que já existem no
tenant. Se faltarem, ele recusa e manda rodar o `seed_demo` antes — inventar
cadastro aqui criaria um segundo conjunto, divergente do que as telas de
cadastro mostram.

## Uso

    python -m app.cli.seed_demo_historico --tenant demo
    python -m app.cli.seed_demo_historico --tenant sobral --allow-non-demo
    python -m app.cli.seed_demo_historico --tenant sobral --allow-non-demo --reset

Idempotente: identifica o que criou pelo prefixo da descrição e não duplica.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import SessionLocal
from ..models import (
    ContaBancaria, Contrato, Debito, DebitoHistorico, Dotacao, FonteRecursos,
    Fornecedor, MovimentacaoConta, NaturezaDespesa, Parcela, Tenant, UnidadeTrabalho, Usuario,
)
from ..services import pagamentos_estados as est

# Marca o que este seed criou. O reset apaga exatamente por ela.
MARCA = "[HIST]"

# Objetos de despesa plausíveis para uma prefeitura. Só texto — os cadastros
# (fornecedor, natureza, fonte) vêm do que já existe no tenant.
_OBJETOS = [
    "Aquisição de medicamentos básicos",
    "Combustível da frota municipal",
    "Alimentação escolar",
    "Material de expediente",
    "Serviços de limpeza urbana",
    "Manutenção predial",
    "Energia elétrica de prédios públicos",
    "Locação de veículos",
    "Serviços de informática",
    "Material de construção",
    "Transporte escolar",
    "Serviços de vigilância",
]

# Idades (em dias) das despesas deixadas em tramitação — uma por faixa do
# gráfico de envelhecimento.
_IDADES_EM_CURSO = [3, 6, 12, 25, 50]

# Vencimentos futuros, um por janela da previsão.
_VENCIMENTOS_FUTUROS = [5, 12, 25, 50, 80]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _guard_tenant_slug(slug: str, allow_non_demo: bool) -> None:
    """Mesmo guard dos demais seeds: dado fictício em tenant que não é de
    demonstração exige intenção declarada."""
    if not slug.startswith("demo") and not allow_non_demo:
        print(
            f"[seed_demo_historico] RECUSADO: tenant '{slug}' não começa com 'demo'.\n"
            f"  Use --allow-non-demo se a intenção é mesmo semear neste tenant.",
            file=sys.stderr,
        )
        sys.exit(2)


def _sessao(tenant_id: int) -> AsyncSession:
    db = SessionLocal()
    db.info["tenant_id"] = int(tenant_id)
    return db


async def _tenant_id(db: AsyncSession, slug: str) -> int:
    tid = (await db.execute(select(Tenant.id).where(Tenant.slug == slug))).scalar_one_or_none()
    if tid is None:
        print(f"[seed_demo_historico] Tenant '{slug}' não existe.", file=sys.stderr)
        sys.exit(3)
    return tid


async def _cadastros(db: AsyncSession, tenant_id: int) -> dict:
    """Reusa o que existe. Recusa se faltar algo essencial."""
    async def _todos(modelo, *extra):
        cond = [modelo.tenant_id == tenant_id]
        if hasattr(modelo, "excluido"):
            cond.append(modelo.excluido.is_(False))
        cond.extend(extra)
        return list((await db.execute(select(modelo).where(*cond))).scalars().all())

    dados = {
        "unidades": await _todos(UnidadeTrabalho),
        "fornecedores": await _todos(Fornecedor),
        "naturezas": await _todos(NaturezaDespesa),
        "fontes": await _todos(FonteRecursos),
        "contas": await _todos(ContaBancaria, ContaBancaria.ativa.is_(True)),
        "contratos": await _todos(Contrato),
        "dotacoes": await _todos(Dotacao),
    }
    faltando = [k for k in ("unidades", "fornecedores", "naturezas", "fontes", "contas")
                if not dados[k]]
    if faltando:
        print(
            f"[seed_demo_historico] RECUSADO: faltam cadastros no tenant: {', '.join(faltando)}.\n"
            f"  Rode o `seed_demo` (e o `seed_demo_operacional`) antes — este seed reusa os\n"
            f"  cadastros existentes de propósito, para não criar um conjunto paralelo.",
            file=sys.stderr,
        )
        sys.exit(4)

    usuario = (await db.execute(select(Usuario.id).where(
        Usuario.tenant_id == tenant_id, Usuario.excluido.is_(False)))).scalars().first()
    if usuario is None:
        print("[seed_demo_historico] Nenhum usuário no tenant.", file=sys.stderr)
        sys.exit(5)
    dados["usuario_id"] = usuario
    return dados


def _conta_da_fonte(contas: list[ContaBancaria], id_fonte: int) -> ContaBancaria | None:
    """A conta pagadora tem de ser da MESMA fonte do empenho — é a regra que a
    autorização aplica de verdade. Semear fora dela produziria um histórico que
    o próprio sistema recusaria criar."""
    candidatas = [c for c in contas if c.id_fonte_recursos == id_fonte]
    return candidatas[0] if candidatas else None


# Até quanto da dotação o histórico pode consumir. Abaixo de 100% de
# propósito: uma demonstração em que TODAS as dotações aparecem estouradas não
# demonstra nada — vira ruído vermelho. E o que sobra sem vínculo alimenta,
# com verdade, o aviso de "despesa sem dotação" que a tela faz questão de dar.
_TETO_EXECUCAO = Decimal("0.70")


def _dotacao_com_espaco(dotacoes: list[Dotacao], consumido: dict[int, Decimal],
                        exercicio: int, id_fonte: int, valor: Decimal) -> Dotacao | None:
    """Dotação do exercício e da fonte que ainda comporta `valor`.

    Sem o teto, 12 meses de despesa contra uma dotação anual produziriam
    execução de centenas por cento. Quem não couber fica sem dotação — que é
    um estado real e previsto, não um erro.
    """
    for d in dotacoes:
        if d.exercicio != exercicio or d.id_fonte_recursos != id_fonte:
            continue
        limite = (d.valor_inicial or Decimal("0")) * _TETO_EXECUCAO
        if consumido.get(d.id, Decimal("0")) + valor <= limite:
            consumido[d.id] = consumido.get(d.id, Decimal("0")) + valor
            return d
    return None


def _primeiro_dia(hoje: date, meses_atras: int) -> date:
    total = hoje.year * 12 + (hoje.month - 1) - meses_atras
    ano, mes0 = divmod(total, 12)
    return date(ano, mes0 + 1, 1)


async def _ja_semeado(db: AsyncSession, tenant_id: int) -> int:
    return (await db.execute(select(Debito).where(
        Debito.tenant_id == tenant_id,
        Debito.descricao.like(f"{MARCA}%")))).scalars().first() is not None


def _novo_debito(*, tenant_id, cad, rnd, descricao, valor, competencia,
                 criado_em, exercicio) -> Debito:
    fonte = rnd.choice(cad["fontes"])
    contrato = None
    if cad["contratos"] and rnd.random() < 0.6:
        contrato = rnd.choice(cad["contratos"])
    return Debito(
        tenant_id=tenant_id,
        id_fornecedor=rnd.choice(cad["fornecedores"]).id,
        id_natureza=rnd.choice(cad["naturezas"]).id,
        id_fonte_recursos=fonte.id,
        id_contrato=contrato.id if contrato else None,
        id_unidade=rnd.choice(cad["unidades"]).id,
        valor_total=valor,
        competencia=competencia,
        descricao=descricao,
        criticidade="MEDIA",
        urgente=False,
        situacao_tramitacao=est.RASCUNHO,
        situacao_fila=est.NAO_REGISTRADA,
        situacao_pagamento=est.NAO_INICIADA,
        id_usuario_solicitante=cad["usuario_id"],
        exercicio=exercicio,
        criado_em=criado_em,
        atualizado_em=criado_em,
    )


def _historico(tenant_id: int, debito_id: int, acao: str, status: str,
               quando: datetime, usuario_id: int) -> DebitoHistorico:
    return DebitoHistorico(
        tenant_id=tenant_id, id_debito=debito_id, acao=acao,
        status_anterior=None, status_novo=status,
        justificativa=f"{MARCA} histórico de demonstração",
        id_usuario=usuario_id, criado_em=quando, versao_debito=1)


async def aplicar(slug: str, meses: int, por_mes: int, semente: int) -> dict:
    rnd = random.Random(semente)
    async with SessionLocal() as s0:
        tid = await _tenant_id(s0, slug)

    async with _sessao(tid) as db:
        if await _ja_semeado(db, tid):
            return {"status": "já semeado — nada a fazer (use --reset para refazer)"}
        cad = await _cadastros(db, tid)
        hoje = _utcnow().date()
        agora = _utcnow()

        executadas = 0
        em_curso = 0
        a_vencer = 0
        # Quanto de cada dotação o histórico já consumiu, para respeitar o teto.
        consumido: dict[int, Decimal] = {}

        # ------------------------------------------------ meses já executados
        for atras in range(meses, 0, -1):
            inicio = _primeiro_dia(hoje, atras)
            competencia = f"{inicio.year:04d}-{inicio.month:02d}"
            quantos = max(1, por_mes + rnd.randint(-1, 2))
            for _ in range(quantos):
                dia = min(rnd.randint(2, 26), 28)
                data_mov = date(inicio.year, inicio.month, dia)
                criado = datetime.combine(data_mov - timedelta(days=rnd.randint(5, 20)),
                                          datetime.min.time())
                valor = Decimal(rnd.randrange(1_500, 180_000)).quantize(Decimal("1.00"))
                d = _novo_debito(
                    tenant_id=tid, cad=cad, rnd=rnd,
                    descricao=f"{MARCA} {rnd.choice(_OBJETOS)}",
                    valor=valor, competencia=competencia, criado_em=criado,
                    exercicio=inicio.year)
                conta = _conta_da_fonte(cad["contas"], d.id_fonte_recursos)
                if conta is None:
                    continue
                # Executada: autorizada, paga e conciliada no mês.
                d.situacao_tramitacao = est.AUTORIZADA
                d.situacao_fila = est.REGISTRADA
                d.situacao_pagamento = est.PAGA
                d.id_conta_pagadora = conta.id
                d.id_conta = conta.id
                d.liquidacao_confirmada = True
                d.data_liquidacao = data_mov - timedelta(days=2)
                d.valor_empenhado = valor
                d.valor_liquidado = valor
                d.revisado = True
                dot = _dotacao_com_espaco(cad["dotacoes"], consumido, inicio.year,
                                          d.id_fonte_recursos, valor)
                if dot is not None:
                    d.id_dotacao = dot.id
                db.add(d)
                await db.flush()

                autorizado_em = datetime.combine(data_mov - timedelta(days=3),
                                                 datetime.min.time())
                db.add(_historico(tid, d.id, "CRIADO", "RASCUNHO", criado, cad["usuario_id"]))
                db.add(_historico(tid, d.id, "AUTORIZADO", "AUTORIZADO", autorizado_em,
                                  cad["usuario_id"]))

                mov = MovimentacaoConta(
                    tenant_id=tid, id_conta=conta.id, tipo="SAIDA", valor=valor,
                    origem="PAGAMENTO", id_debito=d.id, data=data_mov,
                    id_usuario=cad["usuario_id"],
                    descricao=f"{MARCA} pagamento de {d.descricao}",
                    criado_em=datetime.combine(data_mov, datetime.min.time()))
                db.add(mov)
                await db.flush()

                db.add(Parcela(
                    tenant_id=tid, id_debito=d.id, numero=1, valor=valor,
                    vencimento=data_mov, status="PAGA", data_pagamento=data_mov,
                    forma_pagamento="TED", id_movimentacao=mov.id,
                    criado_em=criado))
                executadas += 1
        await db.commit()

        # -------------------------------------- em tramitação, idades variadas
        for idade in _IDADES_EM_CURSO:
            quando = agora - timedelta(days=idade)
            valor = Decimal(rnd.randrange(4_000, 90_000)).quantize(Decimal("1.00"))
            d = _novo_debito(
                tenant_id=tid, cad=cad, rnd=rnd,
                descricao=f"{MARCA} {rnd.choice(_OBJETOS)}",
                valor=valor, competencia=f"{hoje.year:04d}-{hoje.month:02d}",
                criado_em=quando, exercicio=hoje.year)
            d.situacao_tramitacao = rnd.choice(
                [est.AGUARDANDO_GESTOR, est.AGUARDANDO_VALIDACAO, est.AGUARDANDO_AUTORIDADE])
            db.add(d)
            await db.flush()
            db.add(_historico(tid, d.id, "CRIADO", "RASCUNHO", quando, cad["usuario_id"]))
            db.add(Parcela(
                tenant_id=tid, id_debito=d.id, numero=1, valor=valor,
                vencimento=hoje + timedelta(days=30), status="A_PAGAR", criado_em=quando))
            em_curso += 1
        await db.commit()

        # ------------------------------------ autorizadas, com parcela a vencer
        for dias in _VENCIMENTOS_FUTUROS:
            valor = Decimal(rnd.randrange(6_000, 120_000)).quantize(Decimal("1.00"))
            criado = agora - timedelta(days=rnd.randint(5, 25))
            d = _novo_debito(
                tenant_id=tid, cad=cad, rnd=rnd,
                descricao=f"{MARCA} {rnd.choice(_OBJETOS)}",
                valor=valor, competencia=f"{hoje.year:04d}-{hoje.month:02d}",
                criado_em=criado, exercicio=hoje.year)
            conta = _conta_da_fonte(cad["contas"], d.id_fonte_recursos)
            if conta is None:
                continue
            d.situacao_tramitacao = est.AUTORIZADA
            d.situacao_fila = est.REGISTRADA
            d.situacao_pagamento = est.NAO_INICIADA
            d.id_conta_pagadora = conta.id
            d.id_conta = conta.id
            d.liquidacao_confirmada = True
            d.data_liquidacao = hoje - timedelta(days=2)
            dot = _dotacao_com_espaco(cad["dotacoes"], consumido, hoje.year,
                                      d.id_fonte_recursos, valor)
            if dot is not None:
                d.id_dotacao = dot.id
                d.valor_empenhado = valor
                d.revisado = True
            db.add(d)
            await db.flush()
            db.add(_historico(tid, d.id, "CRIADO", "RASCUNHO", criado, cad["usuario_id"]))
            db.add(_historico(tid, d.id, "AUTORIZADO", "AUTORIZADO",
                              criado + timedelta(days=2), cad["usuario_id"]))
            db.add(Parcela(
                tenant_id=tid, id_debito=d.id, numero=1, valor=valor,
                vencimento=hoje + timedelta(days=dias), status="A_PAGAR", criado_em=criado))
            a_vencer += 1
        await db.commit()

    return {"meses": meses, "executadas": executadas, "em_tramitacao": em_curso,
            "a_vencer": a_vencer}


async def resetar(slug: str) -> dict:
    """Apaga só o que este seed criou, pela marca na descrição."""
    async with SessionLocal() as s0:
        tid = await _tenant_id(s0, slug)
    async with _sessao(tid) as db:
        ids = list((await db.execute(select(Debito.id).where(
            Debito.tenant_id == tid, Debito.descricao.like(f"{MARCA}%")))).scalars().all())
        if not ids:
            return {"removidos": 0}
        await db.execute(delete(Parcela).where(Parcela.id_debito.in_(ids)))
        await db.execute(delete(DebitoHistorico).where(DebitoHistorico.id_debito.in_(ids)))
        await db.execute(delete(MovimentacaoConta).where(
            MovimentacaoConta.tenant_id == tid,
            MovimentacaoConta.id_debito.in_(ids)))
        await db.execute(delete(Debito).where(Debito.id.in_(ids)))
        await db.commit()
    return {"removidos": len(ids)}


def main() -> None:
    p = argparse.ArgumentParser(description="Histórico de demonstração do módulo Despesa")
    p.add_argument("--tenant", default="demo", help="slug do tenant")
    p.add_argument("--meses", type=int, default=12, help="quantos meses de histórico")
    p.add_argument("--por-mes", type=int, default=6, help="despesas executadas por mês")
    p.add_argument("--semente", type=int, default=20261125,
                   help="semente do sorteio — mesma semente, mesmo resultado")
    p.add_argument("--allow-non-demo", action="store_true")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()

    _guard_tenant_slug(args.tenant, args.allow_non_demo)
    out = asyncio.run(
        resetar(args.tenant) if args.reset
        else aplicar(args.tenant, args.meses, args.por_mes, args.semente))
    print(f"[seed_demo_historico] OK: {out}")


if __name__ == "__main__":
    main()

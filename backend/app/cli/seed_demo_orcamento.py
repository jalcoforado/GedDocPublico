"""Seed de demonstração do ORÇAMENTO (O1).

Cria dotações, créditos adicionais e vincula parte das despesas existentes,
para a tela de execução orçamentária ter o que mostrar numa demonstração.

**Monta de propósito os quatro estados que a tela precisa saber contar**, e não
só o caso feliz — é justamente neles que o painel prova que não inventa número:

1. Dotação com execução saudável.
2. Dotação **estourada** (empenhado acima da dotação atualizada).
3. Despesa vinculada **sem retorno de empenho** — execução que é piso, não
   número final.
4. Despesa **sem dotação** — contada à parte, nunca rateada.

Idempotente: identifica as dotações pelo prefixo DEMO na ação e não duplica.
Os valores são fictícios e o texto da descrição diz isso.

    python -m app.cli.seed_demo_orcamento            # aplica no tenant 1
    python -m app.cli.seed_demo_orcamento --tenant 2
    python -m app.cli.seed_demo_orcamento --reset    # remove só o que criou
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import delete, select

from ..database import SessionLocal
from ..models import CreditoAdicional, Debito, Dotacao, FonteRecursos, UnidadeTrabalho

# Prefixo que marca o que é demonstração — é por ele que o reset identifica.
MARCA = "DEMO-ORC"

# (sufixo da ação, função, subfunção, programa, descrição, valor inicial, código da fonte)
_DOTACOES = [
    ("2001", "10", "301", "0012", "Manutenção da Atenção Básica (demonstração)",
     "900000.00", "DEMO-1600"),
    ("2002", "12", "361", "0020", "Manutenção do Ensino Fundamental (demonstração)",
     "1200000.00", "DEMO-1540"),
    ("2003", "04", "122", "0001", "Manutenção da Administração Geral (demonstração)",
     "600000.00", "DEMO-1500"),
    ("2004", "15", "452", "0033", "Limpeza Urbana e Serviços Continuados (demonstração)",
     "300000.00", "DEMO-1500"),
    ("2005", "08", "244", "0041", "Proteção Social Básica (demonstração)",
     "150000.00", "DEMO-1500"),
]

# Créditos: uma suplementação e uma anulação, para a dotação atualizada
# diferir da inicial e a conta ficar visível na tela.
_CREDITOS = [
    ("2001", "SUPLEMENTAR", "150000.00", "Decreto 045/2026 (demonstração)"),
    ("2003", "ANULACAO", "80000.00", "Decreto 046/2026 (demonstração)"),
]


async def _unidade_padrao(s, tenant_id: int) -> int:
    uid = (await s.execute(select(UnidadeTrabalho.id).where(
        UnidadeTrabalho.tenant_id == tenant_id).order_by(UnidadeTrabalho.id))).scalars().first()
    if uid is None:
        raise SystemExit("Nenhuma unidade de trabalho no tenant — rode o seed_bootstrap antes.")
    return uid


async def _fontes(s, tenant_id: int) -> dict[str, int]:
    rows = (await s.execute(select(FonteRecursos.codigo, FonteRecursos.id).where(
        FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False)))).all()
    return {c: i for c, i in rows}


async def aplicar(tenant_id: int) -> dict:
    async with SessionLocal() as s:
        unidade = await _unidade_padrao(s, tenant_id)
        fontes = await _fontes(s, tenant_id)
        if not fontes:
            raise SystemExit("Nenhuma fonte de recursos — rode o seed_demo antes.")
        alguma_fonte = next(iter(fontes.values()))

        criadas: dict[str, Dotacao] = {}
        for sufixo, funcao, subfuncao, programa, descricao, valor, cod_fonte in _DOTACOES:
            acao = f"{MARCA}-{sufixo}"
            ja = (await s.execute(select(Dotacao).where(
                Dotacao.tenant_id == tenant_id, Dotacao.acao == acao,
                Dotacao.excluido.is_(False)))).scalar_one_or_none()
            if ja is not None:
                criadas[sufixo] = ja
                continue
            d = Dotacao(
                tenant_id=tenant_id, exercicio=2026, id_unidade=unidade,
                funcao=funcao, subfuncao=subfuncao, programa=programa, acao=acao,
                natureza_codigo="3.3.90.30", grupo_despesa="CUSTEIO",
                id_fonte_recursos=fontes.get(cod_fonte, alguma_fonte),
                descricao=descricao, valor_inicial=Decimal(valor), criado_em=datetime.utcnow())
            s.add(d)
            await s.flush()
            criadas[sufixo] = d
        await s.commit()

        for sufixo, tipo, valor, ato in _CREDITOS:
            dot = criadas.get(sufixo)
            if dot is None:
                continue
            ja = (await s.execute(select(CreditoAdicional).where(
                CreditoAdicional.tenant_id == tenant_id, CreditoAdicional.id_dotacao == dot.id,
                CreditoAdicional.ato == ato, CreditoAdicional.excluido.is_(False),
            ))).scalar_one_or_none()
            if ja is not None:
                continue
            s.add(CreditoAdicional(
                tenant_id=tenant_id, id_dotacao=dot.id, tipo=tipo, valor=Decimal(valor),
                data=date(2026, 6, 1), ato=ato,
                justificativa="Lançamento de demonstração", criado_em=datetime.utcnow()))
        await s.commit()

        # Vincula despesas. A regra de distribuição é deliberada: parte com
        # retorno de empenho, parte sem, e um terço fica SEM dotação — é o que
        # faz a tela mostrar as três leituras diferentes.
        debitos = list((await s.execute(select(Debito).where(
            Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
            Debito.id_dotacao.is_(None)).order_by(Debito.id))).scalars().all())
        ordem = ["2001", "2002", "2003", "2004", "2005"]
        vinculados = com_retorno = 0
        for i, deb in enumerate(debitos):
            if i % 3 == 2:
                continue  # fica sem dotação, de propósito
            dot = criadas[ordem[i % len(ordem)]]
            deb.id_dotacao = dot.id
            deb.exercicio = 2026
            vinculados += 1
            # Dois de cada três vinculados recebem o "retorno do sistema
            # financeiro"; o terceiro fica sem, para a tela avisar.
            if i % 3 == 0:
                deb.valor_empenhado = deb.valor_total
                deb.revisado = True
                com_retorno += 1
            deb.atualizado_em = datetime.utcnow()

        # Estoura a dotação 2005 de propósito: é a menor, e precisa de um
        # empenho acima dela para a faixa vermelha aparecer.
        pequena = criadas.get("2005")
        if pequena is not None and debitos:
            alvo = debitos[0]
            alvo.id_dotacao = pequena.id
            alvo.exercicio = 2026
            alvo.valor_empenhado = Decimal("200000.00")
            alvo.revisado = True
        await s.commit()

    return {"dotacoes": len(criadas), "debitos_vinculados": vinculados,
            "com_retorno_de_empenho": com_retorno}


async def resetar(tenant_id: int) -> dict:
    """Remove só o que este seed criou — nada mais."""
    async with SessionLocal() as s:
        ids = list((await s.execute(select(Dotacao.id).where(
            Dotacao.tenant_id == tenant_id, Dotacao.acao.like(f"{MARCA}-%")))).scalars().all())
        if not ids:
            return {"removidas": 0}
        await s.execute(delete(CreditoAdicional).where(CreditoAdicional.id_dotacao.in_(ids)))
        for deb in (await s.execute(select(Debito).where(
                Debito.tenant_id == tenant_id, Debito.id_dotacao.in_(ids)))).scalars().all():
            deb.id_dotacao = None
        await s.flush()
        await s.execute(delete(Dotacao).where(Dotacao.id.in_(ids)))
        await s.commit()
    return {"removidas": len(ids)}


def main() -> None:
    p = argparse.ArgumentParser(description="Seed de demonstração do orçamento")
    p.add_argument("--tenant", type=int, default=1)
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()
    out = asyncio.run(resetar(args.tenant) if args.reset else aplicar(args.tenant))
    print(f"[seed_demo_orcamento] OK: {out}")


if __name__ == "__main__":
    main()

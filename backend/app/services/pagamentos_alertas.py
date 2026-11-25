"""Central de alertas gerenciais (fatia 6, §11 do brief).

Formaliza o que o painel já detectava solto (`pagamentos_dashboard._alertas`)
num formato único: cada alerta diz **o que aconteceu, quanto custa, onde,
de onde saiu o número, o que fazer e por onde ir ver**.

Três regras que este módulo segue e que valem mais que a lista de alertas:

1. **Alerta sem ação não entra.** Aviso que não diz o que fazer é barulho, e o
   gestor que aprende a ignorar o barulho ignora junto o que importa.
2. **Só fato, nunca estatística apresentada como irregularidade.** Todo alerta
   daqui é verificável no banco: a parcela venceu, o saldo não cobre, a coluna
   está vazia. Concentração de fornecedor, gasto acima da média e afins são
   *observações estatísticas* — o §11 do brief proíbe expressamente
   apresentá-las como irregularidade ou fraude, e elas não estão aqui. Quando
   entrarem, entram como leitura de painel, com outra palavra e outro lugar.
3. **A severidade é do impacto, não do susto.** CRITICO é dinheiro que já
   deveria ter saído ou obrigação sem lastro; ALTO é o que vence na semana;
   MEDIO é operacional; INFORMATIVO é lacuna de cadastro que atrapalha a
   leitura mas não quebra nada hoje.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ContaBancaria, Debito, FonteRecursos, Parcela
from ..schemas.pagamentos import AlertaItem, AlertasOut
from . import pagamentos_caixa as caixa
from . import pagamentos_estados as est
from . import pagamentos_filas as filas

_ABERTAS = ("A_PAGAR", "LIBERADA")
_TEM_RESERVA = and_(Debito.situacao_tramitacao == est.AUTORIZADA,
                    Debito.situacao_pagamento.notin_((est.PAGA, est.CONCILIADA)))

_ORDEM = {"CRITICO": 0, "ALTO": 1, "MEDIO": 2, "INFORMATIVO": 3}


def _utcnow() -> datetime:
    return datetime.utcnow()


def _brl(v: Decimal) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def montar_alertas(db: AsyncSession, *, tenant_id: int) -> AlertasOut:
    hoje = _utcnow().date()
    itens: list[AlertaItem] = []
    painel = await caixa.painel_caixa(db, tenant_id=tenant_id)

    # ---------------------------------------------------- 1. obrigações vencidas
    vencidas_valor, vencidas_qtd = (await db.execute(
        select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
        .join(Debito, Debito.id == Parcela.id_debito)
        .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
               Parcela.status.in_(_ABERTAS), Debito.excluido.is_(False),
               _TEM_RESERVA, Parcela.vencimento < hoje))).one()
    if vencidas_qtd:
        itens.append(AlertaItem(
            codigo="parcelas_vencidas", severidade="CRITICO",
            titulo="Obrigações vencidas e não pagas",
            descricao=(f"{vencidas_qtd} "
                       f"{'parcela venceu' if vencidas_qtd == 1 else 'parcelas venceram'} "
                       f"e continua em aberto, somando {_brl(Decimal(vencidas_valor))}. "
                       "Atraso em despesa autorizada afeta a ordem cronológica de pagamento."),
            impacto_valor=Decimal(vencidas_valor), impacto_qtd=int(vencidas_qtd),
            origem="pagamentos.parcela em aberto com vencimento anterior a hoje, "
                   "de débitos autorizados ainda não pagos",
            acao="Abrir a tesouraria e liberar o pagamento, ou registrar o motivo do atraso.",
            href="/m/pagamentos/tesouraria"))

    # ------------------------------------------------- 2. vence nos próximos 7 dias
    prox_valor, prox_qtd = (await db.execute(
        select(func.coalesce(func.sum(Parcela.valor), 0), func.count(Parcela.id))
        .join(Debito, Debito.id == Parcela.id_debito)
        .where(Parcela.tenant_id == tenant_id, Parcela.excluido.is_(False),
               Parcela.status.in_(_ABERTAS), Debito.excluido.is_(False), _TEM_RESERVA,
               Parcela.vencimento >= hoje,
               Parcela.vencimento <= hoje + timedelta(days=7)))).one()
    if prox_qtd:
        itens.append(AlertaItem(
            codigo="vence_7_dias", severidade="ALTO",
            titulo="Vencimentos nos próximos 7 dias",
            descricao=(f"{prox_qtd} {'parcela vence' if prox_qtd == 1 else 'parcelas vencem'} "
                       f"até {(hoje + timedelta(days=7)).strftime('%d/%m')}, "
                       f"somando {_brl(Decimal(prox_valor))}."),
            impacto_valor=Decimal(prox_valor), impacto_qtd=int(prox_qtd),
            origem="pagamentos.parcela em aberto de débitos autorizados, por vencimento",
            acao="Conferir na previsão financeira se o caixa das contas envolvidas cobre.",
            href="/m/pagamentos/previsao"))

    # ------------------------------------------- 3. conta com obrigação sem lastro
    for c in painel:
        if c.disponivel < 0:
            itens.append(AlertaItem(
                codigo="conta_sem_lastro", severidade="CRITICO",
                titulo="Conta com compromissos acima do saldo",
                descricao=(f"Os compromissos da conta passam do saldo em "
                           f"{_brl(-c.disponivel)}. Autorizar nova despesa nela depende "
                           "de entrada de recurso."),
                impacto_valor=-c.disponivel, escopo=c.nome,
                origem="saldo bancário menos comprometido e bloqueado (pagamentos_caixa.saldo_conta)",
                acao="Remanejar dentro da mesma fonte ou aguardar entrada antes de autorizar.",
                href=f"/m/pagamentos/caixa?conta={c.id_conta}"))

    # ------------------------------------------------- 4. conta abaixo do mínimo
    for c in painel:
        if c.abaixo_minimo and c.disponivel >= 0:
            itens.append(AlertaItem(
                codigo="conta_abaixo_minimo", severidade="MEDIO",
                titulo="Conta abaixo do saldo mínimo",
                descricao=(f"O saldo está em {_brl(c.saldo_atual)}, abaixo do mínimo de "
                           f"{_brl(c.saldo_minimo_alerta)} definido no cadastro."),
                impacto_valor=c.saldo_minimo_alerta - c.saldo_atual, escopo=c.nome,
                origem="conta_bancaria.saldo_minimo_alerta comparado ao saldo apurado",
                acao="Revisar o mínimo no cadastro da conta ou programar aporte.",
                href=f"/m/pagamentos/caixa?conta={c.id_conta}"))

    # --------------------------------------------- 5. fonte sem lastro p/ autorizar
    impacto = await filas.impacto_autorizacoes(db, tenant_id=tenant_id)
    for f in impacto.fontes:
        if not f.suficiente:
            itens.append(AlertaItem(
                codigo="fonte_sem_lastro_para_pendencias", severidade="ALTO",
                titulo="Fonte não cobre o que aguarda autorização",
                descricao=(f"Há {_brl(f.pendente)} aguardando decisão nesta fonte e o disponível dela é "
                           f"{_brl(f.disponivel_antes)}. Faltam {_brl(f.falta)}. Saldo de outras "
                           "fontes não serve: a fonte do empenho é vinculante."),
                impacto_valor=f.falta, impacto_qtd=f.qtd_debitos,
                escopo=f"{f.codigo} — {f.descricao}",
                origem="pendências em AGUARDANDO_AUTORIDADE contra as contas elegíveis da fonte",
                acao="Autorizar só o que couber, ou providenciar recurso na fonte.",
                href="/m/pagamentos/autorizacao"))

    # ----------------------------------- 6. débito autorizado sem conta pagadora
    sem_conta = (await db.execute(select(func.count(Debito.id)).where(
        Debito.tenant_id == tenant_id, Debito.excluido.is_(False),
        Debito.situacao_tramitacao == est.AUTORIZADA,
        Debito.id_conta_pagadora.is_(None)))).scalar_one()
    if sem_conta:
        itens.append(AlertaItem(
            codigo="autorizado_sem_conta_pagadora", severidade="ALTO",
            titulo="Despesa autorizada sem conta pagadora",
            descricao=(f"{sem_conta} "
                       f"{'despesa autorizada está' if sem_conta == 1 else 'despesas autorizadas estão'} "
                       "sem conta pagadora gravada. A conta é escolhida no ato de autorizar, "
                       "então isto não deveria acontecer — e, enquanto durar, a reserva não "
                       "aparece no comprometido de nenhuma conta."),
            impacto_qtd=int(sem_conta),
            origem="débitos AUTORIZADA com id_conta_pagadora nulo",
            acao="Abrir cada despesa e conferir a autorização; avisar o suporte se persistir.",
            href="/m/pagamentos/autorizacao"))

    # ------------------------------- 7. fonte sem vinculação cadastrada (lacuna)
    fontes_sem_vinc = (await db.execute(select(func.count(FonteRecursos.id)).where(
        FonteRecursos.tenant_id == tenant_id, FonteRecursos.excluido.is_(False),
        FonteRecursos.tipo_vinculacao.is_(None)))).scalar_one()
    if fontes_sem_vinc:
        itens.append(AlertaItem(
            codigo="fonte_sem_vinculacao", severidade="INFORMATIVO",
            titulo="Fontes sem vinculação cadastrada",
            descricao=(f"{fontes_sem_vinc} "
                       f"{'fonte está' if fontes_sem_vinc == 1 else 'fontes estão'} sem o tipo de "
                       "vinculação preenchido. Enquanto isso, o painel não consegue separar "
                       "recurso livre de recurso vinculado, e o “disponível” não deve ser lido "
                       "como dinheiro de livre aplicação."),
            impacto_qtd=int(fontes_sem_vinc),
            origem="pagamentos.fonte_recursos com tipo_vinculacao nulo",
            acao="Preencher a vinculação em Cadastros → Fontes de recursos.",
            href="/m/pagamentos/cadastros/fontes"))

    # ----------------------------------------- 8. saldo da conta desatualizado
    desatualizadas = []
    for c in painel:
        atualizado = await caixa.ultima_atualizacao_conta(db, tenant_id=tenant_id,
                                                          conta_id=c.id_conta)
        if atualizado is None or atualizado.date() < hoje:
            desatualizadas.append(c.nome)
    if desatualizadas:
        qtd = len(desatualizadas)
        itens.append(AlertaItem(
            codigo="saldo_desatualizado", severidade="MEDIO",
            titulo="Contas sem movimentação registrada hoje",
            descricao=(f"{qtd} {'conta não teve' if qtd == 1 else 'contas não tiveram'} "
                       "movimentação lançada hoje. O saldo mostrado pode estar atrás do extrato "
                       "do banco."),
            impacto_qtd=qtd, escopo=", ".join(desatualizadas[:3]) + ("…" if qtd > 3 else ""),
            origem="última movimentacao_conta de cada conta, comparada ao dia corrente",
            acao="Importar o extrato e conciliar.",
            href="/m/pagamentos/conciliacao"))

    itens.sort(key=lambda a: (_ORDEM[a.severidade], -(a.impacto_valor or Decimal("0"))))
    return AlertasOut(
        itens=itens,
        criticos=sum(1 for a in itens if a.severidade == "CRITICO"),
        altos=sum(1 for a in itens if a.severidade == "ALTO"),
        medios=sum(1 for a in itens if a.severidade == "MEDIO"),
        informativos=sum(1 for a in itens if a.severidade == "INFORMATIVO"),
        apurado_em=_utcnow())

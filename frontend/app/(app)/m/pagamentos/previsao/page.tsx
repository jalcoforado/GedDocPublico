"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, TrendingDown, Wallet } from "lucide-react";
import Link from "next/link";

import { NavVisaoFinanceiro } from "@/components/pagamentos/NavVisaoFinanceiro";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { GraficoCard } from "@/components/ui/grafico-card";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { api } from "@/lib/api";
import { GRAFICO } from "@/lib/chart-theme";

const fmtBRL = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtData = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("pt-BR");

const pct = (parte: number, todo: number) => (todo <= 0 ? 0 : (parte / todo) * 100);

export default function PrevisaoPage() {
  const q = useQuery({
    queryKey: ["pag-previsao"],
    queryFn: () => api.pagamentos.previsao(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        icon={CalendarClock}
        title="Previsão financeira"
        description="O que vence nos próximos dias e como fica o caixa se tudo for pago no vencimento."
      />
      <NavVisaoFinanceiro />

      {/* A limitação vem ANTES dos números, não num rodapé: quem lê uma
          projeção precisa saber o que ela não inclui antes de confiar nela. */}
      <Alert intent="info">
        <strong className="font-semibold">Esta previsão é só do lado da saída.</strong> O Aprimora
        não tem módulo de receita, então repasses, arrecadação e convênios a receber{" "}
        <strong className="font-semibold">não entram nesta conta</strong>. Saldo projetado
        negativo aqui quer dizer “as obrigações conhecidas passam do dinheiro que está em caixa
        hoje” — não que vá faltar, porque a entrada que ainda vai acontecer não está somada.
      </Alert>

      {q.isLoading && <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />}

      {q.isError && (
        <EmptyState
          icon={CalendarClock}
          title="Não foi possível carregar a previsão"
          description="Tente de novo em instantes."
        />
      )}

      {q.data && <Conteudo d={q.data} />}
    </div>
  );
}

function Conteudo({ d }: { d: NonNullable<Awaited<ReturnType<typeof api.pagamentos.previsao>>> }) {
  const base = Number(d.base_projecao);
  const noventa = d.horizontes[d.horizontes.length - 1];
  const pior = d.horizontes.find((h) => !h.suficiente);

  const insight = pior ? (
    <>
      Em <strong className="font-semibold text-foreground">{pior.dias} dias</strong> as obrigações
      conhecidas passam do que há em caixa: o projetado fica em{" "}
      <strong className="font-semibold text-foreground">{fmtBRL(pior.saldo_projetado)}</strong>.
      Sem entrada de recurso, parte desses vencimentos não terá lastro.
    </>
  ) : noventa ? (
    <>
      Em 90 dias vencem{" "}
      <strong className="font-semibold text-foreground">{fmtBRL(noventa.vence_acumulado)}</strong>,{" "}
      {pct(Number(noventa.vence_acumulado), base).toLocaleString("pt-BR", {
        maximumFractionDigits: 1,
      })}
      % do que está em caixa hoje. O caixa cobre todos os vencimentos conhecidos do período.
    </>
  ) : null;

  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Em caixa hoje"
          value={fmtBRL(d.saldo_atual)}
          icon={Wallet}
          definicao="Saldo bancário somado de todas as contas não excluídas. É o ponto de partida da projeção."
        />
        <KpiCard
          label="Base da projeção"
          value={fmtBRL(d.base_projecao)}
          hint="saldo menos bloqueios"
          icon={Wallet}
          definicao="Saldo bancário menos os bloqueios administrativos vigentes. Parte do saldo, e não do disponível, porque o disponível já desconta estes mesmos vencimentos — usá-lo contaria cada obrigação duas vezes."
        />
        <KpiCard
          label="Vencidas em aberto"
          value={fmtBRL(d.vencidas_valor)}
          hint={d.vencidas_qtd === 1 ? "1 parcela" : `${d.vencidas_qtd} parcelas`}
          icon={AlertTriangle}
          intent={d.vencidas_qtd > 0 ? "danger" : "default"}
          definicao="Parcelas de despesas autorizadas cujo vencimento já passou e que seguem em aberto. Entram em todas as janelas da projeção: é dinheiro que ainda vai sair."
        />
        <KpiCard
          label="Contas em risco"
          value={String(d.contas_em_risco.length)}
          hint={d.contas_em_risco.length === 0 ? "nenhuma em 90 dias" : "no horizonte de 90 dias"}
          icon={TrendingDown}
          intent={d.contas_em_risco.length > 0 ? "danger" : "default"}
          definicao="Contas cujo saldo não cobre o que vence nelas em 90 dias. Saldo de uma conta não paga obrigação de outra, então o total saudável pode esconder uma conta no vermelho."
        />
      </div>

      <GraficoCard
        titulo="Como fica o caixa"
        subtitulo="Janelas cumulativas: 30 dias inclui o que vence em 7 e em 15"
        insight={insight}
      >
        <ul className="divide-y divide-border">
          {d.horizontes.map((h) => {
            const projetado = Number(h.saldo_projetado);
            const consumido = pct(Number(h.vence_acumulado), base);
            return (
              <li key={h.dias} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-foreground">
                      Próximos {h.dias} dias
                      <span className="font-normal text-foreground-subtle"> · até {fmtData(h.ate)}</span>
                    </span>
                    <span className="block text-xs text-foreground-subtle">
                      {h.qtd_parcelas === 0
                        ? "nenhum vencimento"
                        : `${h.qtd_parcelas} ${h.qtd_parcelas === 1 ? "parcela vence" : "parcelas vencem"} · ${fmtBRL(h.vence_acumulado)}`}
                      {Number(h.vence_na_janela) > 0 && h.dias !== 7
                        ? ` (${fmtBRL(h.vence_na_janela)} entram nesta janela)`
                        : ""}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span
                      className={
                        h.suficiente
                          ? "block text-sm font-semibold tabular-nums text-foreground"
                          : "block text-sm font-semibold tabular-nums text-danger-soft-foreground"
                      }
                    >
                      {fmtBRL(projetado)}
                    </span>
                    <span className="block text-xs text-foreground-subtle">saldo projetado</span>
                  </span>
                </div>
                <div
                  className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-surface-2"
                  role="img"
                  aria-label={`Em ${h.dias} dias: ${fmtBRL(h.vence_acumulado)} a pagar, saldo projetado ${fmtBRL(projetado)}`}
                >
                  <span
                    style={{
                      width: `${Math.min(consumido, 100)}%`,
                      backgroundColor: h.suficiente ? GRAFICO.alerta : GRAFICO.negativo,
                    }}
                  />
                </div>
              </li>
            );
          })}
        </ul>
      </GraficoCard>

      {d.contas_em_risco.length > 0 && (
        <GraficoCard
          titulo="Contas que não cobrem os próprios vencimentos"
          subtitulo="Horizonte de 90 dias · saldo de uma conta não paga obrigação de outra"
          insight="Remanejar entre contas depende da vinculação da fonte: recurso vinculado não cobre despesa de outra finalidade."
        >
          <ul className="divide-y divide-border">
            {d.contas_em_risco.map((c) => (
              <li key={c.id_conta} className="py-3">
                <Link
                  href={`/m/pagamentos/caixa?conta=${c.id_conta}`}
                  className="flex items-baseline justify-between gap-3 rounded-card transition-colors duration-fast hover:bg-surface-2"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">
                      {c.nome}
                    </span>
                    <span className="block text-xs text-foreground-subtle">
                      {fmtBRL(c.saldo_atual)} em caixa · {c.qtd_parcelas}{" "}
                      {c.qtd_parcelas === 1 ? "parcela" : "parcelas"} somando{" "}
                      {fmtBRL(c.vence_no_horizonte)}
                    </span>
                  </span>
                  <span className="shrink-0 text-right">
                    <span className="block text-sm font-semibold tabular-nums text-danger-soft-foreground">
                      faltam {fmtBRL(c.falta)}
                    </span>
                    <span className="block text-xs text-foreground-subtle">em 90 dias</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </GraficoCard>
      )}
    </>
  );
}

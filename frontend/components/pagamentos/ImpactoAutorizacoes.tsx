"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Building2, CheckCircle2 } from "lucide-react";
import type { ReactNode } from "react";

import { GraficoCard } from "@/components/ui/grafico-card";
import { api } from "@/lib/api";
import { GRAFICO } from "@/lib/chart-theme";

/**
 * "Se eu autorizar tudo isto, como fica o caixa?" — antes de decidir.
 *
 * Somente leitura: não autoriza, não reserva, não grava nada. A decisão
 * continua sendo o ato humano da fila abaixo, com alçada e segregação de
 * funções (§8 do brief: "o painel não deverá realizar autorizações
 * automaticamente").
 *
 * **A leitura que decide é a da FONTE, não a do total.** Um débito só pode ser
 * pago por conta da própria fonte, então o consolidado não responde se cabe:
 * R$ 500 mil parados numa fonte com R$ 80 mil continuam sem lastro mesmo com
 * milhões em outras contas. Por isso o total aparece pequeno, como
 * dimensionamento, e as fontes aparecem grandes, com a que não fecha no topo.
 */

const fmtBRL = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const fmtPct = (v: number) =>
  `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;

const pct = (parte: number, todo: number) => (todo <= 0 ? 0 : (parte / todo) * 100);

function Numero({
  rotulo,
  valor,
  detalhe,
  tom = "neutro",
}: {
  rotulo: string;
  valor: string;
  detalhe?: string;
  tom?: "neutro" | "risco" | "bom";
}) {
  const cor =
    tom === "risco"
      ? "text-danger-soft-foreground"
      : tom === "bom"
        ? "text-success-soft-foreground"
        : "text-foreground";
  return (
    <div className="min-w-0">
      <p className="text-[11px] font-medium uppercase tracking-wider text-foreground-muted">
        {rotulo}
      </p>
      <p className={`font-display text-xl font-bold leading-tight tabular-nums ${cor}`}>{valor}</p>
      {detalhe && <p className="mt-0.5 text-xs text-foreground-subtle">{detalhe}</p>}
    </div>
  );
}

export function ImpactoAutorizacoes() {
  const q = useQuery({
    queryKey: ["pag-impacto-autorizacoes"],
    queryFn: () => api.pagamentos.autorizacao.impacto(),
  });

  if (q.isLoading || q.isError || !q.data) return null;
  const d = q.data;
  if (d.qtd_debitos === 0) return null;

  const consumo = pct(Number(d.total_pendente), Number(d.disponivel_total));
  const insuficientes = d.fontes.filter((f) => !f.suficiente);

  const insight: ReactNode =
    insuficientes.length > 0 ? (
      <>
        {insuficientes.length === 1
          ? `A fonte ${insuficientes[0].codigo} não cobre o que aguarda decisão nela`
          : `${insuficientes.length} fontes não cobrem o que aguarda decisão nelas`}
        :{" "}
        <strong className="font-semibold text-foreground">
          {fmtBRL(insuficientes.reduce((a, f) => a + Number(f.falta), 0))}
        </strong>{" "}
        sem lastro. Autorizar tudo exigiria entrada de recurso nessas fontes — o saldo das
        outras contas não serve, porque a fonte do empenho é vinculante.
      </>
    ) : (
      <>
        Autorizar as {d.qtd_debitos} pendências consome{" "}
        <strong className="font-semibold text-foreground">{fmtPct(consumo)}</strong> do
        disponível das fontes envolvidas, e todas cobrem o que aguarda decisão nelas.
      </>
    );

  return (
    <GraficoCard
      titulo="Impacto de autorizar o que está pendente"
      subtitulo={`${d.qtd_debitos} ${d.qtd_debitos === 1 ? "despesa aguarda" : "despesas aguardam"} decisão · simulação, nada é autorizado aqui`}
      insight={insight}
    >
      <div className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Numero rotulo="A autorizar" valor={fmtBRL(d.total_pendente)} detalhe={`${d.qtd_debitos} despesas`} />
          <Numero rotulo="Disponível hoje" valor={fmtBRL(d.disponivel_total)} detalhe="nas fontes envolvidas" />
          <Numero
            rotulo="Depois de autorizar"
            valor={fmtBRL(d.disponivel_total_depois)}
            detalhe={`consome ${fmtPct(consumo)} do disponível`}
            tom={Number(d.disponivel_total_depois) < 0 ? "risco" : "neutro"}
          />
          <Numero
            rotulo="Fontes sem lastro"
            valor={String(d.fontes_insuficientes)}
            detalhe={d.fontes_insuficientes === 0 ? "todas cobrem" : "precisam de recurso"}
            tom={d.fontes_insuficientes > 0 ? "risco" : "bom"}
          />
        </div>

        {/* Fonte a fonte: é aqui que se decide. */}
        <ul className="divide-y divide-border border-t border-border">
          {d.fontes.map((f) => {
            const antes = Number(f.disponivel_antes);
            const depois = Number(f.disponivel_depois);
            const pendente = Number(f.pendente);
            const base = Math.max(antes, pendente, 1);
            return (
              <li key={f.id_fonte} className="py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-foreground">
                      {f.codigo} — {f.descricao}
                    </span>
                    <span className="block truncate text-xs text-foreground-subtle">
                      {f.qtd_debitos}{" "}
                      {f.qtd_debitos === 1 ? "despesa aguardando" : "despesas aguardando"} ·{" "}
                      {fmtBRL(f.pendente)}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2 text-right">
                    <span className="text-xs tabular-nums text-foreground-subtle">
                      {fmtBRL(antes)}
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-foreground-subtle" aria-hidden="true" />
                    <span
                      className={
                        f.suficiente
                          ? "text-sm font-semibold tabular-nums text-foreground"
                          : "text-sm font-semibold tabular-nums text-danger-soft-foreground"
                      }
                    >
                      {fmtBRL(depois)}
                    </span>
                  </span>
                </div>
                <div
                  className="mt-2 flex h-2 w-full overflow-hidden rounded-full bg-surface-2"
                  role="img"
                  aria-label={
                    f.suficiente
                      ? `${f.codigo}: sobra ${fmtBRL(depois)} depois de autorizar`
                      : `${f.codigo}: faltam ${fmtBRL(f.falta)}`
                  }
                >
                  <span
                    style={{
                      width: `${pct(Math.max(depois, 0), base)}%`,
                      backgroundColor: GRAFICO.positivo,
                    }}
                  />
                  <span
                    style={{
                      width: `${pct(Math.min(pendente, antes), base)}%`,
                      backgroundColor: GRAFICO.alerta,
                    }}
                  />
                  {!f.suficiente && (
                    <span
                      className="animate-pulse motion-reduce:animate-none"
                      style={{
                        width: `${pct(Number(f.falta), base)}%`,
                        backgroundColor: GRAFICO.negativo,
                      }}
                    />
                  )}
                </div>
                {!f.suficiente && (
                  <p className="mt-1.5 flex items-center gap-1.5 text-xs text-danger-soft-foreground">
                    <AlertTriangle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    Faltam {fmtBRL(f.falta)} nesta fonte.
                  </p>
                )}
              </li>
            );
          })}
        </ul>

        {d.por_unidade.length > 0 && (
          <div>
            <p className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-foreground-muted">
              <Building2 className="h-3.5 w-3.5" aria-hidden="true" />
              De quem vêm as pendências
            </p>
            <ul className="space-y-1.5">
              {d.por_unidade.slice(0, 6).map((u) => (
                <li key={`${u.sigla}-${u.nome}`} className="flex items-center gap-3 text-xs">
                  <span className="min-w-0 flex-1 truncate text-foreground-muted">
                    {u.nome}
                    <span className="text-foreground-subtle">
                      {" "}
                      · {u.qtd_debitos}{" "}
                      {u.qtd_debitos === 1 ? "despesa" : "despesas"}
                    </span>
                  </span>
                  <span className="shrink-0 tabular-nums text-foreground">{fmtBRL(u.valor)}</span>
                  <span className="w-24 shrink-0">
                    <span className="flex h-1.5 w-full overflow-hidden rounded-full bg-surface-2">
                      <span
                        style={{
                          width: `${pct(Number(u.valor), Number(d.total_pendente))}%`,
                          backgroundColor: GRAFICO.principal,
                        }}
                      />
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {d.fontes_insuficientes === 0 && (
          <p className="flex items-center gap-1.5 text-xs text-success-soft-foreground">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            Cada fonte cobre o que aguarda decisão nela.
          </p>
        )}
      </div>
    </GraficoCard>
  );
}

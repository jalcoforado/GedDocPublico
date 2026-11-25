"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Info,
  ShieldAlert,
} from "lucide-react";
import Link from "next/link";

import { NavVisaoFinanceiro } from "@/components/pagamentos/NavVisaoFinanceiro";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import type { AlertaItem } from "@/lib/api";
import { api } from "@/lib/api";

const fmtBRL = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** Severidade → como a linha se apresenta. O vermelho é só do CRÍTICO: se
 *  tudo grita, nada é ouvido. */
const ESTILO = {
  CRITICO: {
    rotulo: "Crítico",
    Icone: AlertOctagon,
    barra: "bg-danger",
    texto: "text-danger-soft-foreground",
    fundo: "bg-danger-soft/40 border-danger/30",
  },
  ALTO: {
    rotulo: "Alto",
    Icone: AlertTriangle,
    barra: "bg-warning",
    texto: "text-warning-soft-foreground",
    fundo: "bg-warning-soft/40 border-warning/30",
  },
  MEDIO: {
    rotulo: "Médio",
    Icone: ShieldAlert,
    barra: "bg-info",
    texto: "text-info-soft-foreground",
    fundo: "bg-info-soft/40 border-info/30",
  },
  INFORMATIVO: {
    rotulo: "Informativo",
    Icone: Info,
    barra: "bg-border-strong",
    texto: "text-foreground-muted",
    fundo: "bg-surface-2 border-border",
  },
} as const;

export default function AlertasPage() {
  const q = useQuery({
    queryKey: ["pag-alertas"],
    queryFn: () => api.pagamentos.alertas(),
  });

  return (
    <div className="space-y-6">
      <PageHeader
        icon={ShieldAlert}
        title="Alertas"
        description="O que precisa de atenção agora, do mais caro para o menos urgente."
      />
      <NavVisaoFinanceiro />

      {q.isLoading && <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />}

      {q.isError && (
        <EmptyState
          icon={ShieldAlert}
          title="Não foi possível carregar os alertas"
          description="Tente de novo em instantes."
        />
      )}

      {q.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              label="Críticos"
              value={q.data.criticos}
              icon={AlertOctagon}
              intent={q.data.criticos > 0 ? "danger" : "default"}
              definicao="Dinheiro que já deveria ter saído, ou obrigação sem saldo que a cubra."
            />
            <KpiCard
              label="Altos"
              value={q.data.altos}
              icon={AlertTriangle}
              intent={q.data.altos > 0 ? "warning" : "default"}
              definicao="O que vence na semana ou trava uma decisão de autorização."
            />
            <KpiCard
              label="Médios"
              value={q.data.medios}
              icon={ShieldAlert}
              definicao="Operacional: cadastro, conciliação, saldo desatualizado."
            />
            <KpiCard
              label="Informativos"
              value={q.data.informativos}
              icon={Info}
              definicao="Lacuna de cadastro que atrapalha a leitura, mas não quebra nada hoje."
            />
          </div>

          {q.data.itens.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="Nada pedindo atenção"
              description="Nenhuma obrigação vencida, nenhuma conta sem lastro e nenhum cadastro faltando."
            />
          ) : (
            <ul className="space-y-3">
              {q.data.itens.map((a, i) => (
                <LinhaAlerta key={`${a.codigo}-${i}`} a={a} />
              ))}
            </ul>
          )}

          <p className="text-xs text-foreground-subtle">
            Todo alerta aqui é um fato conferível no sistema — uma parcela vencida, um saldo que
            não cobre, uma coluna vazia. Leituras estatísticas, como concentração de gastos num
            fornecedor, ficam nos painéis de análise e não são tratadas como indício de
            irregularidade.
          </p>
        </>
      )}
    </div>
  );
}

function LinhaAlerta({ a }: { a: AlertaItem }) {
  const e = ESTILO[a.severidade];
  const Icone = e.Icone;
  return (
    <li className={`overflow-hidden rounded-card border ${e.fundo}`}>
      <div className="flex gap-0">
        <span className={`w-1 shrink-0 ${e.barra}`} aria-hidden="true" />
        <div className="min-w-0 flex-1 p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="flex items-center gap-2">
                <Icone className={`h-4 w-4 shrink-0 ${e.texto}`} aria-hidden="true" />
                <span className="font-display text-sm font-semibold text-foreground">
                  {a.titulo}
                </span>
                <span className={`text-[11px] font-medium uppercase tracking-wider ${e.texto}`}>
                  {e.rotulo}
                </span>
              </p>
              {a.escopo && (
                <p className="mt-0.5 truncate text-xs text-foreground-subtle">{a.escopo}</p>
              )}
            </div>
            {a.impacto_valor != null && (
              <span className="shrink-0 text-right">
                <span className="block font-display text-base font-bold tabular-nums text-foreground">
                  {fmtBRL(a.impacto_valor)}
                </span>
                <span className="block text-[11px] text-foreground-subtle">impacto</span>
              </span>
            )}
          </div>

          <p className="mt-2 text-sm leading-relaxed text-foreground-muted">{a.descricao}</p>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-foreground-muted">
              <span className="font-medium text-foreground">O que fazer:</span> {a.acao}
            </p>
            {a.href && (
              <Link
                href={a.href}
                className="inline-flex shrink-0 items-center gap-1 rounded-badge text-xs font-medium text-brand hover:underline"
              >
                Ver detalhe
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            )}
          </div>

          {/* A origem fica discreta, mas fica: quem desconfia do número precisa
              saber onde conferir sem perguntar para alguém. */}
          <p className="mt-2 border-t border-border/60 pt-2 text-[11px] text-foreground-subtle">
            Origem: {a.origem}
          </p>
        </div>
      </div>
    </li>
  );
}

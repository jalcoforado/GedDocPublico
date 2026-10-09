"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, FileSignature, FileText, Scale } from "lucide-react";
import Link from "next/link";

import {
  ROTA_CONTRATOS,
  VencimentoBadge,
  fmtPercentual,
  isoEmDias,
} from "@/components/contratos/comum";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api } from "@/lib/api";

/** Horizonte da lista "vencem primeiro": o mesmo da maior faixa do painel. */
const HORIZONTE_DIAS = 120;

export default function ContratosPainelPage() {
  const painelQ = useQuery({ queryKey: ["contratos-painel"], queryFn: api.contratos.painel });
  const vencendoQ = useQuery({
    queryKey: ["contratos-vencendo", HORIZONTE_DIAS],
    queryFn: () =>
      api.contratos.list({ vence_ate: isoEmDias(HORIZONTE_DIAS), page: 1, page_size: 10 }),
  });

  const p = painelQ.data;
  const vencendo = vencendoQ.data?.items ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Contratos e Convênios"
        description="Vigências, aditivos e limites legais dos contratos do município."
        icon={FileSignature}
      />

      {painelQ.isError && (
        <Alert intent="danger" title="Não foi possível carregar o painel">
          {(painelQ.error as Error).message}
        </Alert>
      )}

      {p && p.vencidos > 0 && (
        <Alert intent="danger" title={`${p.vencidos} contrato(s) com a vigência vencida`}>
          Contrato vigente com data final no passado é execução sem cobertura contratual.
          Prorrogue por aditivo, encerre ou rescinda.
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <KpiCard
          label="Contratos vigentes"
          value={p ? p.vigentes : "—"}
          hint={p ? fmtMoeda(p.valor_vigente_total) : undefined}
          icon={FileText}
        />
        <KpiCard
          label="Vencem em 30 dias"
          value={p ? p.vencendo_30 : "—"}
          hint={p ? `${p.vencendo_60} em 60 · ${p.vencendo_90} em 90 · ${p.vencendo_120} em 120` : undefined}
          icon={CalendarClock}
          intent={p && p.vencendo_30 > 0 ? "danger" : "default"}
        />
        <KpiCard
          label="Vencidos"
          value={p ? p.vencidos : "—"}
          hint="Vigentes com data final no passado"
          icon={AlertTriangle}
          intent={p && p.vencidos > 0 ? "danger" : "success"}
        />
        <KpiCard
          label="Acima do limite legal"
          value={p ? p.acima_do_limite : "—"}
          hint="Art. 125 da Lei 14.133 — 25% (50% em reforma)"
          icon={Scale}
          intent={p && p.acima_do_limite > 0 ? "warning" : "default"}
        />
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold text-foreground">
            Vencem nos próximos {HORIZONTE_DIAS} dias
          </h2>
          <Link href={ROTA_CONTRATOS} className="text-sm text-primary hover:underline">
            Ver todos os contratos →
          </Link>
        </div>

        {vencendoQ.isLoading ? (
          <div className="py-8 text-center text-muted-foreground">Carregando...</div>
        ) : vencendo.length === 0 ? (
          <EmptyState
            icon={CalendarClock}
            title="Nenhum contrato vencendo"
            description={`Nenhum contrato vigente vence nos próximos ${HORIZONTE_DIAS} dias.`}
          />
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Número</TH>
                <TH>Contratado</TH>
                <TH>Unidade</TH>
                <TH>Vigência até</TH>
                <TH className="text-right">Valor atualizado</TH>
                <TH className="text-right">Aditivado</TH>
              </TR>
            </THead>
            <TBody>
              {vencendo.map((c) => (
                <TR key={c.id}>
                  <TD className="font-mono font-medium">
                    <Link
                      href={`/m/contratos/contratos/${c.id}`}
                      className="text-primary hover:underline"
                    >
                      {c.numero}
                    </Link>
                  </TD>
                  <TD>{c.fornecedor_nome ?? "—"}</TD>
                  <TD className="text-sm text-muted-foreground">{c.unidade_nome ?? "—"}</TD>
                  <TD>
                    <div className="flex flex-wrap items-center gap-2">
                      <span>{fmtData(c.vigencia_fim_atual)}</span>
                      <VencimentoBadge dias={c.dias_para_vencer} />
                    </div>
                  </TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(c.valor_atualizado)}</TD>
                  <TD className="text-right tabular-nums">
                    {fmtPercentual(c.percentual_acrescimo)}
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
        {(vencendoQ.data?.total ?? 0) > vencendo.length && (
          <p className="text-xs text-muted-foreground">
            Mostrando {vencendo.length} de {vencendoQ.data?.total}. A lista completa está em
            Contratos.
          </p>
        )}
      </section>
    </div>
  );
}

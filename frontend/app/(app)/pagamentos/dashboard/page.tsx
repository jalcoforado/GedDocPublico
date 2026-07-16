"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  AlertTriangle,
  BadgeDollarSign,
  BarChart3,
  Clock,
  Landmark,
  Lock,
  ShieldAlert,
  Wallet,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type ComposicaoItem, type StatusDebito } from "@/lib/api";
import { cn } from "@/lib/utils";

// Dataviz: entradas/saídas seguem o mesmo semântico usado no caixa
// (verde/vermelho); a hue única das barras horizontais é o azul
// institucional (#2563eb) — validado via validate_palette.js (ver report).
const COR_ENTRADAS = "#16a34a";
const COR_SAIDAS = "#dc2626";
const COR_BRAND = "#2563eb";

const PERIODOS = [
  { value: 6, label: "6 meses" },
  { value: 12, label: "12 meses" },
  { value: 24, label: "24 meses" },
];

const STATUS_BADGE: Record<
  StatusDebito,
  { intent: "neutral" | "warning" | "info" | "success" | "danger"; label: string }
> = {
  RASCUNHO: { intent: "neutral", label: "Rascunho" },
  AGUARDANDO_APROVACAO: { intent: "warning", label: "Aguardando aprovação" },
  APROVADO: { intent: "info", label: "Aprovado" },
  AUTORIZADO: { intent: "info", label: "Autorizado" },
  PAGO_PARCIAL: { intent: "warning", label: "Pago parcial" },
  PAGO: { intent: "success", label: "Pago" },
  REJEITADO: { intent: "danger", label: "Rejeitado" },
  CANCELADO: { intent: "danger", label: "Cancelado" },
};

function fmtBRL(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/** BRL compacto pros labels diretos das barras ("R$ 1,2 mi", "R$ 850 mil"). */
function fmtBRLCompacto(v: unknown): string {
  const n = typeof v === "string" ? Number(v) : typeof v === "number" ? v : NaN;
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  });
}

function truncaNome(nome: string, max = 18): string {
  return nome.length > max ? `${nome.slice(0, max)}…` : nome;
}

function fmtMesLabel(mes: string): string {
  // mes = 'YYYY-MM'
  const [ano, m] = mes.split("-");
  const d = new Date(Number(ano), Number(m) - 1, 1);
  const s = d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" });
  return s.replace(".", "");
}

function fmtData(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString("pt-BR");
}

function topSeisOutras(itens: ComposicaoItem[]): ComposicaoItem[] {
  // Backend já dobra em top 6 + "Outras"; mantemos ordenação por valor desc
  // para leitura das barras horizontais de cima pra baixo.
  return [...itens].sort((a, b) => Number(b.valor) - Number(a.valor));
}

function TooltipBRL({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="rounded-md border border-border bg-surface-1 px-3 py-2 text-xs shadow-md">
      {label && <p className="mb-1 font-semibold text-foreground">{label}</p>}
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2 text-foreground-muted">
          <span
            className="h-2 w-2 rounded-full"
            style={{ backgroundColor: p.color }}
            aria-hidden="true"
          />
          {p.name}: <span className="tabular-nums text-foreground">{fmtBRL(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

function ComposicaoChart({ titulo, itens }: { titulo: string; itens: ComposicaoItem[] }) {
  const dados = topSeisOutras(itens).map((it) => ({
    nome: it.descricao,
    valor: Number(it.valor),
  }));
  const alturaLinha = 32;
  const altura = Math.max(180, dados.length * alturaLinha + 40);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{titulo}</CardTitle>
      </CardHeader>
      <CardContent>
        {dados.length === 0 ? (
          <EmptyState
            icon={BarChart3}
            title="Sem dados no período"
            description="Nenhum débito lançado nesta categoria."
          />
        ) : (
          <div style={{ height: altura }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={dados}
                layout="vertical"
                margin={{ top: 5, right: 72, left: 8, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="nome"
                  type="category"
                  width={140}
                  tick={{ fontSize: 11 }}
                  tickFormatter={(nome: string) => truncaNome(nome)}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<TooltipBRL />} cursor={{ fill: "hsl(var(--muted))" }} />
                <Bar dataKey="valor" fill={COR_BRAND} radius={[0, 4, 4, 0]} barSize={16}>
                  {/* Rótulo direto (BRL compacto) — texto em token de texto, não na cor da série. */}
                  <LabelList
                    dataKey="valor"
                    position="right"
                    formatter={fmtBRLCompacto}
                    style={{ fill: "hsl(var(--foreground))", fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {dados.length > 0 && (
          <ul className="mt-2 space-y-1">
            {dados.map((d) => (
              <li
                key={d.nome}
                className="flex items-center justify-between text-xs text-foreground-muted"
              >
                <span className="truncate">{d.nome}</span>
                <span className="tabular-nums text-foreground">{fmtBRL(d.valor)}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default function PagamentosDashboardPage() {
  const [meses, setMeses] = useState(12);
  const toast = useToast();
  const router = useRouter();

  const q = useQuery({
    queryKey: ["pag-dashboard", meses],
    queryFn: () => api.pagamentos.dashboard(meses),
  });

  useEffect(() => {
    if (q.isError) {
      toast.error((q.error as Error)?.message ?? "Erro ao carregar dashboard financeiro.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.isError]);

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-20 animate-pulse rounded-xl bg-surface-2/40" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-surface-2/40" />
          ))}
        </div>
        <div className="h-72 animate-pulse rounded-lg bg-surface-2/40" />
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="h-64 animate-pulse rounded-lg bg-surface-2/40" />
          <div className="h-64 animate-pulse rounded-lg bg-surface-2/40" />
        </div>
      </div>
    );
  }

  if (!q.data) {
    return (
      <div className="rounded-lg border border-danger/40 bg-danger-soft p-4 text-sm text-danger-soft-foreground">
        Não foi possível carregar o dashboard financeiro.
      </div>
    );
  }

  const d = q.data;
  const { kpis, fluxo_mensal, por_natureza, por_fonte, maiores_debitos, alertas } = d;

  const fluxo = fluxo_mensal.map((f) => ({
    mes: fmtMesLabel(f.mes),
    entradas: Number(f.entradas),
    saidas: Number(f.saidas),
  }));

  const temAlertas =
    alertas.parcelas_vencidas.length > 0 ||
    alertas.parcelas_7dias.length > 0 ||
    alertas.contas_abaixo_minimo.length > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={BarChart3}
        title="Dashboard financeiro"
        description="Visão consolidada de caixa, despesas e alertas do módulo de pagamentos."
        actions={
          <Select
            value={meses}
            onChange={(e) => setMeses(Number(e.target.value))}
            aria-label="Período do fluxo mensal"
            className="w-auto"
          >
            {PERIODOS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </Select>
        }
      />

      {/* Linha 1 — KPIs */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Saldo total" value={fmtBRL(kpis.saldo_total)} icon={Wallet} />
        <KpiCard
          label="Disponível"
          value={fmtBRL(kpis.disponivel_total)}
          icon={BadgeDollarSign}
          intent="success"
        />
        <KpiCard
          label="Comprometido"
          value={fmtBRL(kpis.comprometido_total)}
          icon={Lock}
          intent="warning"
        />
        <KpiCard
          label="A vencer 30 dias"
          value={fmtBRL(kpis.a_pagar_30d)}
          hint="parcelas em aberto, prospectivo"
          icon={Clock}
        />
        <KpiCard
          label="Vencidas"
          value={fmtBRL(kpis.vencidas_valor)}
          hint={`${kpis.vencidas_qtd} parcela(s)`}
          icon={AlertCircle}
          intent={kpis.vencidas_qtd > 0 ? "danger" : "default"}
        />
        <KpiCard label="Pago no mês" value={fmtBRL(kpis.pago_no_mes)} icon={Landmark} intent="success" />
        <Link href="/pagamentos" className="block">
          <KpiCard
            label="Aguardando aprovação"
            value={kpis.aguardando_aprovacao_qtd}
            icon={AlertTriangle}
            intent={kpis.aguardando_aprovacao_qtd > 0 ? "warning" : "default"}
            hint="ver fila →"
          />
        </Link>
        <Link href="/pagamentos" className="block">
          <KpiCard
            label="Aguardando autorização"
            value={kpis.aguardando_autorizacao_qtd}
            icon={ShieldAlert}
            intent={kpis.aguardando_autorizacao_qtd > 0 ? "warning" : "default"}
            hint="ver fila →"
          />
        </Link>
      </div>

      {/* Linha 2 — fluxo de caixa mensal */}
      <Card>
        <CardHeader>
          <CardTitle>Fluxo de caixa mensal</CardTitle>
        </CardHeader>
        <CardContent>
          {fluxo.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="Sem movimentações no período"
              description="Tente um período maior."
            />
          ) : (
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={fluxo} margin={{ top: 10, right: 20, left: 0, bottom: 0 }} barGap={4}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="mes" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v: number) => fmtBRL(v)} width={90} />
                  <Tooltip content={<TooltipBRL />} cursor={{ fill: "hsl(var(--muted))" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="entradas" name="Entradas" fill={COR_ENTRADAS} radius={[4, 4, 0, 0]} barSize={14} />
                  <Bar dataKey="saidas" name="Saídas" fill={COR_SAIDAS} radius={[4, 4, 0, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Linha 3 — composição por natureza e fonte */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ComposicaoChart titulo="Despesa por natureza (top 6)" itens={por_natureza} />
        <ComposicaoChart titulo="Despesa por fonte de recursos (top 6)" itens={por_fonte} />
      </div>

      {/* Linha 4 — maiores débitos + alertas */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Maiores débitos em aberto</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {maiores_debitos.length === 0 ? (
              <div className="p-4">
                <EmptyState
                  icon={Landmark}
                  title="Sem débitos em aberto"
                  description="Nenhum débito pendente no momento."
                />
              </div>
            ) : (
              <Table variant="flat">
                <THead>
                  <TR>
                    <TH>Fornecedor</TH>
                    <TH>Descrição</TH>
                    <TH className="text-right">Valor</TH>
                    <TH>Status</TH>
                  </TR>
                </THead>
                <TBody>
                  {maiores_debitos.map((deb) => {
                    const badge = STATUS_BADGE[deb.status];
                    return (
                      <TR
                        key={deb.id}
                        onClickRow={() => router.push(`/pagamentos/contas-a-pagar/${deb.id}`)}
                        className="cursor-pointer"
                      >
                        <TD>
                          <Link
                            href={`/pagamentos/contas-a-pagar/${deb.id}`}
                            className="text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {deb.nome_fornecedor}
                          </Link>
                        </TD>
                        <TD className="truncate">{deb.descricao}</TD>
                        <TD className="text-right tabular-nums">{fmtBRL(deb.valor_total)}</TD>
                        <TD>
                          <Badge intent={badge.intent}>{badge.label}</Badge>
                        </TD>
                      </TR>
                    );
                  })}
                </TBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Alertas</CardTitle>
          </CardHeader>
          <CardContent>
            {!temAlertas ? (
              <EmptyState
                icon={ShieldAlert}
                title="Nenhum alerta"
                description="Nenhuma parcela vencida, vencendo ou conta abaixo do mínimo."
              />
            ) : (
              <ul className="space-y-2 text-sm">
                {alertas.parcelas_vencidas.map((p) => (
                  <li
                    key={`venc-${p.id}`}
                    className="flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-danger-soft-foreground"
                  >
                    <AlertCircle className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
                    <span className="flex-1">
                      <Link
                        href={`/pagamentos/contas-a-pagar/${p.id_debito}`}
                        className="font-medium hover:underline"
                      >
                        {p.nome_fornecedor}
                      </Link>{" "}
                      — parcela vencida há {p.dias_atraso} dia(s), venc. {fmtData(p.vencimento)}
                    </span>
                    <span className="shrink-0 tabular-nums font-semibold">{fmtBRL(p.valor)}</span>
                  </li>
                ))}
                {alertas.parcelas_7dias.map((p) => (
                  <li
                    key={`7d-${p.id}`}
                    className="flex items-start gap-2 rounded-md bg-warning-soft px-3 py-2 text-warning-soft-foreground"
                  >
                    <Clock className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
                    <span className="flex-1">
                      <Link
                        href={`/pagamentos/contas-a-pagar/${p.id_debito}`}
                        className="font-medium hover:underline"
                      >
                        {p.nome_fornecedor}
                      </Link>{" "}
                      — vence em até 7 dias, {fmtData(p.vencimento)}
                    </span>
                    <span className="shrink-0 tabular-nums font-semibold">{fmtBRL(p.valor)}</span>
                  </li>
                ))}
                {alertas.contas_abaixo_minimo.map((c) => (
                  <li
                    key={`min-${c.id_conta}`}
                    className="flex items-start gap-2 rounded-md bg-danger-soft px-3 py-2 text-danger-soft-foreground"
                  >
                    <ShieldAlert className="mt-0.5 h-4 w-4 flex-none" aria-hidden="true" />
                    <span className="flex-1">
                      Conta <span className="font-medium">{c.nome}</span> abaixo do saldo mínimo de
                      alerta ({fmtBRL(c.saldo_minimo_alerta)})
                    </span>
                    <span className="shrink-0 tabular-nums font-semibold">{fmtBRL(c.saldo_atual)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

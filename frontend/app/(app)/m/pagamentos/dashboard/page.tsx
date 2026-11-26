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
  ShieldCheck,
  Wallet,
  Filter,
  X,
} from "lucide-react";
import Link from "next/link";
import { type ComponentType, useState } from "react";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import {
  api,
  type ComposicaoItem,
  type DimensaoDespesa,
  type FiltrosDespesa,
} from "@/lib/api";
import { DisponibilidadeContas } from "@/components/pagamentos/DisponibilidadeContas";
import { GraficoCard } from "@/components/ui/grafico-card";
import { NavVisaoFinanceiro } from "@/components/pagamentos/NavVisaoFinanceiro";
import { PAGAMENTO_ROTULO, TRAMITACAO_ROTULO } from "@/components/pagamentos/situacoes";
import { EIXO, GRAFICO } from "@/lib/chart-theme";
import { cn } from "@/lib/utils";

// Dataviz: cores vêm de `lib/chart-theme` (tokens; trocam no tema escuro).
// Entradas/saídas seguem o semântico do caixa (positivo/negativo).
const COR_ENTRADAS = GRAFICO.positivo;
const COR_SAIDAS = GRAFICO.negativo;
const COR_BRAND = GRAFICO.principal;

const PERIODOS = [
  { value: 6, label: "6 meses" },
  { value: 12, label: "12 meses" },
  { value: 24, label: "24 meses" },
];

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

function fmtDataHora(iso: string): string {
  // O backend manda naive UTC (datetime.utcnow); o "Z" evita que o navegador
  // leia como hora local e mostre um horário que nunca existiu.
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
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

/** Concentração do topo: "X responde por Y% do período". Só diz algo quando
 *  há mais de um item — com um só, a frase seria "100%", que não informa. */
function concentracao(itens: ComposicaoItem[]): string | null {
  if (itens.length < 2) return null;
  const total = itens.reduce((acc, i) => acc + Number(i.valor), 0);
  if (total <= 0) return null;
  const maior = [...itens].sort((a, b) => Number(b.valor) - Number(a.valor))[0];
  const pct = (Number(maior.valor) / total) * 100;
  return `${maior.descricao} responde por ${pct.toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
  })}% do pago no período.`;
}

/** Quanto do pago no período não passou por contrato. É a leitura que mais
 *  costuma surpreender quem abre o painel — e some de qualquer ranking que
 *  liste só contratos de verdade. */
function semContrato(itens: ComposicaoItem[]): string | null {
  const total = itens.reduce((acc, i) => acc + Number(i.valor), 0);
  const avulsa = itens.find((i) => i.codigo === "Sem contrato");
  if (!avulsa || total <= 0) return null;
  const pct = (Number(avulsa.valor) / total) * 100;
  return `${pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% do pago no período não está vinculado a contrato.`;
}

function ComposicaoChart({
  titulo,
  itens,
  subtitulo,
  insight,
  dimensao,
  onFiltrar,
}: {
  titulo: string;
  itens: ComposicaoItem[];
  subtitulo?: string;
  insight?: React.ReactNode;
  /** Quando informada, as barras com `id` viram filtro ao clique. */
  dimensao?: DimensaoDespesa;
  onFiltrar?: (dimensao: DimensaoDespesa, id: number, rotulo: string) => void;
}) {
  const dados = topSeisOutras(itens).map((it) => ({
    nome: it.descricao,
    valor: Number(it.valor),
    id: it.id ?? null,
  }));
  const clicavel = Boolean(dimensao && onFiltrar);
  const aoClicar = (payload: { id: number | null; nome: string }) => {
    // A linha agregada não tem id: clicar nela seria aplicar vários recortes
    // ao mesmo tempo, o que não é um recorte.
    if (!clicavel || payload.id == null) return;
    onFiltrar!(dimensao!, payload.id, payload.nome);
  };
  const alturaLinha = 32;
  const altura = Math.max(180, dados.length * alturaLinha + 40);

  return (
    <GraficoCard
      titulo={titulo}
      subtitulo={subtitulo}
      insight={insight ?? concentracao(itens)}
      vazio={dados.length === 0}
      vazioDescricao="Nenhum pagamento lançado nesta categoria."
    >
      <>
          <div style={{ height: altura }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={dados}
                layout="vertical"
                margin={{ top: 5, right: 72, left: 8, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRAFICO.grade} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="nome"
                  type="category"
                  width={140}
                  tick={EIXO.tick}
                  tickFormatter={(nome: string) => truncaNome(nome)}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<TooltipBRL />} cursor={{ fill: GRAFICO.cursor }} />
                <Bar
                  dataKey="valor"
                  fill={COR_BRAND}
                  radius={[0, 4, 4, 0]}
                  barSize={16}
                  cursor={clicavel ? "pointer" : undefined}
                  onClick={(p: unknown) => aoClicar(p as { id: number | null; nome: string })}
                >
                  {/* Rótulo direto (BRL compacto) — texto em token de texto, não na cor da série. */}
                  <LabelList
                    dataKey="valor"
                    position="right"
                    formatter={fmtBRLCompacto}
                    style={{ fill: GRAFICO.texto, fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {dados.length > 0 && (
            <ul className="mt-2 space-y-1">
              {dados.map((d) => (
                <li key={d.nome} className="text-xs text-foreground-muted">
                  {clicavel && d.id != null ? (
                    <button
                      type="button"
                      onClick={() => aoClicar(d)}
                      className="flex w-full items-center justify-between gap-2 rounded px-1 py-0.5 text-left transition-colors duration-fast hover:bg-surface-2"
                      aria-label={`Filtrar por ${d.nome}`}
                    >
                      <span className="truncate">{d.nome}</span>
                      <span className="tabular-nums text-foreground">{fmtBRL(d.valor)}</span>
                    </button>
                  ) : (
                    <span className="flex items-center justify-between gap-2 px-1 py-0.5">
                      <span className="truncate">{d.nome}</span>
                      <span className="tabular-nums text-foreground">{fmtBRL(d.valor)}</span>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
      </>
    </GraficoCard>
  );
}

/** Rótulo do recorte ativo, para a pessoa saber o que está vendo. */
type RotuloFiltro = { dimensao: DimensaoDespesa; id: number; rotulo: string };

const NOME_DIMENSAO: Record<DimensaoDespesa, string> = {
  unidade: "Secretaria",
  fornecedor: "Fornecedor",
  contrato: "Contrato",
  natureza: "Natureza",
  fonte: "Fonte",
};

export default function PagamentosDashboardPage() {
  const [meses, setMeses] = useState(12);
  const [filtros, setFiltros] = useState<RotuloFiltro[]>([]);

  const filtrosQuery: FiltrosDespesa = Object.fromEntries(
    filtros.map((f) => [f.dimensao, f.id]),
  );

  const q = useQuery({
    queryKey: ["pag-dashboard", meses, filtrosQuery],
    queryFn: () => api.pagamentos.dashboard(meses, filtrosQuery),
    // Mantém o painel anterior enquanto o recorte recarrega: a tela piscar
    // inteira a cada clique faz perder o contexto do que se estava olhando.
    placeholderData: (anterior) => anterior,
  });

  /** Um recorte por dimensão: clicar noutra secretaria TROCA a secretaria,
   *  em vez de empilhar duas — duas secretarias ao mesmo tempo seria um
   *  "ou" que o backend não faz e que o leitor não esperaria. */
  const aplicarFiltro = (dimensao: DimensaoDespesa, id: number, rotulo: string) => {
    setFiltros((cur) => [...cur.filter((f) => f.dimensao !== dimensao), { dimensao, id, rotulo }]);
  };
  const removerFiltro = (dimensao: DimensaoDespesa) =>
    setFiltros((cur) => cur.filter((f) => f.dimensao !== dimensao));

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

  if (q.isError || !q.data) {
    // Erro persistente (não toast): fica na tela até o retry dar certo.
    // Mesmo padrão do launcher de módulos — mensagem clara + "Tentar novamente".
    return (
      <EmptyState
        icon={AlertCircle}
        title="Não foi possível carregar o dashboard financeiro"
        description={
          (q.error as Error | null)?.message ??
          "Verifique sua conexão e tente novamente."
        }
        action={
          <Button
            variant="secondary"
            onClick={() => q.refetch()}
            disabled={q.isRefetching}
          >
            {q.isRefetching ? "Carregando…" : "Tentar novamente"}
          </Button>
        }
      />
    );
  }

  const d = q.data;
  const {
    kpis, fluxo_mensal, por_natureza, por_fonte, maiores_debitos, alertas,
  } = d;
  // Campos do painel executivo: a resposta pode não trazê-los (backend antigo
  // ou período sem pagamento), e lista vazia é o estado correto nos dois casos.
  const por_secretaria = d.por_secretaria ?? [];
  const top_fornecedores = d.top_fornecedores ?? [];
  const top_contratos = d.top_contratos ?? [];
  const disponibilidade_contas = d.disponibilidade_contas ?? [];

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
        title="Indicadores financeiros"
        description={
          d.apurado_em
            ? `Visão consolidada de caixa, despesas e alertas. Apurado em ${fmtDataHora(d.apurado_em)}${d.periodo_inicio ? ` · gráficos desde ${fmtData(d.periodo_inicio)}` : ""}.`
            : "Visão consolidada de caixa, despesas e alertas do módulo de Despesa."
        }
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
      <NavVisaoFinanceiro />

      {filtros.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-card border border-brand/30 bg-brand/5 px-3 py-2">
          <Filter className="h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
          <span className="text-xs font-medium text-foreground">Recorte ativo:</span>
          {filtros.map((f) => (
            <button
              key={f.dimensao}
              type="button"
              onClick={() => removerFiltro(f.dimensao)}
              className="inline-flex items-center gap-1 rounded-badge bg-surface-1 px-2 py-0.5 text-xs text-foreground shadow-card transition-colors duration-fast hover:bg-surface-2"
              aria-label={`Remover filtro ${NOME_DIMENSAO[f.dimensao]}: ${f.rotulo}`}
            >
              <span className="text-foreground-subtle">{NOME_DIMENSAO[f.dimensao]}:</span>
              <span className="max-w-[14rem] truncate font-medium">{f.rotulo}</span>
              <X className="h-3 w-3" aria-hidden="true" />
            </button>
          ))}
          <Button variant="ghost" size="sm" onClick={() => setFiltros([])}>
            Ver tudo
          </Button>
          {d.total_filtrado != null && (
            <span className="ml-auto text-xs text-foreground-muted">
              Pago no recorte:{" "}
              <strong className="font-semibold tabular-nums text-foreground">
                {fmtBRL(d.total_filtrado)}
              </strong>
            </span>
          )}
        </div>
      )}

      {/* Linha 1 — KPIs. NÃO são recortados: saldo é da conta bancária, não da
          secretaria. Dizer isso é obrigatório — um filtro que silenciosamente
          não se aplica a alguns números é pior que não ter filtro. */}
      {filtros.length > 0 && (
        <p className="-mb-3 text-xs text-foreground-subtle">
          Os indicadores de saldo abaixo seguem consolidados: saldo, disponível e comprometido são
          da conta bancária e não se recortam por secretaria, fornecedor ou contrato. O recorte
          vale para os gráficos de despesa paga.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Saldo total"
          value={fmtBRL(kpis.saldo_total)}
          icon={Wallet}
          definicao="Soma do saldo bancário de todas as contas ativas. Origem: saldo inicial da conta mais as movimentações lançadas (pagamentos.movimentacao_conta)."
        />
        <KpiCard
          label="Disponível"
          value={fmtBRL(kpis.disponivel_total)}
          icon={BadgeDollarSign}
          intent="success"
          definicao="Saldo bancário menos o comprometido e menos os bloqueios administrativos vigentes hoje. É o que sobra para novas despesas, respeitando a vinculação de cada fonte."
        />
        <KpiCard
          label="Comprometido"
          value={fmtBRL(kpis.comprometido_total)}
          icon={Lock}
          intent="warning"
          definicao="Parcelas ainda em aberto de despesas já autorizadas, reservadas na conta pagadora. Não soma autorizado com empenhado nem com liquidado: conta o saldo que falta pagar de cada parcela, uma vez só."
        />
        <KpiCard
          label="A vencer 30 dias"
          value={fmtBRL(kpis.a_pagar_30d)}
          hint="parcelas em aberto, prospectivo"
          icon={Clock}
          definicao="Parcelas em aberto de despesas autorizadas que vencem de hoje até 30 dias. Não inclui as já vencidas, que têm indicador próprio."
        />
        <KpiCard
          label="Vencidas"
          value={fmtBRL(kpis.vencidas_valor)}
          hint={kpis.vencidas_qtd === 1 ? "1 parcela" : `${kpis.vencidas_qtd} parcelas`}
          icon={AlertCircle}
          intent={kpis.vencidas_qtd > 0 ? "danger" : "default"}
          definicao="Parcelas de despesas autorizadas cuja data de vencimento já passou e que continuam em aberto."
        />
        <KpiCard
          label="Pago no mês"
          value={fmtBRL(kpis.pago_no_mes)}
          icon={Landmark}
          intent="success"
          definicao="Saídas de conta com origem PAGAMENTO no mês corrente. É a mesma medida usada nos gráficos de despesa por secretaria, natureza, fonte, fornecedor e contrato."
        />
        {/* rounded-card faz o outline do :focus-visible global acompanhar o raio do card */}
        <Link
          href="/m/pagamentos"
          className="block rounded-card"
          aria-label={`Aguardando aprovação: ${kpis.aguardando_aprovacao_qtd} — abrir fila de pagamentos`}
        >
          <KpiCard
            label="Aguardando aprovação"
            value={kpis.aguardando_aprovacao_qtd}
            icon={AlertTriangle}
            intent={kpis.aguardando_aprovacao_qtd > 0 ? "warning" : "default"}
            hint="ver fila →"
          />
        </Link>
        <Link
          href="/m/pagamentos"
          className="block rounded-card"
          aria-label={`Aguardando autorização: ${kpis.aguardando_autorizacao_qtd} — abrir fila de pagamentos`}
        >
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
                  <CartesianGrid strokeDasharray="3 3" stroke={GRAFICO.grade} vertical={false} />
                  <XAxis dataKey="mes" {...EIXO} />
                  {/* Eixo em BRL compacto: o valor cheio ("R$ 1.400.000,00") não cabia
                      na largura do eixo e saía cortado. O exato fica no tooltip. */}
                  <YAxis {...EIXO} tickFormatter={fmtBRLCompacto} width={72} />
                  <Tooltip content={<TooltipBRL />} cursor={{ fill: GRAFICO.cursor }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="entradas" name="Entradas" fill={COR_ENTRADAS} radius={[4, 4, 0, 0]} barSize={14} />
                  <Bar dataKey="saidas" name="Saídas" fill={COR_SAIDAS} radius={[4, 4, 0, 0]} barSize={14} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Onde o dinheiro ESTÁ, antes de onde ele foi: a pergunta nº 1 do
          gestor ("quanto temos e quanto é nosso para usar") vem antes da
          nº 10 ("quem gastou mais"). */}
      <DisponibilidadeContas itens={disponibilidade_contas} />

      {/* Linha 3 — onde o dinheiro foi gasto: a secretaria primeiro, porque é
          a pergunta que o gestor faz antes de qualquer outra ("quem está
          gastando mais?"). Ocupa a largura inteira: dividir com outro gráfico
          truncava nomes de secretaria, que são longos por natureza. */}
      <ComposicaoChart
        titulo="Despesa por secretaria"
        subtitulo="Pago no período · clique numa barra para recortar o painel"
        itens={por_secretaria}
        dimensao="unidade"
        onFiltrar={aplicarFiltro}
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <ComposicaoChart
          titulo="Despesa por natureza"
          subtitulo="Top 6 no período · clique para recortar"
          itens={por_natureza}
          dimensao="natureza"
          onFiltrar={aplicarFiltro}
        />
        <ComposicaoChart
          titulo="Despesa por fonte de recursos"
          subtitulo="Top 6 no período · clique para recortar"
          itens={por_fonte}
          dimensao="fonte"
          onFiltrar={aplicarFiltro}
        />
      </div>

      {/* Linha 4 — com quem e por qual contrato. "Sem contrato" aparece no
          ranking de contratos de propósito: é despesa real, e escondê-la faria
          as barras somarem menos que o total pago sem explicar por quê. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ComposicaoChart
          titulo="Maiores fornecedores"
          subtitulo="Top 10 por valor pago · clique para recortar"
          itens={top_fornecedores}
          dimensao="fornecedor"
          onFiltrar={aplicarFiltro}
        />
        <ComposicaoChart
          titulo="Maiores contratos"
          subtitulo="Top 10 por valor pago; inclui a despesa sem contrato"
          itens={top_contratos}
          insight={semContrato(top_contratos)}
          dimensao="contrato"
          onFiltrar={aplicarFiltro}
        />
      </div>

      {/* Linha 4 — maiores débitos + alertas. A lista leva 2/3 da largura e
          cada débito vira linha de duas alturas (fornecedor, descrição), com
          valor e situação à direita: a tabela de 4 colunas em meia tela
          cortava os nomes e escondia a coluna de situação. `items-start`:
          o cartão de alertas, quase sempre curto, não estica até a altura
          da lista. */}
      <div className="grid items-start gap-6 lg:grid-cols-3">
        <section
          aria-labelledby="maiores-debitos"
          className="overflow-hidden rounded-card border border-border bg-surface-1 shadow-card lg:col-span-2"
        >
          <h2
            id="maiores-debitos"
            className="border-b border-border px-5 py-4 font-display text-base font-semibold text-foreground"
          >
            Maiores débitos em aberto
          </h2>
          {maiores_debitos.length === 0 ? (
            <div className="p-5">
              <EmptyState
                icon={Landmark}
                title="Sem débitos em aberto"
                description="Nenhum débito pendente no momento."
              />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {maiores_debitos.map((deb) => {
                // Antes de autorizado, a dimensão que se move é a
                // tramitação; depois, a tramitação fica presa em
                // AUTORIZADA e quem informa é a execução do pagamento.
                const rotulo = deb.situacao_tramitacao === "AUTORIZADA"
                  ? PAGAMENTO_ROTULO[deb.situacao_pagamento]
                  : TRAMITACAO_ROTULO[deb.situacao_tramitacao];
                return (
                  <li key={deb.id}>
                    <Link
                      href={`/m/pagamentos/solicitacoes/${deb.id}`}
                      className="flex items-center gap-4 px-5 py-3 transition-colors duration-fast hover:bg-surface-2"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium text-foreground" title={deb.nome_fornecedor}>
                          {deb.nome_fornecedor}
                        </span>
                        <span className="block truncate text-xs text-foreground-muted" title={deb.descricao}>
                          {deb.descricao}
                        </span>
                      </span>
                      <span className="flex shrink-0 flex-col items-end gap-1">
                        <span className="text-sm font-semibold tabular-nums text-foreground">
                          {fmtBRL(deb.valor_total)}
                        </span>
                        <Badge intent={rotulo.intent} icon={rotulo.icon}>{rotulo.label}</Badge>
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section
          aria-labelledby="alertas"
          className="overflow-hidden rounded-card border border-border bg-surface-1 shadow-card"
        >
          <h2
            id="alertas"
            className="border-b border-border px-5 py-4 font-display text-base font-semibold text-foreground"
          >
            Alertas
          </h2>
          {!temAlertas ? (
            <div className="flex items-start gap-3 px-5 py-4">
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-success-soft text-success-soft-foreground">
                <ShieldCheck className="h-4 w-4" aria-hidden="true" />
              </span>
              <span>
                <span className="block text-sm font-medium text-foreground">Nenhum alerta</span>
                <span className="block text-xs text-foreground-muted">
                  Nenhuma parcela vencida, vencendo ou conta abaixo do mínimo.
                </span>
              </span>
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {alertas.parcelas_vencidas.map((p) => (
                <Alerta
                  key={`venc-${p.id}`}
                  tom="danger"
                  icone={AlertCircle}
                  href={`/m/pagamentos/solicitacoes/${p.id_debito}`}
                  titulo={p.nome_fornecedor}
                  detalhe={`Parcela vencida há ${p.dias_atraso} ${p.dias_atraso === 1 ? "dia" : "dias"} — ${fmtData(p.vencimento)}`}
                  valor={fmtBRL(p.valor)}
                />
              ))}
              {alertas.parcelas_7dias.map((p) => (
                <Alerta
                  key={`7d-${p.id}`}
                  tom="warning"
                  icone={Clock}
                  href={`/m/pagamentos/solicitacoes/${p.id_debito}`}
                  titulo={p.nome_fornecedor}
                  detalhe={`Vence em até 7 dias — ${fmtData(p.vencimento)}`}
                  valor={fmtBRL(p.valor)}
                />
              ))}
              {alertas.contas_abaixo_minimo.map((c) => (
                <Alerta
                  key={`min-${c.id_conta}`}
                  tom="danger"
                  icone={ShieldAlert}
                  titulo={`Conta ${c.nome}`}
                  detalhe={`Abaixo do saldo mínimo de alerta (${fmtBRL(c.saldo_minimo_alerta)})`}
                  valor={fmtBRL(c.saldo_atual)}
                />
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}

/** Uma linha de alerta: a cor fica no ícone, o texto segue neutro. */
function Alerta({
  tom,
  icone: Icone,
  href,
  titulo,
  detalhe,
  valor,
}: {
  tom: "danger" | "warning";
  icone: ComponentType<{ className?: string }>;
  href?: string;
  titulo: string;
  detalhe: string;
  valor: string;
}) {
  const corpo = (
    <>
      <span
        className={cn(
          "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          tom === "danger" ? "bg-danger-soft text-danger-soft-foreground" : "bg-warning-soft text-warning-soft-foreground",
        )}
      >
        <Icone className="h-4 w-4" aria-hidden="true" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{titulo}</span>
        <span className="block text-xs text-foreground-muted">{detalhe}</span>
      </span>
      <span className="shrink-0 text-sm font-semibold tabular-nums text-foreground">{valor}</span>
    </>
  );
  const classe = "flex items-center gap-3 px-5 py-3";
  return (
    <li>
      {href ? (
        <Link href={href} className={cn(classe, "transition-colors duration-fast hover:bg-surface-2")}>
          {corpo}
        </Link>
      ) : (
        <div className={classe}>{corpo}</div>
      )}
    </li>
  );
}

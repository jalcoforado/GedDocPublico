"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { GraficoCard } from "@/components/ui/grafico-card";
import { api } from "@/lib/api";
import { EIXO, GRAFICO } from "@/lib/chart-theme";

/**
 * Os três gráficos da Visão geral.
 *
 * A tela já contava QUANTAS despesas estão em cada etapa. Estes respondem o
 * que a contagem não responde, e por isso não repetem a aba Indicadores:
 *
 * - **Valor parado por etapa** — cinco despesas de R$ 2 mil e cinco de R$ 2
 *   milhões dão a mesma contagem e pedem urgências opostas.
 * - **Envelhecimento** — dez itens parados há 2 dias é saudável; os mesmos dez
 *   parados há 40 dias é um problema, e os dois aparecem como "10".
 * - **Ritmo semanal** — a fila cresce, encolhe ou está estável? Sem isso não
 *   dá para saber se o acúmulo é pontual ou tendência.
 */

const fmtBRL = (v: number | string) =>
  Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

/** `unknown` e não `number`: o `LabelList` do recharts entrega `RenderableText`
 *  (string | number | undefined), e tipar como number quebra a build. Mesmo
 *  padrão do `fmtBRLCompacto` da tela de Indicadores. */
function fmtCompacto(v: unknown): string {
  const n = typeof v === "string" ? Number(v) : typeof v === "number" ? v : NaN;
  if (Number.isNaN(n)) return "—";
  return n.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
    notation: "compact",
    maximumFractionDigits: 1,
  });
}

/** Faixa de envelhecimento → cor. Quanto mais velho, mais quente: a escala é
 *  a própria mensagem, e cor única faria o gráfico só repetir a tabela. */
const COR_FAIXA = [
  GRAFICO.positivo,
  GRAFICO.principal,
  GRAFICO.secundaria,
  GRAFICO.alerta,
  GRAFICO.negativo,
];

function TooltipValor({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: { rotulo?: string; faixa?: string; qtd: number; valor: number } }[];
}) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-md border border-border bg-surface-1 px-3 py-2 text-xs shadow-md">
      <p className="font-semibold text-foreground">{p.rotulo ?? p.faixa}</p>
      <p className="tabular-nums text-foreground-muted">
        {fmtBRL(p.valor)} · {p.qtd} {p.qtd === 1 ? "despesa" : "despesas"}
      </p>
    </div>
  );
}

export function PanoramaVisaoGeral() {
  const q = useQuery({
    queryKey: ["pag-panorama"],
    queryFn: () => api.pagamentos.panorama(),
  });

  if (q.isLoading) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />
        <div className="h-64 animate-pulse rounded-card bg-surface-2/40" />
      </div>
    );
  }
  if (q.isError || !q.data) return null;
  const d = q.data;

  const etapas = d.etapas.map((e) => ({
    rotulo: e.rotulo,
    qtd: e.qtd,
    valor: Number(e.valor),
  }));
  const totalParado = etapas.reduce((a, e) => a + e.valor, 0);
  const maiorEtapa = [...etapas].sort((a, b) => b.valor - a.valor)[0];

  const idades = d.envelhecimento.map((e) => ({
    faixa: e.faixa,
    qtd: e.qtd,
    valor: Number(e.valor),
  }));
  const velhos = idades
    .slice(2)
    .reduce((a, e) => ({ qtd: a.qtd + e.qtd, valor: a.valor + e.valor }), { qtd: 0, valor: 0 });

  const fluxo = d.fluxo_semanal.map((f) => ({
    rotulo: f.rotulo,
    entraram: f.entraram,
    autorizadas: f.autorizadas,
  }));
  const totalEntraram = fluxo.reduce((a, f) => a + f.entraram, 0);
  const totalAutorizadas = fluxo.reduce((a, f) => a + f.autorizadas, 0);
  const saldoFila = totalEntraram - totalAutorizadas;

  if (d.em_curso_qtd === 0 && totalParado === 0) return null;

  return (
    <div className="space-y-4">
      <GraficoCard
        titulo="Despesas por etapa do processo"
        subtitulo={`${fmtBRL(totalParado)} em ${d.etapas.reduce((a, e) => a + e.qtd, 0)} itens em andamento, do pedido ao pagamento`}
        insight={
          maiorEtapa && maiorEtapa.valor > 0 ? (
            <>
              A maior concentração está em{" "}
              <strong className="font-semibold text-foreground">{maiorEtapa.rotulo}</strong>:{" "}
              {fmtBRL(maiorEtapa.valor)}
              {totalParado > 0
                ? `, ${((maiorEtapa.valor / totalParado) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% do valor em andamento.`
                : "."}
            </>
          ) : null
        }
      >
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={etapas} margin={{ top: 18, right: 12, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={GRAFICO.grade} vertical={false} />
              <XAxis dataKey="rotulo" {...EIXO} interval={0} />
              <YAxis {...EIXO} tickFormatter={fmtCompacto} width={70} />
              <Tooltip content={<TooltipValor />} cursor={{ fill: GRAFICO.cursor }} />
              <Bar dataKey="valor" radius={[6, 6, 0, 0]} barSize={46}>
                {etapas.map((e, i) => (
                  <Cell
                    key={e.rotulo}
                    fill={i >= 3 ? GRAFICO.positivo : GRAFICO.principal}
                    fillOpacity={0.55 + i * 0.1}
                  />
                ))}
                <LabelList
                  dataKey="valor"
                  position="top"
                  formatter={fmtCompacto}
                  style={{ fill: GRAFICO.texto, fontSize: 11, fontWeight: 600 }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-5">
          {etapas.map((e) => (
            <li key={e.rotulo} className="text-xs">
              <span className="block truncate text-foreground-subtle">{e.rotulo}</span>
              <span className="block tabular-nums text-foreground">
                {e.qtd} {e.qtd === 1 ? "item" : "itens"}
              </span>
            </li>
          ))}
        </ul>
      </GraficoCard>

      <div className="grid gap-4 lg:grid-cols-2">
        <GraficoCard
          titulo="Tempo em cada etapa"
          subtitulo="Despesas em tramitação, desde a última movimentação"
          insight={
            velhos.qtd > 0 ? (
              <>
                <strong className="font-semibold text-foreground">
                  {velhos.qtd} {velhos.qtd === 1 ? "despesa aguarda" : "despesas aguardam"}{" "}
                  há mais de 7 dias
                </strong>
                , somando {fmtBRL(velhos.valor)}. A mais antiga espera há {d.mais_antigo_dias}{" "}
                {d.mais_antigo_dias === 1 ? "dia" : "dias"}.
              </>
            ) : (
              <>
                Nenhuma despesa aguarda há mais de 7 dias — o fluxo está em dia. A espera mais
                longa é de{" "}
                {d.mais_antigo_dias} {d.mais_antigo_dias === 1 ? "dia" : "dias"}.
              </>
            )
          }
        >
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={idades}
                layout="vertical"
                margin={{ top: 5, right: 56, left: 8, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={GRAFICO.grade} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="faixa"
                  type="category"
                  width={110}
                  tick={EIXO.tick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<TooltipValor />} cursor={{ fill: GRAFICO.cursor }} />
                <Bar dataKey="qtd" radius={[0, 5, 5, 0]} barSize={20}>
                  {idades.map((e, i) => (
                    <Cell key={e.faixa} fill={COR_FAIXA[i] ?? GRAFICO.principal} />
                  ))}
                  <LabelList
                    dataKey="valor"
                    position="right"
                    formatter={fmtCompacto}
                    style={{ fill: GRAFICO.texto, fontSize: 11 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </GraficoCard>

        <GraficoCard
          titulo="Ritmo das últimas semanas"
          subtitulo="Despesas que entraram contra despesas autorizadas"
          insight={
            saldoFila > 0 ? (
              <>
                Entraram <strong className="font-semibold text-foreground">{saldoFila}</strong>{" "}
                {saldoFila === 1 ? "despesa a mais do que foi autorizada" : "despesas a mais do que foram autorizadas"}{" "}
                no período: a fila está crescendo.
              </>
            ) : saldoFila < 0 ? (
              <>
                Foram autorizadas{" "}
                <strong className="font-semibold text-foreground">{Math.abs(saldoFila)}</strong> a
                mais do que entraram: a fila está encolhendo.
              </>
            ) : (
              <>Entradas e autorizações empataram no período: a fila está estável.</>
            )
          }
        >
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={fluxo} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRAFICO.grade} vertical={false} />
                <XAxis dataKey="rotulo" {...EIXO} />
                <YAxis {...EIXO} allowDecimals={false} width={32} />
                <Tooltip cursor={{ fill: GRAFICO.cursor }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar
                  dataKey="entraram"
                  name="Entraram"
                  fill={GRAFICO.principal}
                  radius={[4, 4, 0, 0]}
                  barSize={18}
                />
                <Line
                  type="monotone"
                  dataKey="autorizadas"
                  name="Autorizadas"
                  stroke={GRAFICO.positivo}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </GraficoCard>
      </div>
    </div>
  );
}

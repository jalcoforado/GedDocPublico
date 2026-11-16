"use client";

/**
 * Panorama do Início — os números da prefeitura em movimento, abaixo das
 * pendências ("o que precisa de você") e acima das notificações.
 *
 * Inspirado no que o IAnalisys faz bem: cartão com o número, a variação
 * contra o período anterior e o desenho da tendência; gráficos que respondem
 * a uma pergunta escrita no título; passar o mouse mostra o detalhe; clicar
 * leva à tela que prova o número. Nada aqui é dado novo — cada bloco reusa a
 * consulta (e o cache) da tela que é dona do número: o dashboard executivo,
 * o dashboard financeiro, a lista de veículos e o relatório de alvarás.
 *
 * Cada bloco só aparece se o módulo está contratado E a pessoa tem a leitura
 * dele (as mesmas regras do menu e dos cartões de pendência).
 */
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Clock, FileInput, Landmark, Wallet } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import {
  Area,
  AreaChart,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  BarraSegmentada,
  CartaoTendencia,
  DicaGrafico,
  ListaDeBarras,
  QuadroGrafico,
  SeletorPeriodo,
  Sparkline,
  fmtBRL,
  fmtBRLCurto,
  fmtNum,
} from "@/components/home/graficos";
import { api, dashboardApi, type DashboardKpis, type PagamentosDashboard } from "@/lib/api";
import { EIXO, GRAFICO, corDaSerie } from "@/lib/chart-theme";
import { cn } from "@/lib/utils";

const PERIODOS = [
  { value: 7, label: "7 dias" },
  { value: 30, label: "30 dias" },
  { value: 90, label: "90 dias" },
];

const COR = {
  sucesso: "hsl(var(--success))",
  alerta: "hsl(var(--warning))",
  perigo: "hsl(var(--danger))",
  info: "hsl(var(--info))",
  neutro: "hsl(var(--grafico-6))",
};

export interface AcessoPanorama {
  /** Protocolo contratado + permissão `dashboard` (a do dashboard executivo). */
  protocolo: boolean;
  pagamentos: boolean;
  frota: boolean;
  transporte: boolean;
}

export function Panorama({ acesso }: { acesso: AcessoPanorama }) {
  const [periodo, setPeriodo] = React.useState(30);

  // Mesma chave do dashboard executivo com os filtros padrão dele: abrir o
  // dashboard depois do Início não refaz a consulta.
  const protQ = useQuery({
    queryKey: ["dashboard-kpis", { periodo, idUnidade: null, idServico: null, incluirLegado: true }],
    queryFn: () => dashboardApi.kpis({ periodo, incluir_legado: true }),
    enabled: acesso.protocolo,
    staleTime: 60_000,
  });
  const pagQ = useQuery({
    queryKey: ["pag-dashboard", 12],
    queryFn: () => api.pagamentos.dashboard(12),
    enabled: acesso.pagamentos,
    staleTime: 60_000,
  });

  if (!acesso.protocolo && !acesso.pagamentos && !acesso.frota && !acesso.transporte) return null;

  return (
    <section aria-labelledby="panorama-titulo" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="panorama-titulo" className="font-display text-base font-semibold text-foreground">
            Panorama da prefeitura
          </h2>
          <p className="text-sm text-foreground-muted">
            Como os números andaram — passe o mouse nos gráficos para ver o detalhe.
          </p>
        </div>
        {acesso.protocolo && (
          <SeletorPeriodo rotulo="Período do panorama" valor={periodo} opcoes={PERIODOS} onChange={setPeriodo} />
        )}
      </div>

      <FaixaDeTendencias acesso={acesso} prot={protQ} pag={pagQ} periodo={periodo} />

      {acesso.protocolo && (
        <div className="grid gap-5 xl:grid-cols-3">
          <EntradaDeProcessos q={protQ} periodo={periodo} className="xl:col-span-2" />
          <PrazosAgora q={protQ} />
        </div>
      )}

      {acesso.pagamentos && (
        <div className="grid gap-5 xl:grid-cols-3">
          <FluxoDeCaixa q={pagQ} className="xl:col-span-2" />
          <QuadroGrafico
            pergunta="Para onde vai o dinheiro?"
            resposta="Despesas por natureza nos últimos 12 meses."
            acao={{ href: "/m/pagamentos/dashboard", label: "Financeiro" }}
          >
            {pagQ.isLoading ? (
              <Esqueleto altura="h-56" />
            ) : pagQ.isError ? (
              <Falhou />
            ) : (
              <ListaDeBarras
                formato={fmtBRLCurto}
                cor={GRAFICO.secundaria}
                vazio="Nenhuma despesa no período."
                itens={(pagQ.data?.por_natureza ?? [])
                  .map((n) => ({ rotulo: n.descricao || n.codigo, valor: Number(n.valor) }))
                  .sort((a, b) => b.valor - a.valor)
                  .slice(0, 6)}
              />
            )}
          </QuadroGrafico>
        </div>
      )}

      {(acesso.protocolo || acesso.frota || acesso.transporte) && (
        <div className="grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
          {acesso.protocolo && (
            <QuadroGrafico
              pergunta="Do que tratam os processos?"
              resposta={`Os assuntos que mais entraram nos últimos ${periodo} dias.`}
              acao={{ href: "/dashboard", label: "Dashboard" }}
            >
              {protQ.isLoading ? (
                <Esqueleto altura="h-48" />
              ) : protQ.isError ? (
                <Falhou />
              ) : (
                <ListaDeBarras
                  vazio="Nenhum processo aberto no período."
                  itens={(protQ.data?.por_assunto ?? [])
                    .slice()
                    .sort((a, b) => b.count - a.count)
                    .slice(0, 5)
                    .map((a) => ({ rotulo: a.label, valor: a.count }))}
                />
              )}
            </QuadroGrafico>
          )}
          {acesso.frota && <FrotaAgora />}
          {acesso.transporte && <AlvarasAgora />}
        </div>
      )}
    </section>
  );
}

/* ---------------------------------------------------------------- comum -- */

function Esqueleto({ altura }: { altura: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted motion-reduce:animate-none", altura)} aria-hidden="true" />;
}

function Falhou() {
  return <p className="py-6 text-center text-sm text-danger-soft-foreground">Não foi possível carregar agora.</p>;
}

/** `YYYY-MM-DD` → Date local (sem o deslocamento de fuso do `new Date(iso)`). */
function dia(iso: string): Date {
  const [a, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(a, m - 1, d);
}

function isoLocal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * A série do backend só traz os dias que tiveram processo; o gráfico precisa
 * dos zeros também, senão um feriado some e a linha liga sexta a terça.
 */
function serieCompleta(serie: { dia: string; count: number }[], periodo: number) {
  const porDia = new Map(serie.map((s) => [s.dia.slice(0, 10), s.count]));
  const hoje = new Date();
  const out: { dia: string; count: number }[] = [];
  for (let i = periodo - 1; i >= 0; i--) {
    const d = new Date(hoje.getFullYear(), hoje.getMonth(), hoje.getDate() - i);
    const k = isoLocal(d);
    out.push({ dia: k, count: porDia.get(k) ?? 0 });
  }
  return out;
}

const MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function rotuloMes(ym: string, comAno = false): string {
  const [a, m] = ym.split("-").map(Number);
  return comAno ? `${MES_CURTO[m - 1]}/${String(a).slice(2)}` : MES_CURTO[m - 1];
}

/* ---------------------------------------------------- faixa de cartões -- */

function FaixaDeTendencias({
  acesso,
  prot,
  pag,
  periodo,
}: {
  acesso: AcessoPanorama;
  prot: { data?: DashboardKpis; isLoading: boolean; isError: boolean };
  pag: { data?: PagamentosDashboard; isLoading: boolean; isError: boolean };
  periodo: number;
}) {
  const d = prot.data;
  const k = pag.data?.kpis;
  const serie = d ? serieCompleta(d.serie_temporal, periodo).map((s) => s.count) : [];
  const saidas = (pag.data?.fluxo_mensal ?? []).map((f) => Number(f.saidas));
  const cartoes: React.ReactNode[] = [];

  if (acesso.protocolo && !prot.isError) {
    const p = d?.prazos;
    const comPrazo = p ? p.dentro_do_prazo + p.vencendo + p.atrasado : 0;
    cartoes.push(
      <CartaoTendencia
        key="abertos"
        rotulo="Processos abertos"
        icone={FileInput}
        href="/dashboard"
        carregando={prot.isLoading}
        valor={d ? fmtNum(d.volume.abertos_periodo) : "—"}
        variacao={{ atual: d?.volume.abertos_periodo, anterior: d?.comparativo.abertos_anterior }}
        desenho={<Sparkline valores={serie} />}
        dica={`nos últimos ${periodo} dias`}
      />,
      <CartaoTendencia
        key="concluidos"
        rotulo="Concluídos"
        icone={CheckCircle2}
        href="/dashboard"
        carregando={prot.isLoading}
        valor={d ? fmtNum(d.conclusao.arquivados_periodo) : "—"}
        variacao={{ atual: d?.conclusao.arquivados_periodo, anterior: d?.comparativo.arquivados_anterior }}
        desenho={
          d?.conclusao.taxa_conclusao_pct != null ? (
            <Progresso pct={d.conclusao.taxa_conclusao_pct} cor={COR.sucesso} />
          ) : undefined
        }
        dica={
          d?.conclusao.taxa_conclusao_pct != null
            ? `${Math.round(d.conclusao.taxa_conclusao_pct)}% dos abertos no período`
            : "sem processos abertos no período"
        }
      />,
      <CartaoTendencia
        key="prazo"
        rotulo="No prazo agora"
        icone={Clock}
        href="/m/protocolo/protocolo/vencendo-prazo"
        carregando={prot.isLoading}
        valor={p?.percentual_no_prazo != null ? `${Math.round(p.percentual_no_prazo)}%` : "—"}
        desenho={
          p && comPrazo > 0 ? (
            <Empilhada
              partes={[
                { valor: p.dentro_do_prazo, cor: COR.sucesso },
                { valor: p.vencendo, cor: COR.alerta },
                { valor: p.atrasado, cor: COR.perigo },
              ]}
            />
          ) : undefined
        }
        // O percentual do backend conta "vencendo" como em dia (ainda não
        // venceu). A dica diz isso com os números, para bater com o anel
        // logo abaixo, que separa as duas fatias.
        dica={
          p
            ? comPrazo > 0
              ? `${p.dentro_do_prazo + p.vencendo} de ${comPrazo} com prazo em dia${
                  p.atrasado > 0 ? ` · ${p.atrasado} ${p.atrasado === 1 ? "atrasado" : "atrasados"}` : ""
                }`
              : "nenhum processo com prazo"
            : undefined
        }
      />,
    );
  }

  if (acesso.pagamentos && !pag.isError) {
    const ult = saidas.at(-1);
    const pen = saidas.at(-2);
    cartoes.push(
      <CartaoTendencia
        key="pago"
        rotulo="Pago no mês"
        icone={Wallet}
        href="/m/pagamentos/dashboard"
        carregando={pag.isLoading}
        valor={k ? fmtBRLCurto(Number(k.pago_no_mes)) : "—"}
        // Pagar mais não é bom nem ruim: a variação aparece, sem cor de juízo.
        dica={
          ult != null && pen != null && pen > 0
            ? `${ult >= pen ? "+" : "−"}${Math.abs(Math.round(((ult - pen) / pen) * 100))}% sobre o mês anterior`
            : "saídas dos últimos 12 meses"
        }
        desenho={<Sparkline valores={saidas} cor={GRAFICO.secundaria} />}
      />,
    );
    if (cartoes.length < 4) {
      const saldo = k ? Number(k.saldo_total) : 0;
      const disp = k ? Number(k.disponivel_total) : 0;
      cartoes.push(
        <CartaoTendencia
          key="disponivel"
          rotulo="Disponível em caixa"
          icone={Landmark}
          href="/m/pagamentos/caixa"
          carregando={pag.isLoading}
          valor={k ? fmtBRLCurto(disp) : "—"}
          desenho={saldo > 0 ? <Progresso pct={(disp / saldo) * 100} cor={GRAFICO.secundaria} /> : undefined}
          dica={k ? `de ${fmtBRLCurto(saldo)} em saldo; ${fmtBRLCurto(Number(k.comprometido_total))} comprometido` : undefined}
        />,
      );
    }
  }

  if (cartoes.length === 0) return null;
  return <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{cartoes.slice(0, 4)}</div>;
}

function Progresso({ pct, cor }: { pct: number; cor: string }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden="true">
      <div
        className="h-full rounded-full transition-[width] duration-slow ease-out-expo motion-reduce:transition-none"
        style={{ width: `${Math.min(100, Math.max(0, pct))}%`, backgroundColor: cor }}
      />
    </div>
  );
}

function Empilhada({ partes }: { partes: { valor: number; cor: string }[] }) {
  return (
    <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
      {partes
        .filter((p) => p.valor > 0)
        .map((p, i) => (
          <div key={i} className="h-full" style={{ flexGrow: p.valor, backgroundColor: p.cor }} />
        ))}
    </div>
  );
}

/* ------------------------------------------------- entrada de processos -- */

function EntradaDeProcessos({
  q,
  periodo,
  className,
}: {
  q: { data?: DashboardKpis; isLoading: boolean; isError: boolean };
  periodo: number;
  className?: string;
}) {
  const dados = React.useMemo(() => {
    if (!q.data) return [];
    const s = serieCompleta(q.data.serie_temporal, periodo);
    // Média dos 7 dias até ali: tira o serrote de fim de semana e mostra a
    // tendência. Só a partir de 30 dias — em 7 seria a própria média.
    return s.map((p, i) => {
      const janela = s.slice(Math.max(0, i - 6), i + 1);
      return {
        ...p,
        media: periodo >= 30 && i >= 6 ? janela.reduce((t, x) => t + x.count, 0) / janela.length : null,
      };
    });
  }, [q.data, periodo]);

  const total = dados.reduce((t, p) => t + p.count, 0);
  const pico = dados.reduce<(typeof dados)[number] | null>((m, p) => (!m || p.count > m.count ? p : m), null);
  const mediaDia = dados.length ? total / dados.length : 0;

  return (
    <QuadroGrafico
      className={className}
      pergunta="Quantos processos entraram?"
      resposta={
        q.data
          ? total === 0
            ? `Nenhum processo nos últimos ${periodo} dias.`
            : `${fmtNum(total)} em ${periodo} dias — ${mediaDia.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} por dia${
                pico && pico.count > 0
                  ? `; o pico foi ${dia(pico.dia).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })} (${pico.count}).`
                  : "."
              }`
          : undefined
      }
      acao={{ href: "/dashboard", label: "Dashboard executivo" }}
    >
      {q.isLoading ? (
        <Esqueleto altura="h-60" />
      ) : q.isError ? (
        <Falhou />
      ) : (
        <div className="h-60" role="img" aria-label={`Processos abertos por dia nos últimos ${periodo} dias: ${total} no total.`}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={dados} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="inicio-area" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stopColor={GRAFICO.principal} stopOpacity={0.32} />
                  <stop offset="100%" stopColor={GRAFICO.principal} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={GRAFICO.grade} strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="dia"
                {...EIXO}
                minTickGap={24}
                tickFormatter={(v: string) => dia(v).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}
              />
              <YAxis {...EIXO} allowDecimals={false} width={40} />
              {mediaDia > 0 && (
                <ReferenceLine
                  y={mediaDia}
                  stroke={GRAFICO.eixo}
                  strokeDasharray="4 4"
                  label={{ value: "média", position: "insideTopRight", fill: GRAFICO.eixo, fontSize: 10 }}
                />
              )}
              <Tooltip
                cursor={{ stroke: GRAFICO.eixo, strokeDasharray: "3 3" }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const p = payload[0].payload as (typeof dados)[number];
                  const data = dia(p.dia).toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "long" });
                  return (
                    <DicaGrafico
                      titulo={data.charAt(0).toUpperCase() + data.slice(1)}
                      linhas={[
                        { rotulo: "Processos abertos", valor: fmtNum(p.count), cor: GRAFICO.principal },
                        ...(p.media != null
                          ? [{ rotulo: "Média de 7 dias", valor: p.media.toLocaleString("pt-BR", { maximumFractionDigits: 1 }), cor: GRAFICO.secundaria }]
                          : []),
                      ]}
                    />
                  );
                }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke={GRAFICO.principal}
                strokeWidth={2}
                fill="url(#inicio-area)"
                activeDot={{ r: 5, strokeWidth: 2, stroke: "hsl(var(--surface-1))" }}
                isAnimationActive
                animationDuration={500}
              />
              {periodo >= 30 && (
                <Area
                  type="monotone"
                  dataKey="media"
                  stroke={GRAFICO.secundaria}
                  strokeWidth={1.5}
                  fill="none"
                  dot={false}
                  activeDot={false}
                  connectNulls
                  isAnimationActive
                  animationDuration={500}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
      {periodo >= 30 && q.data && total > 0 && (
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-foreground-muted">
          <Legenda cor={GRAFICO.principal} rotulo="Abertos no dia" />
          <Legenda cor={GRAFICO.secundaria} rotulo="Média de 7 dias" linha />
        </div>
      )}
    </QuadroGrafico>
  );
}

function Legenda({ cor, rotulo, linha }: { cor: string; rotulo: string; linha?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={cn(linha ? "h-0.5 w-3" : "h-2.5 w-2.5 rounded-sm")}
        style={{ backgroundColor: cor }}
        aria-hidden="true"
      />
      {rotulo}
    </span>
  );
}

/* ---------------------------------------------------------- prazos agora -- */

function PrazosAgora({ q }: { q: { data?: DashboardKpis; isLoading: boolean; isError: boolean } }) {
  const [ativo, setAtivo] = React.useState<number | null>(null);
  const p = q.data?.prazos;
  const fatias = p
    ? [
        { rotulo: "Dentro do prazo", valor: p.dentro_do_prazo, cor: COR.sucesso },
        { rotulo: "Vencendo", valor: p.vencendo, cor: COR.alerta },
        { rotulo: "Atrasados", valor: p.atrasado, cor: COR.perigo },
        { rotulo: "Sem prazo", valor: p.sem_prazo, cor: COR.neutro },
      ]
    : [];
  const total = fatias.reduce((t, f) => t + f.valor, 0);
  const destaque = ativo != null ? fatias[ativo] : null;

  return (
    <QuadroGrafico
      pergunta="Os processos estão no prazo?"
      resposta="Os que estão ativos agora, pelo prazo de cada um."
      acao={{ href: "/m/protocolo/protocolo/vencendo-prazo", label: "Vencendo" }}
    >
      {q.isLoading ? (
        <Esqueleto altura="h-60" />
      ) : q.isError ? (
        <Falhou />
      ) : total === 0 ? (
        <p className="py-10 text-center text-sm text-foreground-muted">Nenhum processo ativo agora.</p>
      ) : (
        <div className="flex flex-col items-center gap-4 sm:flex-row xl:flex-col 2xl:flex-row">
          <div className="relative h-44 w-44 shrink-0" role="img" aria-label={fatias.map((f) => `${f.rotulo}: ${f.valor}`).join(", ")}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={fatias.filter((f) => f.valor > 0)}
                  dataKey="valor"
                  nameKey="rotulo"
                  innerRadius="68%"
                  outerRadius="100%"
                  paddingAngle={2}
                  stroke="none"
                  isAnimationActive
                  animationDuration={500}
                  onMouseLeave={() => setAtivo(null)}
                  onMouseEnter={(_: unknown, i: number) => {
                    const f = fatias.filter((x) => x.valor > 0)[i];
                    setAtivo(fatias.indexOf(f));
                  }}
                >
                  {fatias
                    .filter((f) => f.valor > 0)
                    .map((f) => (
                      <Cell
                        key={f.rotulo}
                        fill={f.cor}
                        style={{ transition: "opacity 180ms", opacity: destaque && destaque !== f ? 0.25 : 1 }}
                      />
                    ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            {/* Centro do anel: o total, ou a fatia sob o mouse. */}
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">
              <span className="font-display text-2xl font-semibold tabular-nums text-foreground">
                {destaque ? destaque.valor : total}
              </span>
              <span className="max-w-[6.5rem] text-xs leading-tight text-foreground-muted">
                {destaque ? `${destaque.rotulo.toLowerCase()} · ${Math.round((destaque.valor / total) * 100)}%` : "ativos"}
              </span>
            </div>
          </div>
          <ul className="w-full space-y-0.5">
            {fatias.map((f, i) => (
              <li
                key={f.rotulo}
                // Fatia vazia não tem o que destacar no anel.
                onMouseEnter={() => f.valor > 0 && setAtivo(i)}
                onMouseLeave={() => setAtivo(null)}
                className={cn(
                  "-mx-1.5 flex items-center justify-between gap-2 rounded px-1.5 py-1 text-sm transition-[background-color,opacity] duration-fast",
                  ativo === i && "bg-muted",
                  ativo != null && ativo !== i && "opacity-40",
                )}
              >
                <span className="inline-flex items-center gap-2 text-foreground">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: f.cor }} aria-hidden="true" />
                  {f.rotulo}
                </span>
                <span className="font-semibold tabular-nums text-foreground">{f.valor}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </QuadroGrafico>
  );
}

/* -------------------------------------------------------- fluxo de caixa -- */

type Serie = "entradas" | "saidas" | "saldo";

function FluxoDeCaixa({
  q,
  className,
}: {
  q: { data?: PagamentosDashboard; isLoading: boolean; isError: boolean };
  className?: string;
}) {
  const router = useRouter();
  const [ocultas, setOcultas] = React.useState<Set<Serie>>(new Set());
  const dados = (q.data?.fluxo_mensal ?? []).map((f) => {
    const entradas = Number(f.entradas);
    const saidas = Number(f.saidas);
    return { mes: f.mes, entradas, saidas, saldo: entradas - saidas };
  });
  const totalE = dados.reduce((t, d) => t + d.entradas, 0);
  const totalS = dados.reduce((t, d) => t + d.saidas, 0);
  const alternar = (s: Serie) =>
    setOcultas((o) => {
      const n = new Set(o);
      if (n.has(s)) n.delete(s);
      else n.add(s);
      return n;
    });
  const SERIES: { chave: Serie; rotulo: string; cor: string; linha?: boolean }[] = [
    { chave: "entradas", rotulo: "Entradas", cor: GRAFICO.positivo },
    { chave: "saidas", rotulo: "Saídas", cor: GRAFICO.negativo },
    { chave: "saldo", rotulo: "Saldo do mês", cor: corDaSerie(1), linha: true },
  ];

  return (
    <QuadroGrafico
      className={className}
      pergunta="Como o dinheiro entrou e saiu?"
      resposta={
        q.data
          ? `Em 12 meses: ${fmtBRLCurto(totalE)} de entradas e ${fmtBRLCurto(totalS)} de saídas. Clique num mês para abrir o caixa.`
          : undefined
      }
      acao={{ href: "/m/pagamentos/caixa", label: "Caixa" }}
    >
      {q.isLoading ? (
        <Esqueleto altura="h-60" />
      ) : q.isError ? (
        <Falhou />
      ) : (
        <>
          <div className="h-60" role="img" aria-label="Entradas e saídas por mês nos últimos 12 meses.">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={dados}
                margin={{ top: 8, right: 8, left: 4, bottom: 0 }}
                barGap={2}
                onClick={() => router.push("/m/pagamentos/caixa")}
                className="cursor-pointer"
              >
                <CartesianGrid stroke={GRAFICO.grade} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="mes" {...EIXO} tickFormatter={(v: string) => rotuloMes(v)} />
                <YAxis {...EIXO} width={64} tickFormatter={(v: number) => fmtBRLCurto(v)} />
                <ReferenceLine y={0} stroke={GRAFICO.eixo} />
                <Tooltip
                  cursor={{ fill: GRAFICO.cursor, opacity: 0.6 }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0].payload as (typeof dados)[number];
                    return (
                      <DicaGrafico
                        titulo={rotuloMes(d.mes, true)}
                        linhas={SERIES.filter((s) => !ocultas.has(s.chave)).map((s) => ({
                          rotulo: s.rotulo,
                          valor: fmtBRL(d[s.chave]),
                          cor: s.cor,
                        }))}
                      />
                    );
                  }}
                />
                {!ocultas.has("entradas") && (
                  <Bar dataKey="entradas" fill={GRAFICO.positivo} radius={[3, 3, 0, 0]} maxBarSize={18} animationDuration={500} />
                )}
                {!ocultas.has("saidas") && (
                  <Bar dataKey="saidas" fill={GRAFICO.negativo} radius={[3, 3, 0, 0]} maxBarSize={18} animationDuration={500} />
                )}
                {!ocultas.has("saldo") && (
                  <Line
                    type="monotone"
                    dataKey="saldo"
                    stroke={corDaSerie(1)}
                    strokeWidth={2}
                    dot={{ r: 2.5, fill: corDaSerie(1), strokeWidth: 0 }}
                    activeDot={{ r: 5, strokeWidth: 2, stroke: "hsl(var(--surface-1))" }}
                    animationDuration={500}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {/* Legenda que liga e desliga a série — como no IAnalisys. */}
          <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label="Séries do gráfico">
            {SERIES.map((s) => {
              const ligada = !ocultas.has(s.chave);
              return (
                <button
                  key={s.chave}
                  type="button"
                  aria-pressed={ligada}
                  onClick={() => alternar(s.chave)}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors duration-fast",
                    ligada
                      ? "border-border-strong bg-surface-1 text-foreground hover:bg-muted"
                      : "border-dashed border-border text-foreground-subtle hover:bg-muted",
                  )}
                >
                  <span
                    className={cn(s.linha ? "h-0.5 w-3" : "h-2.5 w-2.5 rounded-sm", !ligada && "opacity-40")}
                    style={{ backgroundColor: s.cor }}
                    aria-hidden="true"
                  />
                  {s.rotulo}
                </button>
              );
            })}
          </div>
        </>
      )}
    </QuadroGrafico>
  );
}

/* ---------------------------------------------------- frota e alvarás -- */

function FrotaAgora() {
  // Mesma consulta (e cache) da tela de Veículos.
  const q = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll(), staleTime: 60_000 });
  const v = q.data ?? [];
  const conta = (s: string) => v.filter((x) => x.situacao === s).length;
  return (
    <QuadroGrafico
      pergunta="Como está a frota agora?"
      resposta={q.data ? `${v.length} ${v.length === 1 ? "veículo cadastrado" : "veículos cadastrados"}.` : undefined}
      acao={{ href: "/m/frota/veiculos", label: "Veículos" }}
    >
      {q.isLoading ? (
        <Esqueleto altura="h-24" />
      ) : q.isError ? (
        <Falhou />
      ) : (
        <BarraSegmentada
          unidade={["veículo", "veículos"]}
          segmentos={[
            { rotulo: "Disponíveis", valor: conta("disponivel"), cor: COR.sucesso, href: "/m/frota/veiculos" },
            { rotulo: "Em uso", valor: conta("em_uso"), cor: COR.info, href: "/m/frota/solicitacoes" },
            { rotulo: "Em manutenção", valor: conta("manutencao"), cor: COR.alerta, href: "/m/frota/manutencoes" },
            { rotulo: "Fora de uso", valor: conta("inativo") + conta("baixado"), cor: COR.neutro, href: "/m/frota/veiculos" },
          ]}
        />
      )}
    </QuadroGrafico>
  );
}

function AlvarasAgora() {
  // Mesma chave dos cartões de pendência e do relatório de alvarás.
  const q = useQuery({
    queryKey: ["/transporte-regulado/alvaras/relatorio/kpis"],
    queryFn: () => api.alvaras.relatorio.kpis(),
    staleTime: 60_000,
  });
  const k = q.data;
  return (
    <QuadroGrafico
      pergunta="Os alvarás estão em dia?"
      resposta={
        k
          ? `${k.total_alvaras} ${k.total_alvaras === 1 ? "alvará" : "alvarás"}; "a renovar" vence em até 30 dias.`
          : undefined
      }
      acao={{ href: "/m/transporte/relatorio", label: "Relatório" }}
    >
      {q.isLoading ? (
        <Esqueleto altura="h-24" />
      ) : q.isError ? (
        <Falhou />
      ) : k ? (
        <BarraSegmentada
          unidade={["alvará", "alvarás"]}
          segmentos={[
            { rotulo: "Em dia", valor: k.ativos, cor: COR.sucesso, href: "/m/transporte/relatorio" },
            { rotulo: "A renovar", valor: k.a_renovar_30d, cor: COR.alerta, href: "/m/transporte/relatorio" },
            { rotulo: "Vencidos", valor: k.vencidos, cor: COR.perigo, href: "/m/transporte/relatorio" },
            { rotulo: "Sem validade", valor: k.indefinidos, cor: COR.neutro, href: "/m/transporte/relatorio" },
          ]}
        />
      ) : null}
    </QuadroGrafico>
  );
}

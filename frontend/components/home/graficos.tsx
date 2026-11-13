"use client";

/**
 * Peças pequenas de gráfico do Início. Ficam aqui, e não em components/ui,
 * enquanto só o Início as usa; a primeira tela que precisar de uma delas a
 * promove para ui/ (e para a seção "Padrão de tela" do design system).
 *
 * Cor vem sempre de lib/chart-theme ou de token semântico — nada de hex.
 */
import { ArrowDownRight, ArrowRight, ArrowUpRight, Minus, type LucideIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { GRAFICO } from "@/lib/chart-theme";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------- formatos -- */

export function fmtNum(n: number): string {
  return n.toLocaleString("pt-BR");
}

/** R$ curto para eixo e cartão: "R$ 1,2 mi", "R$ 850 mil", "R$ 420". */
export function fmtBRLCurto(v: number): string {
  const abs = Math.abs(v);
  const sinal = v < 0 ? "−" : "";
  if (abs >= 1_000_000) return `${sinal}R$ ${(abs / 1_000_000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mi`;
  if (abs >= 1_000) return `${sinal}R$ ${(abs / 1_000).toLocaleString("pt-BR", { maximumFractionDigits: 0 })} mil`;
  return `${sinal}R$ ${abs.toLocaleString("pt-BR", { maximumFractionDigits: 0 })}`;
}

export function fmtBRL(v: number): string {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

/* ------------------------------------------------------- seletor período -- */

export function SeletorPeriodo<T extends number>({
  valor,
  opcoes,
  onChange,
  rotulo,
}: {
  valor: T;
  opcoes: { value: T; label: string }[];
  onChange: (v: T) => void;
  /** Nome do grupo para leitor de tela ("Período do panorama"). */
  rotulo: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={rotulo}
      className="inline-flex rounded-md border border-border bg-surface-1 p-0.5 shadow-xs"
    >
      {opcoes.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={valor === o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "h-8 rounded px-3 text-xs font-medium transition-colors duration-fast",
            valor === o.value
              ? "bg-brand text-primary-foreground shadow-sm"
              : "text-foreground-muted hover:bg-muted hover:text-foreground",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------ sparkline -- */

/**
 * Linha mínima com área em degradê — o "desenho da tendência" ao lado do
 * número, como nos cartões do IAnalisys. SVG puro: não precisa de eixo nem
 * de tooltip, e recharts para 30 pontos num cartão é peso à toa.
 */
export function Sparkline({
  valores,
  cor = GRAFICO.principal,
  className,
}: {
  valores: number[];
  cor?: string;
  className?: string;
}) {
  const id = React.useId();
  if (valores.length < 2) return null;
  const W = 120;
  const H = 36;
  const max = Math.max(...valores);
  const min = Math.min(...valores);
  const faixa = max - min || 1;
  const pts = valores.map((v, i) => [
    (i / (valores.length - 1)) * W,
    H - 3 - ((v - min) / faixa) * (H - 6),
  ]);
  const linha = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = `${linha} L${W},${H} L0,${H} Z`;
  const [ux, uy] = pts[pts.length - 1];
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      className={cn("h-9 w-full overflow-visible", className)}
      style={{ color: cor }}
    >
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="currentColor" stopOpacity={0.28} />
          <stop offset="100%" stopColor="currentColor" stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path d={linha} fill="none" stroke="currentColor" strokeWidth={1.75} vectorEffect="non-scaling-stroke" />
      <circle cx={ux} cy={uy} r={2.5} fill="currentColor" />
    </svg>
  );
}

/* --------------------------------------------------- cartão de tendência -- */

export interface Variacao {
  atual: number | null | undefined;
  anterior: number | null | undefined;
  /** Cair é bom (tempo médio, atrasos). */
  menorMelhor?: boolean;
}

function VariacaoPill({ atual, anterior, menorMelhor }: Variacao) {
  if (atual == null || anterior == null) return null;
  if (atual === anterior) {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs text-foreground-subtle">
        <Minus className="h-3 w-3" aria-hidden="true" />
        igual ao período anterior
      </span>
    );
  }
  const subiu = atual > anterior;
  const bom = subiu !== !!menorMelhor;
  const pct = anterior === 0 ? null : Math.round(((atual - anterior) / Math.abs(anterior)) * 100);
  const Icone = subiu ? ArrowUpRight : ArrowDownRight;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-xs font-medium tabular-nums",
        bom ? "bg-success-soft text-success-soft-foreground" : "bg-danger-soft text-danger-soft-foreground",
      )}
      title={`Período anterior: ${fmtNum(anterior)}`}
    >
      <Icone className="h-3 w-3" aria-hidden="true" />
      {pct === null ? "novo" : `${pct > 0 ? "+" : ""}${pct}%`}
    </span>
  );
}

/**
 * O número, para onde ele vai e como chegou até aqui: rótulo, valor grande,
 * variação contra o período anterior e um desenho (sparkline, barra ou
 * faixa). O cartão inteiro é o link para a tela que prova o número.
 */
export function CartaoTendencia({
  rotulo,
  valor,
  icone: Icone,
  href,
  variacao,
  dica,
  desenho,
  carregando,
}: {
  rotulo: string;
  valor: React.ReactNode;
  icone: LucideIcon;
  href: string;
  variacao?: Variacao;
  dica?: React.ReactNode;
  desenho?: React.ReactNode;
  carregando?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group flex min-w-0 flex-col gap-2 rounded-card border border-border bg-surface-1 p-4 shadow-card",
        "transition-[box-shadow,border-color,transform] duration-fast ease-out",
        "hover:-translate-y-0.5 hover:border-border-strong hover:shadow-card-hover",
        "motion-reduce:transition-none motion-reduce:hover:translate-y-0",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">{rotulo}</span>
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10 text-brand dark:bg-brand/20">
          <Icone className="h-3.5 w-3.5" aria-hidden="true" />
        </span>
      </div>
      {carregando ? (
        <div className="h-[4.5rem] animate-pulse rounded bg-muted motion-reduce:animate-none" aria-hidden="true" />
      ) : (
        <>
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="font-display text-2xl font-semibold tabular-nums text-foreground">{valor}</span>
            {variacao && <VariacaoPill {...variacao} />}
          </div>
          {desenho}
          {dica && <span className="text-xs text-foreground-muted">{dica}</span>}
        </>
      )}
      <span className="mt-auto inline-flex items-center gap-1 text-xs font-medium text-foreground-subtle transition-colors duration-fast group-hover:text-primary">
        Ver detalhe
        <ArrowRight className="h-3 w-3 transition-transform duration-fast group-hover:translate-x-0.5" aria-hidden="true" />
      </span>
    </Link>
  );
}

/* ----------------------------------------------------- moldura de gráfico -- */

/**
 * O cartão de cada gráfico. O título é a PERGUNTA que o gráfico responde
 * ("Quantos processos entraram?") — o padrão das telas que o Heitor gostou no
 * IAnalisys —, e a resposta curta vem na linha de baixo.
 */
export function QuadroGrafico({
  pergunta,
  resposta,
  acao,
  children,
  className,
}: {
  pergunta: string;
  resposta?: React.ReactNode;
  acao?: { href: string; label: string };
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      aria-label={pergunta}
      className={cn("flex min-w-0 flex-col rounded-card border border-border bg-surface-1 shadow-card", className)}
    >
      <header className="flex items-start justify-between gap-3 px-5 pt-4">
        <div className="min-w-0">
          <h3 className="font-display text-sm font-semibold text-foreground">{pergunta}</h3>
          {resposta && <p className="mt-0.5 text-xs text-foreground-muted">{resposta}</p>}
        </div>
        {acao && (
          <Link
            href={acao.href}
            className="-mx-1.5 inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-xs font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
          >
            {acao.label}
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        )}
      </header>
      <div className="flex-1 px-5 pb-4 pt-3">{children}</div>
    </section>
  );
}

/* ------------------------------------------------------- lista de barras -- */

/**
 * Ranking em barras horizontais: rótulo, barra proporcional ao maior e o
 * valor à direita. Lê-se de cima para baixo como uma lista — mais fácil que
 * pizza com seis fatias. Passar o mouse destaca a linha e mostra a fatia do
 * total.
 */
export function ListaDeBarras({
  itens,
  formato = fmtNum,
  cor = GRAFICO.principal,
  vazio = "Nada no período.",
}: {
  itens: { rotulo: string; valor: number; href?: string }[];
  formato?: (v: number) => string;
  cor?: string;
  vazio?: string;
}) {
  if (itens.length === 0) return <p className="py-6 text-center text-sm text-foreground-muted">{vazio}</p>;
  const max = Math.max(...itens.map((i) => i.valor)) || 1;
  const total = itens.reduce((s, i) => s + i.valor, 0) || 1;
  return (
    <ol className="space-y-1">
      {itens.map((i) => {
        const pct = Math.round((i.valor / total) * 100);
        const conteudo = (
          <>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-foreground" title={i.rotulo}>
                {i.rotulo}
              </span>
              <span className="shrink-0 tabular-nums text-foreground">
                {formato(i.valor)}
                <span className="ml-1.5 text-xs text-foreground-subtle">{pct}%</span>
              </span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full transition-[width] duration-slow ease-out-expo motion-reduce:transition-none"
                style={{ width: `${Math.max(2, (i.valor / max) * 100)}%`, backgroundColor: cor }}
              />
            </div>
          </>
        );
        return (
          <li key={i.rotulo}>
            {i.href ? (
              <Link href={i.href} className="-mx-2 block rounded-md px-2 py-1.5 transition-colors duration-fast hover:bg-muted">
                {conteudo}
              </Link>
            ) : (
              <div className="-mx-2 rounded-md px-2 py-1.5 transition-colors duration-fast hover:bg-muted">{conteudo}</div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

/* --------------------------------------------------------- barra em faixa -- */

export interface Segmento {
  rotulo: string;
  valor: number;
  /** `hsl(var(--token))` — status semântico ou série do chart-theme. */
  cor: string;
  href?: string;
}

/**
 * Uma faixa dividida pelo peso de cada parte (a frota agora: disponível, em
 * uso, em manutenção…), com a legenda embaixo. Passar o mouse numa parte —
 * na faixa ou na legenda — destaca as duas.
 */
export function BarraSegmentada({ segmentos, unidade }: { segmentos: Segmento[]; unidade: [string, string] }) {
  const [ativo, setAtivo] = React.useState<string | null>(null);
  const total = segmentos.reduce((s, x) => s + x.valor, 0);
  if (total === 0) return <p className="py-4 text-center text-sm text-foreground-muted">Nada cadastrado ainda.</p>;
  const nome = (n: number) => (n === 1 ? unidade[0] : unidade[1]);
  return (
    <div className="space-y-3">
      <div className="flex h-3 gap-0.5 overflow-hidden rounded-full" onMouseLeave={() => setAtivo(null)}>
        {segmentos
          .filter((s) => s.valor > 0)
          .map((s) => (
            <div
              key={s.rotulo}
              title={`${s.rotulo}: ${s.valor} ${nome(s.valor)}`}
              onMouseEnter={() => setAtivo(s.rotulo)}
              className={cn(
                "h-full transition-opacity duration-fast first:rounded-l-full last:rounded-r-full",
                ativo && ativo !== s.rotulo && "opacity-30",
              )}
              style={{ flexGrow: s.valor, backgroundColor: s.cor }}
            />
          ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1">
        {segmentos.map((s) => {
          const linha = (
            <>
              <span className="flex min-w-0 items-center gap-2 text-sm text-foreground">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: s.cor }} aria-hidden="true" />
                <span className="truncate">{s.rotulo}</span>
              </span>
              <span className="text-sm font-semibold tabular-nums text-foreground">{s.valor}</span>
            </>
          );
          const classe = cn(
            "-mx-1.5 flex items-center justify-between gap-2 rounded px-1.5 py-1 transition-[background-color,opacity] duration-fast",
            ativo && ativo !== s.rotulo && "opacity-40",
            ativo === s.rotulo && "bg-muted",
          );
          return (
            <li key={s.rotulo} onMouseEnter={() => setAtivo(s.rotulo)} onMouseLeave={() => setAtivo(null)}>
              {s.href && s.valor > 0 ? (
                <Link href={s.href} className={cn(classe, "hover:bg-muted")}>
                  {linha}
                </Link>
              ) : (
                <div className={classe}>{linha}</div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/* --------------------------------------------------------- tooltip tema -- */

/** Caixa do tooltip do recharts nas cores do tema (a padrão é branca fixa). */
export function DicaGrafico({
  titulo,
  linhas,
}: {
  titulo: string;
  linhas: { rotulo: string; valor: string; cor?: string }[];
}) {
  return (
    <div className="rounded-md border border-border bg-surface-3 px-3 py-2 text-xs shadow-md">
      <p className="mb-1 font-semibold text-foreground">{titulo}</p>
      {linhas.map((l) => (
        <p key={l.rotulo} className="flex items-center justify-between gap-4 text-foreground-muted">
          <span className="inline-flex items-center gap-1.5">
            {l.cor && <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: l.cor }} aria-hidden="true" />}
            {l.rotulo}
          </span>
          <span className="font-medium tabular-nums text-foreground">{l.valor}</span>
        </p>
      ))}
    </div>
  );
}

"use client";

import { ArrowUpRight, Check, Landmark } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";

import { fmtMoeda } from "@/components/pagamentos/format";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Combobox } from "@/components/ui/combobox";
import type { ContaElegivel } from "@/lib/api";
import { cn } from "@/lib/utils";

/*
 * Peças da tela de Autorizações (2026-11-11, pedido do Heitor: "o menu de
 * autorizações não está bom"). A tela é uma fila de seleção em lote: marcar
 * itens, ver quanto sai de cada conta, decidir. Estas peças existem para que
 * as duas abas (Despesa e Pagamento) se leiam igual.
 */

/** Soma de valores que chegam da API como texto decimal ("1250.00"). */
export function somar<T>(itens: T[], valor: (item: T) => string | number): number {
  return itens.reduce((acc, item) => acc + (Number(valor(item)) || 0), 0);
}

/** "1 despesa" / "3 despesas". */
export function contar(n: number, singular: string, plural: string): string {
  return `${n} ${n === 1 ? singular : plural}`;
}

/**
 * Cabeçalho de um grupo (uma fonte, ou uma conta): marcar todos, nome e
 * descrição, e à direita quantos itens e quanto somam. A caixa fica
 * "meio marcada" quando só parte do grupo está escolhida.
 */
export function CabecalhoDoGrupo({
  titulo,
  subtitulo,
  marcados,
  total,
  quantidade,
  valorTotal,
  onMarcarTodos,
  desabilitado,
  rotuloMarcarTodos,
  selo,
}: {
  titulo: ReactNode;
  subtitulo?: ReactNode;
  /** Quantos itens do grupo estão marcados. */
  marcados: number;
  total: number;
  /** Ex.: "2 despesas". */
  quantidade: string;
  valorTotal: number;
  onMarcarTodos: () => void;
  desabilitado?: boolean;
  rotuloMarcarTodos: string;
  selo?: ReactNode;
}) {
  const ref = useRef<HTMLInputElement>(null);
  const todos = total > 0 && marcados === total;
  const parte = marcados > 0 && !todos;
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = parte;
  }, [parte]);

  return (
    <header className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-4 py-3">
      <Checkbox
        ref={ref}
        checked={todos}
        onChange={onMarcarTodos}
        disabled={desabilitado || total === 0}
        aria-label={rotuloMarcarTodos}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-display text-base font-semibold tracking-tight text-titulo">{titulo}</h3>
          {selo}
        </div>
        {subtitulo && <p className="truncate text-sm text-foreground-muted">{subtitulo}</p>}
      </div>
      <p className="shrink-0 text-right text-sm text-foreground-muted">
        {quantidade} ·{" "}
        <span className="font-semibold tabular-nums text-foreground">{fmtMoeda(valorTotal)}</span>
      </p>
    </header>
  );
}

/**
 * Uma linha da fila: a linha inteira marca e desmarca (é um `<label>`), e a
 * seta à direita abre a solicitação sem mexer na seleção. Marcada, a linha
 * ganha o fundo da marca — dá para ver o lote de relance.
 */
export function LinhaSelecionavel({
  marcada,
  onAlternar,
  desabilitada,
  rotulo,
  titulo,
  selos,
  descricao,
  detalhe,
  valor,
  href,
}: {
  marcada: boolean;
  onAlternar: () => void;
  desabilitada?: boolean;
  /** Nome acessível da caixa: "Selecionar Papelaria Central — R$ 63.200,00". */
  rotulo: string;
  titulo: string;
  selos?: ReactNode;
  descricao?: ReactNode;
  detalhe?: ReactNode;
  valor: string | number;
  href: string;
}) {
  return (
    <li>
      <label
        className={cn(
          "flex items-center gap-3 px-4 py-3 transition-colors duration-fast",
          desabilitada ? "cursor-not-allowed opacity-60" : "cursor-pointer hover:bg-surface-2",
          marcada && "bg-brand/5 hover:bg-brand/10 dark:bg-brand/10 dark:hover:bg-brand/15",
        )}
      >
        <Checkbox
          checked={marcada}
          onChange={onAlternar}
          disabled={desabilitada}
          aria-label={rotulo}
          className="shrink-0"
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate font-medium text-foreground" title={titulo}>
              {titulo}
            </span>
            {selos}
          </div>
          {descricao && <p className="truncate text-sm text-foreground-muted">{descricao}</p>}
          {detalhe && <p className="truncate text-xs text-foreground-subtle">{detalhe}</p>}
        </div>
        <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
          {fmtMoeda(valor)}
        </span>
        <Link
          href={href}
          aria-label={`Abrir a solicitação de ${titulo}`}
          title="Abrir a solicitação"
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </label>
    </li>
  );
}

/**
 * Quanto do disponível da conta o lote marcado consome. Sem nada marcado,
 * diz o que fazer; passando do disponível, diz quanto falta — a autorização
 * seria recusada pelo servidor por saldo.
 */
export function MedidorDeSaldo({
  selecionado,
  disponivel,
}: {
  selecionado: number;
  disponivel: string | number;
}) {
  const disp = Number(disponivel) || 0;
  if (selecionado <= 0) {
    return (
      <p className="text-xs text-foreground-subtle">
        Marque as despesas abaixo para ver quanto sai desta conta.
      </p>
    );
  }
  const pct = disp > 0 ? (selecionado / disp) * 100 : 100;
  const excede = selecionado > disp;
  const alerta = !excede && pct >= 80;
  return (
    <div className="space-y-1.5">
      <div
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
        role="meter"
        aria-label="Consumo do disponível da conta"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.min(100, Math.round(pct))}
      >
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-base",
            excede ? "bg-danger" : alerta ? "bg-warning" : "bg-success",
          )}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <p
        className={cn(
          "text-xs tabular-nums",
          excede ? "font-medium text-danger-soft-foreground" : "text-foreground-muted",
        )}
      >
        {excede ? (
          <>
            O marcado passa {fmtMoeda(selecionado - disp)} do disponível ({fmtMoeda(disp)}) — o
            servidor recusa por saldo. Desmarque algo ou escolha outra conta.
          </>
        ) : (
          <>
            Sai {fmtMoeda(selecionado)} de {fmtMoeda(disp)} disponíveis · sobram{" "}
            <span className="font-medium text-foreground">{fmtMoeda(disp - selecionado)}</span>
          </>
        )}
      </p>
    </div>
  );
}

function linhaDaConta(c: ContaElegivel): string {
  return `${c.banco} · ag. ${c.agencia} · c/ ${c.conta_mascarada}`;
}

/**
 * De qual conta sai o dinheiro. Até quatro contas, ficam todas à vista como
 * cartões (nome, banco e o disponível — o que decide a escolha); mais que
 * isso, um campo com busca. Era um `<select>` que espremia tudo numa linha só
 * ("DEMO Conta FUNDEB · Caixa Econômica ag.0987 c/****2310 — disp. R$ …").
 */
export function EscolhaDeConta({
  id,
  contas,
  valor,
  onChange,
  erro,
}: {
  id: string;
  contas: ContaElegivel[];
  valor: number | undefined;
  onChange: (idConta: number) => void;
  erro?: string;
}) {
  const idErro = `${id}-erro`;
  const titulo = (
    <p id={`${id}-titulo`} className="text-sm font-medium text-foreground">
      De qual conta sai o dinheiro?
    </p>
  );
  const mensagem = erro && (
    <p id={idErro} role="alert" className="text-xs font-medium text-danger-soft-foreground">
      {erro}
    </p>
  );

  if (contas.length > 4) {
    return (
      <div id={id} className="space-y-1.5 scroll-mt-28">
        <label htmlFor={`${id}-busca`}>{titulo}</label>
        <Combobox
          id={`${id}-busca`}
          aria-invalid={!!erro}
          aria-describedby={erro ? idErro : undefined}
          options={contas.map((c) => ({
            value: c.id_conta,
            label: c.nome,
            hint: `${linhaDaConta(c)} · disponível ${fmtMoeda(c.disponivel)}`,
          }))}
          value={valor ?? null}
          onChange={(v) => v != null && onChange(Number(v))}
          placeholder="Escolha a conta pagadora"
          searchPlaceholder="Buscar pelo nome ou pelo banco…"
          emptyText="Nenhuma conta com esse nome."
        />
        {mensagem}
      </div>
    );
  }

  return (
    <div id={id} className="space-y-2 scroll-mt-28">
      {titulo}
      <div
        role="radiogroup"
        aria-labelledby={`${id}-titulo`}
        aria-describedby={erro ? idErro : undefined}
        aria-invalid={erro ? true : undefined}
        className="grid gap-2 sm:grid-cols-2"
      >
        {contas.map((c) => {
          const escolhida = c.id_conta === valor;
          return (
            <label
              key={c.id_conta}
              className={cn(
                "relative flex cursor-pointer items-start gap-3 rounded-lg border bg-card px-3 py-2.5 transition-colors duration-fast",
                "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                escolhida
                  ? "border-brand bg-brand/5 dark:bg-brand/10"
                  : erro
                    ? "border-danger/60 hover:border-danger"
                    : "border-border hover:border-border-strong hover:bg-surface-2",
              )}
            >
              <input
                type="radio"
                name={`${id}-conta`}
                value={c.id_conta}
                checked={escolhida}
                onChange={() => onChange(c.id_conta)}
                aria-label={`${c.nome}, disponível ${fmtMoeda(c.disponivel)}`}
                className="sr-only"
              />
              <span
                aria-hidden="true"
                className={cn(
                  "mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md",
                  escolhida ? "bg-brand text-primary-foreground" : "bg-muted text-foreground-muted",
                )}
              >
                {escolhida ? <Check className="h-4 w-4" /> : <Landmark className="h-4 w-4" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-foreground" title={c.nome}>
                  {c.nome}
                </span>
                <span className="block truncate text-xs text-foreground-subtle">{linhaDaConta(c)}</span>
                {c.abaixo_minimo && (
                  <Badge intent="warning" className="mt-1">
                    Abaixo do mínimo
                  </Badge>
                )}
              </span>
              <span className="shrink-0 text-right">
                <span className="block text-[11px] text-foreground-subtle">Disponível</span>
                <span className="block whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
                  {fmtMoeda(c.disponivel)}
                </span>
              </span>
            </label>
          );
        })}
      </div>
      {mensagem}
    </div>
  );
}

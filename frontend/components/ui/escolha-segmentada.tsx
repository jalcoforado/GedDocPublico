"use client";

import { AlertCircle, type LucideIcon } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export interface OpcaoEscolha<V extends string> {
  valor: V;
  rotulo: string;
  icon?: LucideIcon;
  /** O que acontece ao escolher esta opção — aparece sob o grupo quando marcada. */
  descricao?: string;
  /** Opção que existe mas não está disponível agora (o `title` diz por quê). */
  disabled?: boolean;
  title?: string;
}

/**
 * Escolha entre 2 a 4 opções nomeadas, todas à vista. Para poucas opções é
 * melhor que um `<select>` (que esconde as alternativas) e que um
 * interruptor (que só diz "ligado/desligado", sem nomear o outro lado).
 *
 * Nasceu como `EscolhaConfig` no formulário de abertura de processo e virou
 * componente do design system em 2026-11-10. Por baixo são
 * `<input type="radio">` nativos: setas, Tab e leitor de tela funcionam sem
 * código próprio. A descrição da opção marcada fica sob o grupo, ligada por
 * `aria-describedby`.
 */
export function EscolhaSegmentada<V extends string>({
  nome,
  titulo,
  valor,
  opcoes,
  onChange,
  moldura = true,
  required,
  error,
  className,
}: {
  /** `name` dos rádios — único na tela. */
  nome: string;
  titulo: string;
  valor: V;
  opcoes: OpcaoEscolha<V>[];
  onChange: (v: V) => void;
  /** Com moldura (cartão próprio) ou solto dentro de uma seção. */
  moldura?: boolean;
  /** Asterisco no título, como no `FormField`. */
  required?: boolean;
  /** Erro do grupo (ex.: nenhuma opção escolhida e o grupo é obrigatório). */
  error?: string;
  className?: string;
}) {
  const atual = opcoes.find((o) => o.valor === valor);
  const descricaoId = `${nome}-descricao`;
  const erroId = `${nome}-erro`;
  return (
    <fieldset
      aria-describedby={error ? erroId : undefined}
      aria-invalid={error ? true : undefined}
      className={cn(
        moldura && "rounded-lg border border-border bg-surface-1 p-3",
        moldura && error && "border-danger",
        className,
      )}
    >
      <legend className="sr-only">
        {titulo}
        {required ? " (obrigatório)" : ""}
      </legend>
      <div aria-hidden="true" className="mb-2 text-sm font-medium text-foreground">
        {titulo}
        {required && <span className="ml-0.5 text-danger">*</span>}
      </div>
      <div
        className={cn(
          "grid gap-1 rounded-md bg-surface-2 p-1",
          opcoes.length === 2 && "grid-cols-2",
          opcoes.length === 3 && "grid-cols-3",
          opcoes.length >= 4 && "grid-cols-2 sm:grid-cols-4",
        )}
      >
        {opcoes.map((o) => {
          const marcada = o.valor === valor;
          const Icon = o.icon;
          return (
            <label
              key={o.valor}
              title={o.title}
              className={cn(
                // `relative` prende o rádio `sr-only` (absoluto) dentro da
                // opção; sem ele o foco do clique rolava a página até o rádio.
                "relative flex min-h-9 cursor-pointer items-center justify-center gap-1.5 rounded px-2 py-1.5 text-center text-sm transition-colors duration-fast",
                "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                o.disabled && "cursor-not-allowed opacity-50",
                marcada
                  ? "bg-card font-medium text-foreground shadow-xs"
                  : !o.disabled && "text-foreground-muted hover:bg-card/60 hover:text-foreground",
                !marcada && o.disabled && "text-foreground-muted",
              )}
            >
              <input
                type="radio"
                name={nome}
                value={o.valor}
                checked={marcada}
                disabled={o.disabled}
                onChange={() => onChange(o.valor)}
                aria-describedby={marcada && o.descricao ? descricaoId : undefined}
                className="sr-only"
              />
              {Icon && <Icon className={cn("h-4 w-4 shrink-0", marcada && "text-brand")} aria-hidden="true" />}
              {o.rotulo}
            </label>
          );
        })}
      </div>
      {atual?.descricao && (
        <p id={descricaoId} className="mt-2 text-xs text-foreground-muted">
          {atual.descricao}
        </p>
      )}
      {error && (
        <p id={erroId} className="mt-2 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground">
          <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </fieldset>
  );
}

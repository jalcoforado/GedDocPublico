import * as React from "react";

import { cn } from "@/lib/utils";

interface SectionCardProps {
  /**
   * Título da seção. Renderizado como `<h2>` semântico, mas com tamanho
   * compatível com card (não com page-title).
   */
  title: string;
  /** Subtítulo curto explicando o propósito da seção. */
  description?: string;
  /** Ícone decorativo opcional ao lado do título. */
  icon?: React.ComponentType<{ className?: string }>;
  /**
   * Numeração opcional ("passo N"). Usada em formulários multi-step
   * (ex: /processos/novo). Em uso genérico, omitir.
   */
  step?: number;
  children: React.ReactNode;
  className?: string;
}

/**
 * Card de seção com header + body. Generaliza o helper local
 * historicamente em /processos/novo para reuso em catálogo, dashboard,
 * detalhe do cidadão, etc.
 *
 * Aparência preservada: bordas suaves, header com ícone tinto e body
 * com padding e gap padrão. O `step` opcional exibe a pílula
 * "passo N" que existia no formulário de abertura.
 */
export function SectionCard({
  title,
  description,
  icon: Icon,
  step,
  children,
  className,
}: SectionCardProps) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border bg-card shadow-xs",
        className,
      )}
    >
      <header className="flex items-start gap-3 border-b border-border px-5 py-4">
        {Icon && (
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
            aria-hidden="true"
          >
            <Icon className="h-4 w-4" />
          </span>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {step !== undefined && (
              <span className="rounded-full bg-surface-3 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-foreground-muted">
                passo {step}
              </span>
            )}
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              {title}
            </h2>
          </div>
          {description && (
            <p className="mt-0.5 text-xs text-foreground-muted">{description}</p>
          )}
        </div>
      </header>
      <div className="space-y-4 p-5">{children}</div>
    </section>
  );
}

"use client";

import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { useModuloAtual } from "@/lib/modulo-atual";
import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface PageHeaderProps {
  /** Lista de breadcrumbs (não inclui o Home — já é adicionado automaticamente). */
  breadcrumbs?: BreadcrumbItem[];
  /** Título principal — grande e em peso bold. */
  title: React.ReactNode;
  /** Subtítulo curto explicando a página. */
  description?: React.ReactNode;
  /** Slot de ações no canto direito (ex: botão "Novo X"). */
  actions?: React.ReactNode;
  /** Ícone decorativo opcional ao lado do título. */
  icon?: React.ComponentType<{ className?: string }>;
  /** Barra de tabs/filtros logo abaixo do header. */
  tabs?: React.ReactNode;
  /** Variante visual: default (sólido) ou hero (gradient suave atrás do título). */
  variant?: "default" | "hero";
  className?: string;
}

/**
 * Header padrão de página. Garante identidade consistente em todas as
 * telas: breadcrumb minimalista, título tipográfico grande, slot de ações
 * alinhado à direita, e tabs/filtros opcionais embaixo.
 *
 * Variante "hero" adiciona um gradient suave atrás (navy → âmbar) — usar
 * em páginas-vitrine (dashboard, login).
 */
export function PageHeader({
  breadcrumbs,
  title,
  description,
  actions,
  icon: Icon,
  tabs,
  variant = "default",
  className,
}: PageHeaderProps) {
  const isHero = variant === "hero";
  const modulo = useModuloAtual();
  // Dentro de um módulo o SHELL já desenha "Menu principal › Meus módulos ›
  // Módulo" (`TrilhaDoModulo`). Daqui sai o que repetiria aquilo: a migalha
  // da raiz do módulo ("Frota Pública" → /m/frota) e o atalho de Início. E se
  // o que sobra é só o nome da própria tela, não sobra nada a mostrar — o
  // título logo abaixo já diz isso. Fica a trilha quando há um nível
  // intermediário de verdade (um link de volta para a lista, por exemplo).
  const raizes = modulo ? [modulo.raiz, `/m/${modulo.slug}`] : [];
  const migalhas = (breadcrumbs ?? []).filter((bc) => !bc.href || !raizes.includes(bc.href));
  const mostrarMigalhas = modulo ? migalhas.some((bc) => bc.href) : migalhas.length > 0;

  // document.title por rota (fatia 3.5): o PageHeader está em toda tela — é o
  // lugar natural do título da aba enquanto o PageShell (UX-04) não existe.
  React.useEffect(() => {
    if (typeof title === "string" && title) {
      document.title = `${title} — Aprimora`;
    }
  }, [title]);

  return (
    // <div>, não <header>: o shell já tem o banner; dois <header> aninhados
    // eram ruído de landmark para leitor de tela (fatia 3.5).
    <div
      className={cn(
        // O -mx/px espelha o padding do <main> — os dois vêm de --density-space
        // para o sangramento continuar alinhado em qualquer densidade (3.9).
        "relative -mx-4 mb-2 px-4 sm:-mx-[var(--density-space)] sm:px-[var(--density-space)]",
        isHero &&
          "border-b border-border bg-gradient-to-br from-brand/5 via-transparent to-accent/5",
        className,
      )}
    >
      {/* Breadcrumb */}
      {mostrarMigalhas && (
        <nav
          aria-label={modulo ? "Trilha da tela" : "Trilha"}
          className="mb-2 flex items-center gap-1 pt-2 text-xs text-foreground-muted"
        >
          {!modulo && (
            <Link
              href="/home"
              className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-muted hover:text-foreground transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              aria-label="Início"
            >
              <Home className="h-3 w-3" aria-hidden="true" />
            </Link>
          )}
          {migalhas.map((bc, i) => (
            <React.Fragment key={i}>
              {(i > 0 || !modulo) && (
                <ChevronRight
                  className="h-3 w-3 shrink-0 text-foreground-subtle"
                  aria-hidden="true"
                />
              )}
              {bc.href ? (
                <Link
                  href={bc.href}
                  className="rounded px-1 py-0.5 hover:bg-muted hover:text-foreground transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  {bc.label}
                </Link>
              ) : (
                <span className="px-1 py-0.5 text-foreground">{bc.label}</span>
              )}
            </React.Fragment>
          ))}
        </nav>
      )}

      {/* Title row */}
      <div className="flex flex-wrap items-start justify-between gap-3 py-[var(--density-gap)]">
        <div className="flex min-w-0 items-start gap-3">
          {Icon && (
            <div
              className={cn(
                "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
                isHero
                  ? "bg-brand-gradient text-white shadow-brand"
                  : "bg-brand/10 text-brand dark:bg-brand/20 dark:text-brand-light",
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
            </div>
          )}
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight text-titulo">
              {title}
            </h1>
            {description && (
              <p className="mt-1 max-w-2xl text-sm text-foreground-muted">
                {description}
              </p>
            )}
          </div>
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        )}
      </div>

      {/* Tabs/filtros */}
      {tabs && (
        <div className="-mx-4 sm:-mx-[var(--density-space)] border-b border-border bg-surface-1/40">
          <div className="px-4 sm:px-[var(--density-space)]">{tabs}</div>
        </div>
      )}
    </div>
  );
}

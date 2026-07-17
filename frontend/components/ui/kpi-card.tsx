"use client";

import { LucideIcon, Minus, TrendingDown, TrendingUp } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

type Intent = "default" | "success" | "warning" | "danger" | "info";

const INTENT_CLASSES: Record<
  Intent,
  { iconBg: string; iconColor: string; valueColor: string }
> = {
  default: {
    iconBg: "bg-brand/10 dark:bg-brand/20",
    iconColor: "text-brand dark:text-brand-light",
    valueColor: "text-foreground",
  },
  success: {
    iconBg: "bg-success/10",
    iconColor: "text-success-soft-foreground",
    valueColor: "text-foreground",
  },
  warning: {
    iconBg: "bg-warning/15",
    iconColor: "text-warning-soft-foreground",
    valueColor: "text-foreground",
  },
  danger: {
    iconBg: "bg-danger/10",
    iconColor: "text-danger-soft-foreground",
    valueColor: "text-foreground",
  },
  info: {
    iconBg: "bg-info-soft",
    iconColor: "text-info-soft-foreground",
    valueColor: "text-foreground",
  },
};

interface KpiCardProps {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  icon?: LucideIcon;
  intent?: Intent;
  /** Para tendência: valor atual e anterior, e flag se queda é boa. */
  current?: number | null;
  previous?: number | null;
  lowerIsBetter?: boolean;
  className?: string;
}

interface DeltaInfo {
  kind: "up" | "down" | "flat" | "n/a";
  pct: number | null;
}

function computeDelta(
  current: number | null | undefined,
  previous: number | null | undefined,
): DeltaInfo {
  if (current == null || previous == null) return { kind: "n/a", pct: null };
  const diff = current - previous;
  if (Math.abs(diff) < 1e-9) return { kind: "flat", pct: 0 };
  if (previous === 0)
    return { kind: current > 0 ? "up" : "down", pct: null };
  const pct = ((current - previous) / Math.abs(previous)) * 100;
  return { kind: current > previous ? "up" : "down", pct: Math.round(pct * 10) / 10 };
}

function TrendBadge({
  delta,
  lowerIsBetter,
}: {
  delta: DeltaInfo;
  lowerIsBetter: boolean;
}) {
  if (delta.kind === "n/a") return null;
  if (delta.kind === "flat") {
    return (
      <span className="inline-flex items-center gap-0.5 text-xs font-medium text-foreground-subtle">
        <Minus className="h-3 w-3" aria-hidden="true" />
        sem alteração
      </span>
    );
  }
  const isGood =
    (delta.kind === "up" && !lowerIsBetter) ||
    (delta.kind === "down" && lowerIsBetter);
  const color = isGood
    ? "text-success-soft-foreground bg-success-soft/60"
    : "text-danger-soft-foreground bg-danger-soft/60";
  const Icon = delta.kind === "up" ? TrendingUp : TrendingDown;
  const label =
    delta.pct != null
      ? `${delta.pct > 0 ? "+" : ""}${delta.pct.toFixed(1)}%`
      : "novo";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-badge px-1.5 py-0.5 text-xs font-semibold tabular-nums",
        color,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {label}
    </span>
  );
}

/**
 * Card de KPI premium pra dashboards. Diferenças vs antigo:
 * - Borda gradient sutil ao hover (brand→accent)
 * - Número grande em font-mono pra alinhamento entre cards
 * - Ícone num quadrado tinto identitário (mesmo do PageHeader)
 * - Trend badge em pill colorida com background sutil
 */
export function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  intent = "default",
  current,
  previous,
  lowerIsBetter = false,
  className,
}: KpiCardProps) {
  const i = INTENT_CLASSES[intent];
  const delta = computeDelta(current, previous);

  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-card border border-border bg-surface-1 p-4 shadow-card",
        "transition-all duration-base hover:-translate-y-0.5 hover:shadow-card-hover",
        "before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-gradient-to-r",
        "before:from-transparent before:via-brand/40 before:to-accent/40 before:opacity-0",
        "hover:before:opacity-100 before:transition-opacity before:duration-base",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-foreground-muted">
              {label}
            </span>
            <TrendBadge delta={delta} lowerIsBetter={lowerIsBetter} />
          </div>
          <div
            className={cn(
              "mt-2 text-[28px] font-bold leading-none tabular-nums tracking-tight",
              "font-mono", // alinha melhor entre cards
              i.valueColor,
            )}
          >
            {value}
          </div>
          {hint && (
            <div className="mt-2 text-xs text-foreground-subtle">{hint}</div>
          )}
        </div>
        {Icon && (
          <div
            className={cn(
              "flex h-10 w-10 shrink-0 items-center justify-center rounded-lg",
              i.iconBg,
            )}
          >
            <Icon className={cn("h-5 w-5", i.iconColor)} aria-hidden="true" />
          </div>
        )}
      </div>
    </div>
  );
}

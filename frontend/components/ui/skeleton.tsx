import { cn } from "@/lib/utils";

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Variante visual: pulse (default) ou shimmer. */
  variant?: "pulse" | "shimmer";
}

/**
 * Placeholder de carregamento. Use no lugar de "Carregando..." pra
 * percepção de velocidade. Shimmer dá um touch premium em telas mais
 * complexas (KPI cards do dashboard).
 */
export function Skeleton({ className, variant = "pulse", ...props }: SkeletonProps) {
  return (
    <div
      role="status"
      aria-label="Carregando"
      className={cn(
        "rounded-md bg-muted",
        variant === "pulse" && "animate-pulse-soft",
        variant === "shimmer" &&
          "relative overflow-hidden bg-gradient-to-r from-muted via-surface-2 to-muted bg-[length:200%_100%] animate-shimmer",
        className,
      )}
      {...props}
    />
  );
}

/** Skeleton de linha (com altura padrão pra body text). */
export function SkeletonLine({
  className,
  width = "100%",
}: {
  className?: string;
  width?: string;
}) {
  return <Skeleton className={cn("h-4", className)} style={{ width }} />;
}

/** Skeleton de card KPI (usado no dashboard durante load). */
export function SkeletonKpi() {
  return (
    <div className="space-y-2 rounded-lg border border-border bg-surface-1 p-4 sm:p-6">
      <SkeletonLine width="60%" className="h-3" />
      <Skeleton className="h-8 w-1/3" variant="shimmer" />
      <SkeletonLine width="40%" className="h-3" />
    </div>
  );
}

/** Skeleton de linha de tabela. */
export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  return (
    <tr className="border-b border-border">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-3 py-3">
          <SkeletonLine width={i === 0 ? "30%" : "70%"} />
        </td>
      ))}
    </tr>
  );
}

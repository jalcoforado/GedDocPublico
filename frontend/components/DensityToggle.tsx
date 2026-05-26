"use client";

import { Maximize2, Minimize2 } from "lucide-react";

import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function DensityToggle() {
  const { density, setDensity } = useTheme();
  const compact = density === "compact";

  return (
    <button
      type="button"
      onClick={() => setDensity(compact ? "comfortable" : "compact")}
      aria-label={compact ? "Modo confortável" : "Modo compacto"}
      title={compact ? "Modo confortável" : "Modo compacto"}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface-1 text-foreground-muted",
        "transition-colors duration-fast hover:bg-muted hover:text-foreground",
      )}
    >
      {compact ? (
        <Maximize2 className="h-4 w-4" aria-hidden="true" />
      ) : (
        <Minimize2 className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}

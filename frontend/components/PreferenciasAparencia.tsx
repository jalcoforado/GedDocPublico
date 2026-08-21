"use client";

import {
  Maximize2,
  Minimize2,
  Monitor,
  Moon,
  Sun,
} from "lucide-react";

import { useTheme, type Density, type ThemePreference } from "@/lib/theme";
import { cn } from "@/lib/utils";

const THEME_OPTS: Array<{
  value: ThemePreference;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { value: "system", label: "Sistema", icon: Monitor },
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
];

const DENSITY_OPTS: Array<{
  value: Density;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}> = [
  { value: "comfortable", label: "Confortável", icon: Maximize2 },
  { value: "compact", label: "Compacto", icon: Minimize2 },
];

function Radiogroup<T extends string>({
  label,
  opts,
  atual,
  onChange,
}: {
  label: string;
  opts: Array<{ value: T; label: string; icon: React.ComponentType<{ className?: string }> }>;
  atual: T;
  onChange: (v: T) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-foreground-subtle">
        {label}
      </div>
      <div
        role="radiogroup"
        aria-label={label}
        className="flex rounded-md border border-border bg-surface-1 p-0.5"
      >
        {opts.map((opt) => {
          const Icon = opt.icon;
          const active = atual === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(opt.value)}
              className={cn(
                "inline-flex h-8 flex-1 items-center justify-center gap-1 rounded text-xs font-medium transition-colors duration-fast",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "bg-brand text-primary-foreground shadow-sm"
                  : "text-foreground-muted hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="h-3 w-3" aria-hidden="true" />
              {opt.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Tema + densidade como radiogroups de verdade (UX-03 fatia 3.7) — a única
 * implementação, consumida pelo AvatarDropdown e pela superfície canônica em
 * /perfil. Antes eram `menuitemradio` fora de menu válido, que leitor de
 * tela não anuncia como opção selecionável.
 */
export function PreferenciasAparencia({ className }: { className?: string }) {
  const { preference, setPreference, density, setDensity } = useTheme();
  return (
    <div className={cn("space-y-3", className)}>
      <Radiogroup label="Tema" opts={THEME_OPTS} atual={preference} onChange={setPreference} />
      <Radiogroup label="Densidade" opts={DENSITY_OPTS} atual={density} onChange={setDensity} />
    </div>
  );
}

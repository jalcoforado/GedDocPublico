"use client";

import { Monitor, Moon, Sun } from "lucide-react";

import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/** Toggle 3-estados (sistema / claro / escuro) inline no Header. */
export function ThemeToggle() {
  const { preference, setPreference } = useTheme();

  const options = [
    { value: "system" as const, icon: Monitor, label: "Sistema" },
    { value: "light" as const, icon: Sun, label: "Claro" },
    { value: "dark" as const, icon: Moon, label: "Escuro" },
  ];

  return (
    <div
      role="group"
      aria-label="Tema"
      className="inline-flex rounded-md border border-border bg-surface-1 p-0.5"
    >
      {options.map((o) => {
        const Icon = o.icon;
        const active = preference === o.value;
        return (
          <button
            key={o.value}
            type="button"
            onClick={() => setPreference(o.value)}
            aria-label={`Tema: ${o.label}`}
            aria-pressed={active}
            title={o.label}
            className={cn(
              "inline-flex h-7 w-7 items-center justify-center rounded transition-colors duration-fast",
              active
                ? "bg-brand text-primary-foreground shadow-xs"
                : "text-foreground-muted hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        );
      })}
    </div>
  );
}

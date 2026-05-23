"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const TABS = [
  { href: "/relatorios", label: "Processos" },
  { href: "/relatorios/tramitacao", label: "Tramitação" },
  { href: "/relatorios/assinaturas", label: "Assinaturas" },
];

export function RelatoriosNav() {
  const pathname = usePathname();
  return (
    <div
      role="tablist"
      aria-label="Tipos de relatório"
      className="flex gap-1 border-b border-border"
    >
      {TABS.map((t) => {
        const active = pathname === t.href;
        return (
          <Link
            key={t.href}
            href={t.href}
            role="tab"
            aria-selected={active}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex h-11 items-center px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}

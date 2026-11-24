"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { canSeeItem, MENUS } from "@/lib/menus";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/m/pagamentos", label: "Visão geral" },
  { href: "/m/pagamentos/dashboard", label: "Indicadores" },
];

/**
 * Visão geral × Indicadores de Pagamentos. No menu por área (2026-11-14) o
 * antigo "Dashboard" deixou de ser item da barra — eram duas entradas para a
 * mesma pergunta ("como está o financeiro?") — e virou esta aba da Visão
 * geral.
 *
 * Links para outra rota, não abas de verdade: `<nav>` com `aria-current`,
 * como o `RelatoriosNav` (ver o porquê lá). Cada link só aparece para quem
 * pode ver a tela — a mesma regra do menu.
 */
export function NavVisaoFinanceiro() {
  const pathname = usePathname();
  const { can } = useAuth();
  const itens = MENUS.pagamentos.grupos.flatMap((g) => g.items);
  const visiveis = LINKS.filter((l) => {
    const item = itens.find((i) => i.href === l.href);
    return !item || canSeeItem(item, can);
  });
  if (visiveis.length < 2) return null;
  return (
    <nav aria-label="Visão do financeiro" className="border-b border-border">
      <ul className="flex gap-1">
        {visiveis.map((l) => {
          const ativo = pathname === l.href;
          return (
            <li key={l.href}>
              <Link
                href={l.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "flex h-11 items-center px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  ativo
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {l.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

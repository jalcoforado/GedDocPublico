"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import { MENUS, canSeeItem } from "@/lib/menus";
import { cn } from "@/lib/utils";

const RAIZ = "/m/pagamentos/solicitacoes";

/**
 * As etapas de Solicitações como abas — "Todas", "Aguardando Gestor",
 * "Aguardando Validação", "Aguardando Autoridade", "Concluídas". Eram quatro
 * itens do menu lateral para recortes da mesma lista (o mesmo caso das caixas
 * do Protocolo, ver `AbasCaixas`).
 *
 * Geradas do menu (`lib/menus/pagamentos.ts`): "Solicitações" e os itens com
 * `lugar: "aba"`, podados pela mesma `canSeeItem` — quem não é gestor não vê
 * a aba do gestor, como não via o item. Cada aba é uma tela (rota própria),
 * então é `<nav>` com links e `aria-current`, não `role="tab"`.
 */
export function AbasSolicitacoes() {
  const pathname = usePathname();
  const { can } = useAuth();
  const itens = MENUS.pagamentos.grupos
    .flatMap((g) => g.items)
    .filter((i) => (i.href === RAIZ || (i.lugar === "aba" && i.href.startsWith(`${RAIZ}/`))) && canSeeItem(i, can));
  if (itens.length <= 1) return null;

  return (
    <nav aria-label="Etapas das solicitações" className="border-b border-border">
      <ul className="-mb-px flex gap-0.5 overflow-x-auto">
        {itens.map((i) => {
          const ativo = pathname === i.href;
          const Icone = i.icon;
          return (
            <li key={i.href} className="shrink-0">
              <Link
                href={i.href}
                aria-current={ativo ? "page" : undefined}
                className={cn(
                  "flex h-10 items-center gap-1.5 whitespace-nowrap rounded-t-md border-b-2 px-3 text-sm font-medium transition-colors duration-fast",
                  ativo
                    ? "border-primary text-primary"
                    : "border-transparent text-foreground-muted hover:border-border-strong hover:bg-muted hover:text-foreground",
                )}
              >
                <Icone className="h-4 w-4 shrink-0" aria-hidden="true" />
                {i.href === RAIZ ? "Todas" : i.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

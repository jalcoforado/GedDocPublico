import { BarChart3, Home, PenSquare } from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Itens transversais — não pertencem a nenhum módulo contratável, aparecem
 * sempre. Início e Dashboard vieram do grupo "Geral" da Sidebar (linha 71);
 * Organograma saiu daqui e foi para `administracao.ts` (§12: estrutura
 * organizacional é matéria de administração). "Para assinar" veio do grupo
 * "Processos" (linha 84): o apêndice §12 do spec trata assinatura como
 * transversal — `moduloDoPathname("/para-assinar")` é `null`.
 */
export const menuComum: MenuModulo = {
  slug: "comum",
  raiz: "/home",
  grupos: [
    {
      title: "Geral",
      defaultOpen: true,
      items: [
        { label: "Início", href: "/home", icon: Home },
        { label: "Dashboard", href: "/dashboard", icon: BarChart3 },
        { label: "Para assinar", href: "/para-assinar", icon: PenSquare },
      ],
    },
  ],
};

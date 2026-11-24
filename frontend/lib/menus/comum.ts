import { FolderTree, Home } from "lucide-react";

import type { MenuModulo } from "./tipos";

/**
 * Itens transversais — não pertencem a nenhum módulo contratável, aparecem
 * sempre. Início vem do grupo "Geral" da Sidebar (linha 71); Organograma
 * saiu daqui e foi para `administracao.ts` (§12: estrutura organizacional é
 * matéria de administração).
 *
 * Dashboard e "Para assinar" removidos do menu por pedido explícito
 * (2026-08-07) — as rotas /dashboard e /para-assinar continuam existindo
 * (alcançáveis por URL direta e pelo breadcrumb/ícone de home em
 * PageHeader), só saíram da navegação lateral.
 *
 * "Cadastros e configuração" (`/cadastros`, menu por área de 2026-11-14)
 * junta os índices de todos os módulos. Fica `lugar: "hub"` aqui para o
 * Ctrl+K achá-lo; quem o põe na barra, perto da Administração, é
 * `navPorArea` (`lib/menus/areas.ts`).
 */
export const menuComum: MenuModulo = {
  slug: "comum",
  raiz: "/home",
  grupos: [
    {
      title: "Geral",
      semTitulo: true,
      defaultOpen: true,
      items: [
        { label: "Início", href: "/home", icon: Home },
        { label: "Cadastros e configuração", href: "/cadastros", icon: FolderTree, lugar: "hub" },
      ],
    },
  ],
};

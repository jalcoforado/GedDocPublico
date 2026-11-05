/** Tipos do menu. Vieram de components/Sidebar.tsx, sem alteração de forma. */
import type React from "react";

export interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  perm?: string;
  anyOf?: string[];
  /** Subitens — vira um subgrupo colapsável (chevron) dentro do grupo pai. */
  children?: NavItem[];
}

export interface NavGroup {
  title: string;
  items: NavItem[];
  /** Estado inicial do grupo (antes da hidratação do localStorage). */
  defaultOpen?: boolean;
}

export interface MenuModulo {
  slug: string;
  /** Onde o launcher e o switcher entram. Nesta fatia é a URL ANTIGA. */
  raiz: string;
  grupos: NavGroup[];
}

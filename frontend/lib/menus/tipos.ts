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

/**
 * A ação principal do módulo — o botão no alto do menu lateral, acima dos
 * grupos ("Abrir processo" no protocolo). Uma por módulo, e só quando há uma
 * ação que é o motivo de a pessoa entrar ali. Aparece para quem tem
 * `perm` + `action` (criar exige `inserir`, não só ler).
 */
export interface AcaoPrincipal {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  perm: string;
  action?: "inserir" | "atualizar" | "excluir";
}

export interface MenuModulo {
  slug: string;
  /** Onde o launcher e o switcher entram. Nesta fatia é a URL ANTIGA. */
  raiz: string;
  acaoPrincipal?: AcaoPrincipal;
  grupos: NavGroup[];
}

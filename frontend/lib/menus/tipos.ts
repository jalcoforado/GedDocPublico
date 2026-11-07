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
  /**
   * Onde a tela mora na navegação (desde 2026-11-05, menu único):
   * - `"barra"` (padrão): no menu lateral — as telas de trabalho do dia;
   * - `"hub"`: na tela-índice do módulo (cadastros, configuração, referência),
   *   alcançável por ela e pelo Ctrl+K, fora da barra;
   * - `"aba"`: é aba de outra tela (as etapas de Solicitações), só Ctrl+K.
   * O item continua declarado aqui em todos os casos: Ctrl+K, as guardas de
   * rota e a tabela de permissões leem esta lista inteira.
   */
  lugar?: "barra" | "hub" | "aba";
}

export interface NavGroup {
  title: string;
  items: NavItem[];
  /** Estado inicial do grupo (antes da hidratação do localStorage). */
  defaultOpen?: boolean;
  /** Sem cabeçalho no menu (o "Início" no topo). */
  semTitulo?: boolean;
  /** Destaque baixo: separado por uma linha, no fim (Administração). */
  quieto?: boolean;
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

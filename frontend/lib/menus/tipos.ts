/** Tipos do menu. Vieram de components/Sidebar.tsx, sem alteração de forma. */
import type React from "react";

import type { CaixaProcesso } from "@/lib/api";

export interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  perm?: string;
  anyOf?: string[];
  /** Subitens — vira um subgrupo colapsável (chevron) dentro do grupo pai. */
  children?: NavItem[];
  /**
   * Parâmetro de busca que distingue este item de irmãos com o MESMO caminho
   * (as caixas de Processos são todas `/m/protocolo/processos`, cada uma com
   * o seu `?caixa=`). O `href` já carrega a query; este campo existe para o
   * menu saber qual deles está aberto. Irmão sem `filtro` é "o resto": fica
   * ativo quando nenhum filtro casa.
   */
  filtro?: { chave: string; valor: string };
  /** Caixa cujo contador aparece ao lado do rótulo. */
  contador?: CaixaProcesso;
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

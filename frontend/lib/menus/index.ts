import { menuAdministracao } from "./administracao";
import { menuComum } from "./comum";
import { menuFrota } from "./frota";
import { menuPagamentos } from "./pagamentos";
import { menuProtocolo } from "./protocolo";
import { menuTransporte } from "./transporte";
import type { MenuModulo } from "./tipos";

export type { MenuModulo, NavGroup, NavItem } from "./tipos";

/** slug do catálogo (aprimora_py.modulo.slug) → menu. */
export const MENUS: Record<string, MenuModulo> = {
  protocolo: menuProtocolo,
  pagamentos: menuPagamentos,
  frota: menuFrota,
  transporte: menuTransporte,
  administracao: menuAdministracao,
  comum: menuComum,
};

export function menuDoModulo(slug: string | null): MenuModulo | null {
  if (!slug) return null;
  return MENUS[slug] ?? null;
}

/**
 * Ordem dos grupos no NAV monolítico original (Sidebar.tsx antes do split):
 * "Geral" vinha primeiro, depois Processos/Protocolo/Cadastros, Frota,
 * Transporte Regulado, Pagamentos e por fim Administração.
 *
 * A ponte temporária da Task 1 em `components/Sidebar.tsx` usava esta ordem
 * para remontar o NAV inteiro; saiu na Task 3, quando a Sidebar passou a
 * renderizar só `menuDoModulo(modulo) + MENUS.comum`. A constante continua
 * viva só como fonte de verdade do `__tests__/menus.test.tsx` ("a ponte
 * temporária reproduz a ordem original do NAV") — guarda de regressão para
 * não perder essa ordem de vista caso ela volte a importar (ex.: um launcher
 * futuro que liste todos os módulos de uma vez).
 */
export const ORDEM_GRUPOS_ORIGINAL: readonly string[] = [
  "comum",
  "protocolo",
  "frota",
  "transporte",
  "pagamentos",
  "administracao",
];

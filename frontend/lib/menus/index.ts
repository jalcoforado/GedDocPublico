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
 * A ponte temporária da Task 1 em `components/Sidebar.tsx` usa esta ordem —
 * `Object.values(MENUS)` NÃO é confiável para isso porque depende da ordem
 * dos literais do objeto, que não é o mesmo contrato que "ordem visível pro
 * usuário". Sai junto com a ponte, na Task 3.
 */
export const ORDEM_GRUPOS_ORIGINAL: readonly string[] = [
  "comum",
  "protocolo",
  "frota",
  "transporte",
  "pagamentos",
  "administracao",
];

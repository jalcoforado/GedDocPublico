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

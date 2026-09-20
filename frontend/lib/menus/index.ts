import { menuAdministracao } from "./administracao";
import { menuComum } from "./comum";
import { menuFrota } from "./frota";
import { menuPagamentos } from "./pagamentos";
import { canSeeItem } from "./permissoes";
import { menuProtocolo } from "./protocolo";
import { menuTransporte } from "./transporte";
import type { MenuModulo, NavItem } from "./tipos";

export type { MenuModulo, NavGroup, NavItem } from "./tipos";
export { canSeeItem } from "./permissoes";

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

export interface ItemComModulo {
  item: NavItem;
  /** slug do módulo dono (`MenuModulo.slug`) — "comum" para transversal. */
  moduloSlug: string;
}

/**
 * Achata a árvore de TODOS os menus em itens-folha navegáveis, cada um
 * marcado com o slug do módulo dono. Um item com `children` não entra por si
 * só — na Sidebar ele é só um acordeão (`toggleSub`), quem navega são os
 * filhos; listar o pai também duplicaria o href do primeiro filho.
 *
 * Fonte para o CommandPalette montar a lista a partir de `lib/menus` em vez
 * de manter uma cópia estática própria (a divergência que motivou esta
 * função existir).
 */
export function itensNavegaveis(): ItemComModulo[] {
  function folhas(items: NavItem[]): NavItem[] {
    return items.flatMap((i) => (i.children && i.children.length > 0 ? folhas(i.children) : [i]));
  }
  return Object.values(MENUS).flatMap((menu) =>
    folhas(menu.grupos.flatMap((g) => g.items)).map((item) => ({ item, moduloSlug: menu.slug })),
  );
}

/**
 * Para onde o launcher/switcher deve mandar o usuário ao entrar num módulo:
 * o primeiro item navegável, na ordem declarada de grupos/itens, que ELE
 * pode ver — não `MENUS[slug].raiz` fixo (achado do review da F2, item
 * 1.0.9: a raiz fixa podia ser uma tela fora do menu daquele usuário, sem
 * dar 403 porque leitura não é gateada por permissão, só incoerente).
 * Cai em `raiz` só se o módulo não tiver nenhum item visível — módulo
 * contratado sem nenhuma permissão concedida ainda —, para nunca deixar de
 * navegar.
 */
export function primeiraRotaVisivel(slug: string, can: (perm: string) => boolean): string {
  const menu = MENUS[slug];
  if (!menu) return "/home";
  const primeiro = itensNavegaveis().find(
    (x) => x.moduloSlug === slug && canSeeItem(x.item, can),
  );
  return primeiro?.item.href ?? menu.raiz;
}

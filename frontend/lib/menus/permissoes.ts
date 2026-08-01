import type { NavItem } from "./tipos";

/**
 * Poda por permissão de um item de menu. Fonte ÚNICA — Sidebar e
 * CommandPalette consomem esta função em vez de reimplementá-la. Duas cópias
 * divergem, e o sintoma é o item aparecer num lugar e sumir no outro (o que
 * esta extração existe para evitar).
 *
 * Independente do filtro de módulo: aqui só decide quem PODE ver, dado que o
 * item já é candidato (módulo contratado). Um item sem `perm`/`anyOf` é
 * sempre visível a quem já passou pelo filtro de módulo.
 */
export function canSeeItem(item: NavItem, can: (perm: string) => boolean): boolean {
  return (
    (!item.perm && !item.anyOf) ||
    (!!item.perm && can(item.perm)) ||
    (!!item.anyOf && item.anyOf.some((p) => can(p)))
  );
}

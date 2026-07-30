/**
 * Guarda do split do menu. O NAV tinha 637 linhas num arquivo; o risco do split
 * não é escrever errado, é PERDER item no caminho — e item perdido não quebra
 * teste nenhum, só desaparece da tela de alguém.
 */
import { describe, expect, it } from "vitest";

import { MENUS, menuDoModulo } from "@/lib/menus";
import type { NavItem } from "@/lib/menus/tipos";
import { moduloDoPathname } from "@/lib/modulos";

/** Todos os hrefs de um menu, incluindo os de subitens. */
function hrefs(items: NavItem[]): string[] {
  return items.flatMap((i) => [i.href, ...(i.children ? hrefs(i.children) : [])]);
}

const TODOS = Object.values(MENUS).flatMap((m) => hrefs(m.grupos.flatMap((g) => g.items)));

describe("split dos menus", () => {
  it("não está vazio", () => {
    // Sem isto, todas as asserções abaixo passam vacuamente.
    expect(TODOS.length).toBeGreaterThan(40);
    expect(Object.keys(MENUS).sort()).toEqual([
      "administracao", "comum", "frota", "pagamentos", "protocolo", "transporte",
    ]);
  });

  it("nenhum href aparece em dois módulos", () => {
    const vistos = new Map<string, string>();
    const duplicados: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const antes = vistos.get(href);
        if (antes && antes !== slug) duplicados.push(`${href}: ${antes} e ${slug}`);
        vistos.set(href, slug);
      }
    }
    expect(duplicados).toEqual([]);
  });

  it("cada item está no módulo que o mapa de pathname aponta", () => {
    // Se um item foi para o arquivo errado, o menu do módulo A mostra tela do
    // módulo B — e na F3 o redirect vai jogar o usuário para fora do menu em
    // que ele acabou de clicar.
    const divergentes: string[] = [];
    for (const [slug, menu] of Object.entries(MENUS)) {
      if (slug === "comum") continue; // transversais não têm módulo
      for (const href of hrefs(menu.grupos.flatMap((g) => g.items))) {
        const derivado = moduloDoPathname(href);
        if (derivado !== slug) divergentes.push(`${href}: arquivo=${slug} mapa=${derivado}`);
      }
    }
    expect(divergentes).toEqual([]);
  });

  it("todo módulo tem raiz navegável e ela pertence ao próprio módulo", () => {
    for (const [slug, menu] of Object.entries(MENUS)) {
      expect(menu.raiz, `${slug} sem raiz`).toMatch(/^\//);
      if (slug !== "comum") expect(moduloDoPathname(menu.raiz)).toBe(slug);
    }
  });

  it("menuDoModulo devolve null para slug desconhecido", () => {
    expect(menuDoModulo("nao-existe")).toBeNull();
  });
});

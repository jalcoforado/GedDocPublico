/**
 * O hub é a porta do módulo. Card entregue e não ligado — ou ligado e marcado
 * como não-pronto — é exatamente como Alvarás e Relatórios ficaram invisíveis
 * por quatro fases, com backend, tela e testes todos verdes.
 */
import { describe, expect, it } from "vitest";

import { menuDoModulo } from "@/lib/menus";
import type { NavItem } from "@/lib/menus/tipos";
import { moduloDoPathname } from "@/lib/modulos";
import { CARDS } from "@/lib/transporte-hub";

function hrefs(items: NavItem[]): string[] {
  return items.flatMap((i) => [i.href, ...(i.children ? hrefs(i.children) : [])]);
}

describe("hub do transporte regulado", () => {
  it("todo card pronto tem href", () => {
    expect(CARDS.filter((c) => c.ready && !c.href).map((c) => c.title)).toEqual([]);
  });

  it("nenhum card com href fica escondido como não-pronto", () => {
    expect(CARDS.filter((c) => c.href && !c.ready).map((c) => c.title)).toEqual([]);
  });

  it("todo card pronto aponta para rota do próprio módulo", () => {
    const fora = CARDS.filter((c) => c.ready && c.href)
      .filter((c) => moduloDoPathname(c.href!) !== "transporte")
      .map((c) => c.title);
    expect(fora).toEqual([]);
  });

  it("todo card pronto está no menu do módulo", () => {
    // Hub e menu são duas listas da mesma navegação. Divergir significa que a
    // tela existe num lugar e some no outro — o sintoma é o usuário achar por
    // um caminho e não achar pelo outro.
    const menu = menuDoModulo("transporte");
    expect(menu).not.toBeNull();
    const doMenu = new Set(hrefs(menu!.grupos.flatMap((g) => g.items)));
    const foraDoMenu = CARDS.filter((c) => c.ready && c.href)
      .filter((c) => !doMenu.has(c.href!))
      .map((c) => c.title);
    expect(foraDoMenu).toEqual([]);
  });

  it("os dois cards não entregues seguem sem href", () => {
    // Card tracejado é honesto; card tracejado sobre tela pronta, não.
    // Recadastramento saiu desta lista na P5.1 e Pontos e Vagas na P6, quando
    // cada tela passou a existir.
    //
    // "Rotas e Linhas" virou "Linhas e Itinerários" na P6: ao escopar a fatia
    // ficou claro que táxi e mototáxi não têm linha, têm ponto — e que uma
    // entidade genérica serviria mal aos dois. O ponto foi entregue; linha
    // distrital/escolar também foi entregue na P6b — só Ocorrências fica.
    const semHref = CARDS.filter((c) => !c.ready).map((c) => c.title);
    expect(semHref).toEqual(["Ocorrências"]);
  });
});

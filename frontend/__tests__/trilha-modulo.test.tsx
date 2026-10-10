/**
 * Trilha do topo das telas de módulo — "Menu principal › Meus módulos ›
 * Módulo", do layout de referência.
 *
 * Dois modos de falha que importam: a migalha do módulo aparecer DUAS vezes
 * (as telas da frota já declaravam "Frota Pública → /m/frota" por conta
 * própria), e a trilha sumir das telas transversais que tinham a sua.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PageHeader } from "@/components/ui/page-header";
import { ModuloAtualProvider } from "@/lib/modulo-atual";
import { NOME_MODULO, SLUGS_MODULO, nomeDoModulo } from "@/lib/modulos";

const FROTA = { slug: "frota", nome: "Frota", raiz: "/m/frota" };

function links() {
  return within(screen.getByRole("navigation", { name: "Trilha" }))
    .getAllByRole("link")
    .map((a) => [a.textContent, a.getAttribute("href")]);
}

describe("trilha do módulo", () => {
  it("dentro de um módulo: Menu principal › Meus módulos › Módulo", () => {
    render(
      <ModuloAtualProvider value={FROTA}>
        <PageHeader title="Veículos" />
      </ModuloAtualProvider>,
    );
    expect(links()).toEqual([
      ["Menu principal", "/home"],
      ["Meus módulos", "/modulos"],
      ["Frota", "/m/frota"],
    ]);
  });

  it("a migalha que a página declarava para a raiz do módulo não se repete", () => {
    render(
      <ModuloAtualProvider value={FROTA}>
        <PageHeader
          title="Motoristas"
          breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Motoristas" }]}
        />
      </ModuloAtualProvider>,
    );
    const trilha = screen.getByRole("navigation", { name: "Trilha" });
    expect(links().filter(([, href]) => href === "/m/frota")).toHaveLength(1);
    expect(within(trilha).queryByText("Frota Pública")).toBeNull();
    // A migalha própria da página continua, no fim.
    expect(within(trilha).getByText("Motoristas")).toBeTruthy();
  });

  it("tela transversal com migalhas mantém a trilha que já tinha", () => {
    render(<PageHeader title="Notificações" breadcrumbs={[{ label: "Perfil", href: "/perfil" }]} />);
    const hrefs = links().map(([, href]) => href);
    expect(hrefs).toEqual(["/home", "/perfil"]);
    expect(screen.queryByText("Meus módulos")).toBeNull();
  });

  it("tela transversal sem migalhas não ganha trilha", () => {
    render(<PageHeader title="Meu perfil" />);
    expect(screen.queryByRole("navigation", { name: "Trilha" })).toBeNull();
  });
});

describe("nome dos módulos", () => {
  it("todo módulo com rota tem nome de exibição — senão a trilha mostra o slug", () => {
    for (const slug of SLUGS_MODULO) {
      expect(NOME_MODULO[slug], slug).toBeTruthy();
    }
  });

  it("slug desconhecido volta como veio, em vez de sumir", () => {
    expect(nomeDoModulo("modulo-novo")).toBe("modulo-novo");
  });
});

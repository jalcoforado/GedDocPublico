/**
 * Trilha do topo das telas de módulo — "Menu principal › Meus módulos ›
 * Módulo", do layout de referência.
 *
 * A trilha mora no SHELL. A primeira versão ficava no `PageHeader`, e uma em
 * cada três telas de módulo (Usuários, Grupos, Relatórios…) desenha o próprio
 * título sem ele: nessas a trilha não aparecia, e nenhum teste via, porque os
 * testes só exercitavam telas COM `PageHeader`.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrilhaDoModulo } from "@/components/TrilhaDoModulo";
import { PageHeader } from "@/components/ui/page-header";
import { MENUS } from "@/lib/menus";
import { ModuloAtualProvider } from "@/lib/modulo-atual";
import { NOME_MODULO, SLUGS_MODULO, nomeDoModulo } from "@/lib/modulos";

const FROTA = { slug: "frota", nome: "Frota", raiz: "/m/frota" };

const links = (nav: HTMLElement) =>
  within(nav)
    .getAllByRole("link")
    .map((a) => [a.textContent, a.getAttribute("href")]);

describe("trilha do módulo (shell)", () => {
  it("Menu principal › Meus módulos › Módulo, cada parte um link", () => {
    render(<TrilhaDoModulo modulo={FROTA} />);
    expect(links(screen.getByRole("navigation", { name: "Trilha" }))).toEqual([
      ["Menu principal", "/home"],
      ["Meus módulos", "/modulos"],
      ["Frota", "/m/frota"],
    ]);
  });

  it("não depende de a tela usar PageHeader — vale para tela com <h1> próprio", () => {
    render(
      <ModuloAtualProvider value={FROTA}>
        <TrilhaDoModulo modulo={FROTA} />
        <h1>Usuários</h1>
      </ModuloAtualProvider>,
    );
    expect(screen.getByRole("navigation", { name: "Trilha" })).toBeTruthy();
  });
});

describe("PageHeader dentro de um módulo", () => {
  function renderEmFrota(ui: React.ReactNode) {
    return render(<ModuloAtualProvider value={FROTA}>{ui}</ModuloAtualProvider>);
  }

  it("não desenha uma segunda trilha de módulo — isso é do shell", () => {
    renderEmFrota(<PageHeader title="Veículos" />);
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByText("Meus módulos")).toBeNull();
  });

  it("some a migalha que só repetiria o módulo e o nome da própria tela", () => {
    renderEmFrota(
      <PageHeader
        title="Motoristas"
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Motoristas" }]}
      />,
    );
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.queryByText("Frota Pública")).toBeNull();
  });

  it("mantém o nível intermediário de verdade — o link de volta para a lista", () => {
    renderEmFrota(
      <PageHeader
        title="Solicitação 12"
        breadcrumbs={[
          { label: "Frota Pública", href: "/m/frota" },
          { label: "Solicitações", href: "/m/frota/solicitacoes" },
          { label: "Solicitação 12" },
        ]}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Trilha da tela" });
    expect(links(nav)).toEqual([["Solicitações", "/m/frota/solicitacoes"]]);
    // Sem o atalho de Início: ele já está na trilha do shell.
    expect(within(nav).queryByRole("link", { name: "Início" })).toBeNull();
  });
});

describe("PageHeader fora de módulo (telas transversais)", () => {
  it("com migalhas mantém a trilha que já tinha, com o atalho de Início", () => {
    render(<PageHeader title="Notificações" breadcrumbs={[{ label: "Perfil", href: "/perfil" }]} />);
    const nav = screen.getByRole("navigation", { name: "Trilha" });
    expect(links(nav).map(([, href]) => href)).toEqual(["/home", "/perfil"]);
  });

  it("sem migalhas não ganha trilha", () => {
    render(<PageHeader title="Meu perfil" />);
    expect(screen.queryByRole("navigation")).toBeNull();
  });
});

describe("nome e raiz dos módulos", () => {
  it("todo módulo com rota tem nome de exibição — senão a trilha mostra o slug", () => {
    for (const slug of SLUGS_MODULO) expect(NOME_MODULO[slug], slug).toBeTruthy();
  });

  it("todo módulo com rota tem menu, de onde sai o destino do último item da trilha", () => {
    for (const slug of SLUGS_MODULO) expect(MENUS[slug]?.raiz, slug).toMatch(/^\/m\//);
  });

  it("slug desconhecido volta como veio, em vez de sumir", () => {
    expect(nomeDoModulo("modulo-novo")).toBe("modulo-novo");
  });
});

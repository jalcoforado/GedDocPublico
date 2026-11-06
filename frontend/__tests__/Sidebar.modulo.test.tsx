/**
 * Menu único (2026-11-05, no modelo do IAnalisys): a Sidebar mostra TODOS os
 * módulos contratados, em toda tela, cada um como uma seção com as telas de
 * trabalho dele. Substitui o modelo anterior — só o módulo da URL, mais um
 * cabeçalho para trocar de módulo e o launcher `/modulos`.
 *
 * O que este teste protege: módulo não contratado não aparece (mesmo com
 * permissão); cadastros e etapas (`lugar` "hub"/"aba") ficam fora da barra;
 * Administração vem por último e fechada; e uma falha de `/modulos/me` não
 * esvazia o menu.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const onde = { pathname: "/m/frota/veiculos" };
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => onde.pathname,
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: true },
    perms: [],
    loading: false,
    can: () => true,
    logout: vi.fn(),
  }),
}));

const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () => modulosMock(),
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

const m = (slug: string, nome: string, ordem: number) => ({ slug, nome, icone: null, ordem });
const TODOS = {
  itens: [
    m("protocolo", "Protocolo", 1),
    m("pagamentos", "Pagamentos", 2),
    m("frota", "Frota", 3),
    m("administracao", "Administração", 0), // ordem baixa de propósito: mesmo assim vai pro fim
    m("transporte", "Transporte Regulado", 4),
  ],
};

beforeEach(() => {
  onde.pathname = "/m/frota/veiculos";
  modulosMock.mockReset();
  modulosMock.mockResolvedValue(TODOS);
  window.localStorage.clear();
});

function renderSidebar(props: ComponentProps<typeof Sidebar>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <Sidebar {...props} />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("menu único", () => {
  it("todos os módulos contratados aparecem, em qualquer tela — não só o da URL", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    expect(await screen.findByRole("link", { name: "Caixas de trabalho" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Conciliação" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Veículos" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Alvarás" })).toBeInTheDocument();
  });

  it("no Início (sem módulo na URL) o menu é o mesmo", async () => {
    onde.pathname = "/home";
    renderSidebar({ modulo: null, open: true, onClose: () => {} });
    expect(await screen.findByRole("link", { name: "Caixas de trabalho" })).toBeInTheDocument();
    // Dois links "Início": a marca do município e o item do menu.
    expect(screen.getAllByRole("link", { name: "Início" }).some((a) => a.getAttribute("aria-current") === "page")).toBe(true);
  });

  it("módulo não contratado não aparece, mesmo com permissão para tudo", async () => {
    modulosMock.mockResolvedValue({ itens: [m("frota", "Frota", 1)] });
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Veículos" });
    expect(screen.queryByRole("link", { name: "Caixas de trabalho" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Conciliação" })).toBeNull();
  });

  it("cadastros e etapas ficam fora da barra; a tela-índice do módulo entra no lugar", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Caixas de trabalho" });
    for (const fora of ["Manifestantes", "Assuntos", "CCD (Classificação)", "Aguardando Gestor", "Fornecedores", "Motoristas", "Empresas"]) {
      expect(screen.queryByRole("link", { name: fora }), fora).toBeNull();
    }
    expect(screen.getByRole("link", { name: "Cadastros e configuração" })).toHaveAttribute("href", "/m/protocolo/cadastros");
    expect(screen.getByRole("link", { name: "Cadastros e controle" })).toHaveAttribute("href", "/m/pagamentos/cadastros");
  });

  it("seções na ordem do catálogo, Administração por último e fechada", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Caixas de trabalho" });
    const botoes = screen
      .getAllByRole("button")
      .filter((b) => b.hasAttribute("aria-expanded") && /^(Protocolo|Pagamentos|Frota|Transporte Regulado|Administração)$/.test(b.textContent?.trim() ?? ""));
    expect(botoes.map((b) => b.textContent?.trim())).toEqual([
      "Protocolo",
      "Pagamentos",
      "Frota",
      "Transporte Regulado",
      "Administração",
    ]);
    const adm = botoes[botoes.length - 1];
    expect(adm.getAttribute("aria-expanded")).toBe("false");
    for (const b of botoes.slice(0, -1)) expect(b.getAttribute("aria-expanded")).toBe("true");
  });

  it("dentro da Administração, ela abre sozinha (o item atual nunca fica escondido)", async () => {
    onde.pathname = "/m/administracao/usuarios";
    renderSidebar({ modulo: "administracao", open: true, onClose: () => {} });
    const usuarios = await screen.findByRole("link", { name: "Usuários" });
    await waitFor(() => expect(usuarios.closest("[id^='nav-group-']")?.className).not.toMatch(/\bhidden\b/));
  });

  it("o cabeçalho de troca de módulo saiu — a barra já é a troca", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Veículos" });
    expect(screen.queryByTestId("sidebar-modulo-header")).toBeNull();
    expect(screen.queryByRole("link", { name: /Meus módulos/ })).toBeNull();
  });

  it("se /modulos/me falhar, fica ao menos o módulo da URL — o menu não esvazia", async () => {
    modulosMock.mockRejectedValue(new Error("fora do ar"));
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: "Navegação principal" });
    expect(await within(nav).findByRole("link", { name: "Veículos" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Caixas de trabalho" })).toBeNull();
  });
});

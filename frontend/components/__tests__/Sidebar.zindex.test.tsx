/**
 * Regressão do drawer mobile: o overlay da Sidebar já esteve empatado com o
 * Header (a ordem do DOM decidia, e o Header ficava clicável por cima do
 * drawer aberto). O contrato é de camadas: overlay estritamente acima do
 * Header, painel estritamente acima do overlay. jsdom não calcula stacking
 * real, então o teste resolve as classes de camada pelos tokens `--z-*`.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/m/frota/veiculos",
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
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () =>
      Promise.resolve({
        itens: [{ slug: "frota", nome: "Frota", icone: "Truck", ordem: 1 }],
      }),
  },
}));

import { resolveZ, tokensZ } from "../../__tests__/_camadas";

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

// jsdom não implementa matchMedia; o ThemeProvider consulta a preferência do
// SO ao montar. Sem isso a montagem quebra antes de qualquer asserção.
window.matchMedia =
  window.matchMedia ??
  (((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia);

function renderSidebar(props: ComponentProps<typeof Sidebar>) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <Sidebar {...props} />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

/** Resolve a camada do elemento pela escala `--z-*` (fonte: globals.css). */
function zIndexDe(el: Element): number {
  return resolveZ(el.getAttribute("class") ?? "");
}

// O Header usa `z-sticky`; o contrato compara pela escala, então mudar o VALOR
// do token não quebra o teste — mudar a ORDEM das camadas quebra, que é o ponto.
const Z_HEADER = tokensZ().sticky;

describe("camadas do drawer mobile da Sidebar", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("com o drawer aberto, o overlay fica estritamente acima do Header", () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const overlay = screen.getByTestId("sidebar-overlay");
    expect(zIndexDe(overlay)).toBeGreaterThan(Z_HEADER);
  });

  it("o painel do drawer fica estritamente acima do overlay", () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const overlay = screen.getByTestId("sidebar-overlay");
    const painel = screen.getByRole("navigation", { name: "Navegação principal" });
    expect(zIndexDe(painel)).toBeGreaterThan(zIndexDe(overlay));
  });
});

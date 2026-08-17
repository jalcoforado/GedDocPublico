/**
 * Regressão do drawer mobile: o Header é `sticky top-0 z-30`, e o overlay da
 * Sidebar já esteve em `z-30` (empate — a ordem do DOM decidia e o Header
 * ficava clicável por cima do drawer aberto). O contrato aqui é de camadas:
 * overlay estritamente acima do Header (z-30), painel estritamente acima do
 * overlay. jsdom não calcula stacking real, então o teste valida as classes
 * utilitárias `z-N` explicitamente.
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

/** Extrai o N do utilitário `z-N` (base, sem variante responsiva). */
function zIndexDe(el: Element): number {
  const tokens = (el.getAttribute("class") ?? "").split(/\s+/);
  const z = tokens.find((t) => /^z-\d+$/.test(t));
  if (!z) throw new Error(`elemento sem utilitário z-N: ${el.getAttribute("class")}`);
  return Number(z.slice(2));
}

// O valor do Header (components/Header.tsx, `sticky top-0 z-30`). Se o Header
// subir de camada um dia, este contrato precisa ser revisto junto.
const Z_HEADER = 30;

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

/**
 * UX-03 fatia 3.8 — tablets (768–1024px): sidebar colapsada SEMPRE presente
 * em vez de esconder tudo atrás do hambúrguer. Um tablet tem largura de sobra
 * para 68px de ícones; tratá-lo como celular custava um toque extra em cada
 * navegação.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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
    modulos: () => Promise.resolve({ itens: [] }),
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

const matchMediaOriginal = window.matchMedia;
afterEach(() => {
  window.matchMedia = matchMediaOriginal;
});

function simulaViewportTablet() {
  window.matchMedia = ((query: string) => ({
    matches: query.includes("768px"), // só a media query da faixa tablet casa
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

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

describe("sidebar em tablet (UX-03 fatia 3.8)", () => {
  it("na faixa tablet, a sidebar rende colapsada mesmo sem preferência salva", () => {
    simulaViewportTablet();
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    expect(nav).toHaveAttribute("data-collapsed", "true");
  });

  it("a nav é estática a partir de md (não vive atrás do drawer)", () => {
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    expect(nav.className).toContain("md:static");
    expect(nav.className).toContain("md:translate-x-0");
  });

  it("fora da faixa tablet, a preferência do usuário continua mandando", () => {
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    expect(nav).toHaveAttribute("data-collapsed", "false");
  });
});

/**
 * UX-03 fatia 3.6 — sidebar colapsada: o rótulo dos itens permanece
 * acessível (sr-only) em vez de display:none. (O flyout de item-pai saiu da
 * barra com o menu único: não há mais item-pai.)
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  // A barra lateral lê a query da URL (qual caixa de Processos está aberta).
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/m/pagamentos",
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
    modulos: () => Promise.resolve({ itens: [{ slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 }] }),
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

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

beforeEach(() => {
  document.documentElement.dataset.sidebarCollapsed = "1";
});
afterEach(() => {
  delete document.documentElement.dataset.sidebarCollapsed;
});

describe("sidebar colapsada (UX-03 fatia 3.6)", () => {
  it("no menu único não há item-pai na barra: os cadastros moram na tela-índice", async () => {
    // O flyout de item-pai (fatia 3.6) existia para o "Cadastros" de
    // Pagamentos, que tinha filhos. Desde o menu único (2026-11-05) ele é um
    // link direto para `/m/pagamentos/cadastros`, onde os cadastros estão.
    renderSidebar({ modulo: "pagamentos", open: false, onClose: () => {} });
    const link = await screen.findByRole("link", { name: /cadastros e controle/i });
    expect(link).toHaveAttribute("href", "/m/pagamentos/cadastros");
    expect(screen.queryByRole("link", { name: /naturezas/i })).toBeNull();
  });

  it("o rótulo dos itens fica sr-only quando colapsada — não display:none", async () => {
    renderSidebar({ modulo: "pagamentos", open: false, onClose: () => {} });
    const link = await screen.findByRole("link", { name: /conciliação/i });
    const rotulo = within(link).getByText("Conciliação");
    // md:, não lg:, desde a 3.8 — o colapso também vale na faixa tablet
    expect(rotulo.className).toContain("md:sr-only");
    expect(rotulo.className).not.toMatch(/(?:md|lg):hidden/);
  });
});

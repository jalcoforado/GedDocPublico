/**
 * UX-03 fatia 3.6 — sidebar colapsada: item-pai com filhos vira flyout (não
 * navega silenciosamente para o 1º filho), e o rótulo dos itens permanece
 * acessível (sr-only) em vez de display:none.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
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
    modulos: () => Promise.resolve({ itens: [] }),
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
  it("item-pai com filhos é um botão que abre flyout com os filhos — não navega sozinho", () => {
    renderSidebar({ modulo: "pagamentos", open: false, onClose: () => {} });
    const pai = screen.getByRole("button", { name: /cadastros/i });
    expect(pai.tagName).toBe("BUTTON");
    fireEvent.click(pai);
    const flyout = document.querySelector("[data-popover]") as HTMLElement;
    expect(flyout).not.toBeNull();
    const naturezas = within(flyout).getByRole("link", { name: /naturezas/i });
    expect(naturezas).toHaveAttribute("href", "/m/pagamentos/cadastros/naturezas");
  });

  it("o rótulo dos itens fica sr-only quando colapsada — não display:none", () => {
    renderSidebar({ modulo: "pagamentos", open: false, onClose: () => {} });
    const link = screen.getByRole("link", { name: /conciliação/i });
    const rotulo = within(link).getByText("Conciliação");
    expect(rotulo.className).toContain("lg:sr-only");
    expect(rotulo.className).not.toContain("lg:hidden");
  });
});

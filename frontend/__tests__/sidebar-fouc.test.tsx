/**
 * UX-03 fatia 3.2 — anti-FOUC do colapso da Sidebar. O estado colapsado era
 * lido num useEffect: a sidebar SEMPRE pintava larga e encolhia um frame
 * depois, a cada navegação. O caminho sem flash: o THEME_INIT_SCRIPT (que já
 * roda antes do primeiro paint para o tema) grava o estado no <html>, e a
 * Sidebar nasce com ele.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
import { THEME_INIT_SCRIPT } from "@/lib/theme";
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
  localStorage.clear();
  delete document.documentElement.dataset.sidebarCollapsed;
});
afterEach(() => {
  delete document.documentElement.dataset.sidebarCollapsed;
});

describe("THEME_INIT_SCRIPT — estado do colapso", () => {
  it("com o colapso salvo, o script marca o <html> antes do React montar", () => {
    localStorage.setItem("aprimora.sidebar.collapsed", "1");
    // executa o script inline exatamente como o <head> faria
    new Function(THEME_INIT_SCRIPT)();
    expect(document.documentElement.dataset.sidebarCollapsed).toBe("1");
  });

  it("sem estado salvo, não marca nada", () => {
    new Function(THEME_INIT_SCRIPT)();
    expect(document.documentElement.dataset.sidebarCollapsed).toBeUndefined();
  });
});

describe("Sidebar — nasce colapsada sem flash", () => {
  it("com o <html> marcado pelo script, o PRIMEIRO render já sai colapsado", () => {
    document.documentElement.dataset.sidebarCollapsed = "1";
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    expect(nav).toHaveAttribute("data-collapsed", "true");
  });

  it("sem a marca, nasce expandida", () => {
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    expect(nav).toHaveAttribute("data-collapsed", "false");
  });

  it("alternar o colapso atualiza a marca no <html> (próximo load pinta certo)", () => {
    renderSidebar({ modulo: "frota", open: false, onClose: () => {} });
    fireEvent.click(screen.getByRole("button", { name: /recolher sidebar/i }));
    expect(document.documentElement.dataset.sidebarCollapsed).toBe("1");
    fireEvent.click(screen.getByRole("button", { name: /expandir sidebar/i }));
    expect(document.documentElement.dataset.sidebarCollapsed).toBeUndefined();
  });
});

/**
 * UX-03 fatia 3.1 — o drawer mobile da Sidebar segue o padrão de Dialog:
 * ESC fecha, Tab fica preso dentro enquanto aberto, o foco entra ao abrir e
 * volta ao gatilho ao fechar, e clicar num link da ROTA ATUAL fecha (antes o
 * fechamento dependia do pathname mudar — link da própria página não fechava
 * nada, e o drawer ficava aberto cobrindo a tela).
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
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

const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () => modulosMock(),
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

beforeEach(() => {
  modulosMock.mockReset();
  modulosMock.mockResolvedValue({
    itens: [
      { slug: "frota", nome: "Frota", icone: "Truck", ordem: 1 },
      { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
    ],
  });
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

describe("Sidebar drawer — padrão de Dialog (UX-03 fatia 3.1)", () => {
  it("ESC fecha o drawer aberto", async () => {
    const onClose = vi.fn();
    renderSidebar({ modulo: "frota", open: true, onClose });
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("fechado, ESC não dispara onClose", async () => {
    const onClose = vi.fn();
    renderSidebar({ modulo: "frota", open: false, onClose });
    await userEvent.keyboard("{Escape}");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("aberto, o foco entra no drawer", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    await waitFor(() => {
      const nav = screen.getByRole("navigation", { name: /navegação principal/i });
      expect(nav.contains(document.activeElement)).toBe(true);
    });
  });

  it("Tab no último focável volta ao primeiro (trap) enquanto aberto", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const nav = screen.getByRole("navigation", { name: /navegação principal/i });
    const focaveis = nav.querySelectorAll<HTMLElement>(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    );
    const ultimo = focaveis[focaveis.length - 1];
    ultimo.focus();
    await userEvent.keyboard("{Tab}");
    expect(nav.contains(document.activeElement)).toBe(true);
  });

  it("clicar num link da rota ATUAL fecha o drawer (pathname não muda)", () => {
    const onClose = vi.fn();
    renderSidebar({ modulo: "frota", open: true, onClose });
    // "Veículos" aponta para a rota atual /m/frota/veiculos
    fireEvent.click(screen.getByText("Veículos"));
    expect(onClose).toHaveBeenCalled();
  });

  it("ao fechar, o foco volta para o elemento que estava focado antes de abrir", async () => {
    function Harness() {
      const [open, setOpen] = React.useState(false);
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            hamburguer
          </button>
          <Sidebar modulo="frota" open={open} onClose={() => setOpen(false)} />
        </>
      );
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <ThemeProvider>
          <Harness />
        </ThemeProvider>
      </QueryClientProvider>,
    );
    const gatilho = screen.getByRole("button", { name: "hamburguer" });
    await userEvent.click(gatilho);
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(gatilho).toHaveFocus());
  });
});

/**
 * UX-03 fatia 3.3 — contrato de largura do conteúdo (spec §12.2): o <main>
 * centraliza em max-w-7xl por padrão; página que precisa de largura total
 * (dashboard) opta por fora marcando qualquer elemento com [data-full-width]
 * — o container solta o teto via :has(), sem prop nova no layout.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/m/frota/veiculos",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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
    notificacoes: { naoLidas: () => Promise.resolve({ total: 0, itens: [] }) },
    branding: () => Promise.resolve(null),
  },
}));

import AppLayout from "@/app/(app)/layout";
import { ThemeProvider } from "@/lib/theme";

function renderApp(children: React.ReactNode) {
  return render(
    <ThemeProvider>
      <AppLayout>{children}</AppLayout>
    </ThemeProvider>,
  );
}

describe("contrato de largura do conteúdo (UX-03 fatia 3.3)", () => {
  it("o conteúdo da página vive num container max-w-7xl centralizado", () => {
    renderApp(<p>conteúdo da página</p>);
    const container = screen
      .getByText("conteúdo da página")
      .closest(".max-w-7xl") as HTMLElement | null;
    expect(container).not.toBeNull();
    expect(container!.className).toContain("mx-auto");
  });

  it("o container oferece o opt-out por :has([data-full-width])", () => {
    renderApp(<p>conteúdo</p>);
    const container = screen.getByText("conteúdo").closest(".max-w-7xl") as HTMLElement;
    expect(container.className).toContain("has-[[data-full-width]]:max-w-none");
  });
});

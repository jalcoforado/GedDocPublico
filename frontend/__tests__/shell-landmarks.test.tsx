/**
 * UX-03 fatia 3.5 — skip link, landmarks e document.title. Antes: nenhum
 * atalho para pular a navegação, dois <header> aninhados semanticamente
 * (shell e PageHeader) e toda aba do navegador chamada só "Aprimora".
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
    branding: () => Promise.resolve(null),
  },
  notificacoesApi: {
    listarMinhas: () => Promise.resolve({ nao_lidas: 0, itens: [] }),
  },
}));

import AppLayout from "@/app/(app)/layout";
import { PageHeader } from "@/components/ui/page-header";
import { ThemeProvider } from "@/lib/theme";

function renderApp(children: React.ReactNode) {
  return render(
    <ThemeProvider>
      <AppLayout>{children}</AppLayout>
    </ThemeProvider>,
  );
}

describe("shell — skip link e landmarks (UX-03 fatia 3.5)", () => {
  it("o primeiro focável do shell é o skip link, apontando para o main", () => {
    renderApp(<p>conteúdo</p>);
    const skip = screen.getByRole("link", { name: /pular para o conteúdo/i });
    expect(skip.getAttribute("href")).toBe("#conteudo");
    const main = screen.getByRole("main");
    expect(main.id).toBe("conteudo");
  });

  it("o header do shell tem rótulo acessível", () => {
    renderApp(<p>conteúdo</p>);
    expect(screen.getByRole("banner").getAttribute("aria-label")).toBeTruthy();
  });
});

describe("PageHeader — sem banner aninhado + document.title (fatia 3.5)", () => {
  it("não renderiza um segundo <header> (role banner)", () => {
    render(<PageHeader title="Veículos" />);
    expect(screen.queryByRole("banner")).toBeNull();
  });

  it("define document.title com o título da página", () => {
    render(<PageHeader title="Veículos" />);
    expect(document.title).toBe("Veículos — Aprimora");
  });

  it("título não-string não quebra nem polui o document.title", () => {
    document.title = "Aprimora";
    render(<PageHeader title={<span>Composto</span>} />);
    expect(document.title).toBe("Aprimora");
  });
});

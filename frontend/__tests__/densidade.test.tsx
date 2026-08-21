/**
 * UX-03 fatia 3.9 — densidade de verdade (P1-13): o "Modo compacto" só
 * mudava tabelas. Agora `--density-*` é consumido pelo <main>, cards,
 * PageHeader e controles de formulário — o toggle muda a tela inteira.
 */
import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
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
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { ThemeProvider } from "@/lib/theme";

const globals = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

describe("densidade de verdade (UX-03 fatia 3.9)", () => {
  it("o modo compacto redefine os tokens de espaço de seção e ritmo vertical", () => {
    const compacto = globals.match(
      /:root\[data-density="compact"\]\s*\{[^}]*\}/,
    )?.[0];
    expect(compacto, "bloco compact existe").toBeTruthy();
    expect(compacto).toContain("--density-space:");
    expect(compacto).toContain("--density-gap:");
  });

  it("o <main> respira com --density-space (não p-6 fixo)", () => {
    render(
      <ThemeProvider>
        <AppLayout>
          <p>conteúdo</p>
        </AppLayout>
      </ThemeProvider>,
    );
    const main = screen.getByRole("main");
    expect(main.className).toContain("--density-space");
  });

  it("cards usam --density-space no padding das seções", () => {
    render(
      <Card>
        <CardHeader data-testid="ch">cabeçalho</CardHeader>
        <CardContent data-testid="cc">corpo</CardContent>
        <CardFooter data-testid="cf">rodapé</CardFooter>
      </Card>,
    );
    for (const id of ["ch", "cc", "cf"]) {
      expect(screen.getByTestId(id).className).toContain("--density-space");
    }
  });

  it("PageHeader alinha com o main via --density-space e ritma com --density-gap", () => {
    const { container } = render(<PageHeader title="Veículos" />);
    const raiz = container.firstElementChild as HTMLElement;
    expect(raiz.className).toContain("--density-space");
    const linhaTitulo = screen.getByRole("heading", { level: 1 })
      .closest("div")!.parentElement!.parentElement as HTMLElement;
    expect(linhaTitulo.className).toContain("--density-gap");
  });

  it("Input e Select têm altura de --density-row-h (mesma régua das linhas de tabela)", () => {
    render(
      <>
        <Input aria-label="campo" />
        <Select aria-label="escolha" />
      </>,
    );
    expect(screen.getByLabelText("campo").className).toContain("--density-row-h");
    expect(screen.getByLabelText("escolha").className).toContain("--density-row-h");
  });
});

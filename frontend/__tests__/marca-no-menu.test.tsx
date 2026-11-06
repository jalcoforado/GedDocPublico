/**
 * Onde a marca do município aparece: no CABEÇALHO, que vai de ponta a ponta
 * por cima da barra lateral (2026-11-06), sobre faixa clara. Na barra só na
 * gaveta do celular, que cobre o cabeçalho. Antes ficava num cartão branco no
 * topo da barra verde, e o cabeçalho (na cor da marca) a escondia no desktop.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/m/frota/veiculos",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", email: "t@x.test", is_super_usuario: true },
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
      Promise.resolve({ itens: [{ slug: "frota", nome: "Frota", icone: "Truck", ordem: 1 }] }),
  },
}));
vi.mock("@/lib/branding", () => ({
  useBranding: () => ({
    nome: "Prefeitura de Itaitinga",
    logo_url: "/brand/itaitinga-brasao.png",
    logo_login_url: "/brand/itaitinga-logo.png",
  }),
}));
// O cabeçalho monta busca, sino e conta; aqui só interessa a marca.
vi.mock("@/components/BuscaGlobal", () => ({ BuscaGlobal: () => null }));
vi.mock("@/components/NotificacoesBell", () => ({ NotificacoesBell: () => null }));
vi.mock("@/components/AvatarDropdown", () => ({ AvatarDropdown: () => null }));
vi.mock("@/components/UnidadeAtiva", () => ({ UnidadeAtiva: () => null }));
vi.mock("@/components/CommandPalette", () => ({ useCommandPalette: () => null }));

import { Header } from "@/components/Header";
import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

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

function comProviders(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>{ui}</ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("marca do município", () => {
  it("o cabeçalho traz a marca horizontal, num link para o início — em toda largura", () => {
    comProviders(<Header onOpenSidebar={() => {}} />);
    const inicio = screen.getByRole("link", { name: "Início" });
    expect(inicio.getAttribute("href")).toBe("/home");
    expect(Array.from(inicio.querySelectorAll("img")).map((i) => i.getAttribute("src"))).toEqual([
      "/brand/itaitinga-logo.png",
    ]);
    // Antes ela sumia do desktop quando havia menu lateral; agora o cabeçalho
    // passa por cima da barra e é ele quem leva a marca.
    expect(inicio.className).not.toContain("md:hidden");
  });

  it("no menu lateral a marca só existe na gaveta do celular (que cobre o cabeçalho)", () => {
    comProviders(<Sidebar modulo="frota" open onClose={() => {}} />);
    const marca = screen
      .getAllByRole("link", { name: "Início" })
      .find((a) => a.querySelector("img"));
    expect(marca, "link da marca na gaveta").toBeTruthy();
    expect(marca?.parentElement?.className).toContain("md:hidden");
  });

  it("no escuro a marca ganha fundo claro (texto marinho de prefeitura não some)", () => {
    comProviders(<Header />);
    expect(screen.getByRole("link", { name: "Início" }).className).toContain("bg-marca-fundo");
  });
});

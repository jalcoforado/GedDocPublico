/**
 * Onde a marca do município aparece: no topo do MENU LATERAL quando há menu,
 * e no cabeçalho só onde não há menu ao lado. As duas juntas, lado a lado,
 * eram redundância — e a primeira correção tirou a do menu, quando a que
 * devia sair era a do cabeçalho.
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
vi.mock("@/components/ModuloSwitcher", () => ({ ModuloSwitcher: () => null }));
vi.mock("@/components/NotificacoesBell", () => ({ NotificacoesBell: () => null }));
vi.mock("@/components/AvatarDropdown", () => ({ AvatarDropdown: () => null }));
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
  it("o menu lateral traz a marca, num link para o início", () => {
    comProviders(<Sidebar modulo="frota" open onClose={() => {}} />);
    // O menu também tem um ITEM "Início"; a marca é o link que carrega imagem.
    const inicio = screen
      .getAllByRole("link", { name: "Início" })
      .find((a) => a.querySelector("img"));
    expect(inicio, "link da marca no topo do menu").toBeTruthy();
    if (!inicio) return;
    expect(inicio.getAttribute("href")).toBe("/home");
    const imagens = Array.from(inicio.querySelectorAll("img")).map((i) => i.getAttribute("src"));
    // A horizontal para a barra aberta e a quadrada (brasão) para a recolhida.
    expect(imagens).toEqual(["/brand/itaitinga-logo.png", "/brand/itaitinga-brasao.png"]);
  });

  it("com menu lateral, a marca do cabeçalho some do desktop (fica para o celular)", () => {
    comProviders(<Header onOpenSidebar={() => {}} />);
    expect(screen.getByRole("link", { name: "Início" }).className).toContain("md:hidden");
  });

  it("sem menu lateral (início, perfil), o cabeçalho é quem mostra a marca", () => {
    comProviders(<Header />);
    expect(screen.getByRole("link", { name: "Início" }).className).not.toContain("md:hidden");
  });
});

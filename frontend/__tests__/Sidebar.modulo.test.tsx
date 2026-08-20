/**
 * A Sidebar passa a renderizar SÓ o módulo ativo, mais os transversais.
 * O que este teste protege: estar em /m/frota não pode mostrar menu de
 * pagamentos — era exatamente o que a Sidebar de 637 linhas fazia.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

// admin.me alimenta o link de plataforma (não testado aqui); modulos alimenta
// o SidebarModuloHeader — mesma queryKey `modulos-me` do ModuloSwitcher.
const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () => modulosMock(),
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

const DOIS_MODULOS = {
  itens: [
    { slug: "frota", nome: "Frota", icone: "Truck", ordem: 1 },
    { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
  ],
};

beforeEach(() => {
  modulosMock.mockReset();
  modulosMock.mockResolvedValue(DOIS_MODULOS);
});

// jsdom não implementa matchMedia; o ThemeProvider consulta a preferência do
// SO ao montar. Sem isso a montagem quebra antes de qualquer asserção.
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

// A Sidebar consulta /admin/me via react-query (link de plataforma) e usa
// ThemeToggle no rodapé (exige ThemeProvider) — sem os dois a montagem
// explode antes de qualquer asserção rodar.
function renderSidebar(props: ComponentProps<typeof Sidebar>) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <Sidebar {...props} />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("Sidebar por módulo", () => {
  it("mostra o menu do módulo ativo e não o dos outros", () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    expect(screen.getByText("Veículos")).toBeTruthy();
    expect(screen.queryByText("Contas a pagar")).toBeNull();
    expect(screen.queryByText("Permissionários")).toBeNull();
  });

  it("em rota transversal mostra os itens comuns e nenhum menu de módulo", () => {
    renderSidebar({ modulo: null, open: true, onClose: () => {} });
    expect(screen.getByText("Início")).toBeTruthy();
    expect(screen.queryByText("Veículos")).toBeNull();
  });

  it("o grupo comum (transversais) vem antes do grupo do módulo ativo", () => {
    // Guarda viva da ordem: "Geral" era o primeiro grupo no NAV original.
    // Precisa renderizar a Sidebar de verdade — um teste que só olhasse dados
    // (MENUS/ORDEM_GRUPOS_ORIGINAL) já passou verde uma vez com a Sidebar
    // montando a ordem oposta, porque nunca exercitava o componente.
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const geral = screen.getByText("Geral");
    // Botão do GRUPO "Frota" (role button, aria-expanded) — não o texto do
    // cabeçalho de módulo (role link), que também pode conter "Frota".
    const frota = screen.getByRole("button", { name: "Frota" });
    const posicao = geral.compareDocumentPosition(frota);
    expect(posicao & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

describe("cabeçalho de módulo (topo da Sidebar) — seletor", () => {
  it("dentro de um módulo, com mais de um módulo disponível, é um botão fechado com o nome do módulo", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const header = await waitFor(() => screen.getByTestId("sidebar-modulo-header"));
    expect(header.tagName).toBe("BUTTON");
    expect(header).toHaveAttribute("aria-expanded", "false");
    expect(header.textContent).toContain("Frota");
    // fechado: nenhum link de outro módulo ocupando a Sidebar
    expect(screen.queryByTestId("sidebar-modulo-lista")).toBeNull();
  });

  it("clicar abre a lista com os OUTROS módulos (raiz de cada um) e o link para /modulos — clicar de novo fecha", async () => {
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const header = await waitFor(() => screen.getByTestId("sidebar-modulo-header"));
    fireEvent.click(header);
    const lista = screen.getByTestId("sidebar-modulo-lista");
    expect(header).toHaveAttribute("aria-expanded", "true");
    const pagamentos = within(lista).getByRole("link", { name: /Pagamentos/ });
    expect(pagamentos).toHaveAttribute("href", "/m/pagamentos");
    // o módulo ativo não se lista a si mesmo — é o rótulo do botão
    expect(within(lista).queryByRole("link", { name: /Frota/ })).toBeNull();
    expect(within(lista).getByRole("link", { name: /todos os módulos/i })).toHaveAttribute(
      "href",
      "/modulos",
    );
    fireEvent.click(header);
    expect(screen.queryByTestId("sidebar-modulo-lista")).toBeNull();
  });

  it("em rota transversal, mostra rótulo neutro e a lista traz todos os módulos", async () => {
    renderSidebar({ modulo: null, open: true, onClose: () => {} });
    const header = await waitFor(() => screen.getByTestId("sidebar-modulo-header"));
    expect(header.textContent).toContain("Módulos");
    expect(header.textContent).not.toMatch(/frota|pagamentos/i);
    fireEvent.click(header);
    const lista = screen.getByTestId("sidebar-modulo-lista");
    expect(within(lista).getByRole("link", { name: /Frota/ })).toBeTruthy();
    expect(within(lista).getByRole("link", { name: /Pagamentos/ })).toBeTruthy();
  });

  it("com um único módulo disponível, mostra só o nome do módulo — sem link, sem seta, sem ação", async () => {
    // O launcher faz auto-redirect quando há um módulo só: um link aqui
    // bateria e voltaria na hora. Vale tanto dentro do módulo quanto numa
    // rota transversal — o que importa é ter um módulo só, não a rota atual.
    modulosMock.mockResolvedValue({
      itens: [{ slug: "frota", nome: "Frota", icone: "Truck", ordem: 1 }],
    });
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const header = await waitFor(() => screen.getByTestId("sidebar-modulo-header"));
    expect(header.tagName).toBe("DIV");
    expect(header).not.toHaveAttribute("href");
    expect(header.textContent).toBe("Frota");
  });

  it("erro ao carregar módulos fica visível e recuperável — não pode ser confundido com módulo único", async () => {
    modulosMock.mockReset();
    modulosMock.mockRejectedValue(new Error("falhou"));
    renderSidebar({ modulo: "frota", open: true, onClose: () => {} });
    const header = await waitFor(() => screen.getByTestId("sidebar-modulo-header"));
    expect(header.tagName).toBe("BUTTON");
    expect(header.textContent).toMatch(/indisponíveis/i);
  });
});

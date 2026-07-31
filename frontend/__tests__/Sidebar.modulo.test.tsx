/**
 * A Sidebar passa a renderizar SÓ o módulo ativo, mais os transversais.
 * O que este teste protege: estar em /frotas não pode mostrar menu de
 * pagamentos — era exatamente o que a Sidebar de 637 linhas fazia.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/frotas/veiculos",
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

import { Sidebar } from "@/components/Sidebar";
import { ThemeProvider } from "@/lib/theme";

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
    const frota = screen.getByText("Frota");
    const posicao = geral.compareDocumentPosition(frota);
    expect(posicao & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

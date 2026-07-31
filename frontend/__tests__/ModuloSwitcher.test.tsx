/**
 * O switcher. A propriedade de desenho que ele carrega (§6): trocar de módulo
 * NÃO passa pelo launcher — "o launcher é porta de entrada, não pedágio".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
const usePathnameMock = vi.fn(() => "/frotas/veiculos");
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  usePathname: () => usePathnameMock(),
}));

const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { modulos: () => modulosMock() },
}));

import { ModuloSwitcher } from "@/components/ModuloSwitcher";

// O componente herda o QueryClient da árvore (`Providers`, mesmo padrão do
// launcher) — aqui, como em Launcher.test.tsx, é o teste quem monta o
// provider, já que não há layout real montado no teste unitário.
function renderSwitcher() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ModuloSwitcher />
    </QueryClientProvider>,
  );
}

const DOIS_MODULOS = {
  itens: [
    { slug: "frota", nome: "Frota", icone: "Truck", ordem: 3 },
    { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
  ],
};

beforeEach(() => {
  push.mockClear();
  usePathnameMock.mockReturnValue("/frotas/veiculos");
  modulosMock.mockReset();
  modulosMock.mockResolvedValue(DOIS_MODULOS);
});

describe("switcher de módulo", () => {
  it("mostra o módulo ativo, derivado do pathname", async () => {
    renderSwitcher();
    await waitFor(() => expect(screen.getByRole("button", { name: /frota/i })).toBeTruthy());
  });

  it("trocar de módulo vai direto para a raiz, sem passar pelo launcher", async () => {
    renderSwitcher();
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /frota/i })));
    fireEvent.click(screen.getByText("Pagamentos"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/pagamentos"));
    expect(push).not.toHaveBeenCalledWith("/modulos");
  });

  it("oferece um caminho explícito de volta ao launcher", async () => {
    renderSwitcher();
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /frota/i })));
    fireEvent.click(screen.getByText(/todos os módulos/i));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/modulos"));
  });

  it("em rota transversal não aparenta estar em nenhum módulo", async () => {
    usePathnameMock.mockReturnValue("/home");
    renderSwitcher();
    const botao = await waitFor(() =>
      screen.getByRole("button", { name: /selecionar módulo/i }),
    );
    expect(botao).toBeTruthy();
    // Nem o nome acessível nem o rótulo visível podem mencionar um módulo
    // específico — a rota é transversal, não pertence a "frota".
    expect(screen.queryByRole("button", { name: /frota/i })).toBeNull();
    expect(screen.getByText("Módulos")).toBeTruthy();
  });

  it("erro ao carregar fica visível e recuperável, sem exigir reload", async () => {
    modulosMock.mockReset();
    modulosMock.mockRejectedValue(new Error("falhou"));
    renderSwitcher();

    const botaoErro = await waitFor(() =>
      screen.getByRole("button", { name: /não foi possível carregar os módulos/i }),
    );
    expect(botaoErro).toBeTruthy();
    // Não pode ser confundido com "só existe um módulo": aquele estado some
    // (retorna null), este permanece visível com um gatilho de nova tentativa.
    expect(screen.queryByRole("button", { name: /frota/i })).toBeNull();

    // A próxima tentativa (clique) resolve com sucesso — prova que dá para
    // sair do estado de erro sem recarregar a página.
    modulosMock.mockResolvedValueOnce(DOIS_MODULOS);
    fireEvent.click(botaoErro);
    await waitFor(() => expect(screen.getByRole("button", { name: /frota/i })).toBeTruthy());
  });
});

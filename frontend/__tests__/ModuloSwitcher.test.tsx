/**
 * O switcher. A propriedade de desenho que ele carrega (§6): trocar de módulo
 * NÃO passa pelo launcher — "o launcher é porta de entrada, não pedágio".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  usePathname: () => "/frotas/veiculos",
}));

vi.mock("@/lib/api", () => ({
  api: {
    modulos: () =>
      Promise.resolve({
        itens: [
          { slug: "frota", nome: "Frota", icone: "Truck", ordem: 3 },
          { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
        ],
      }),
  },
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
});

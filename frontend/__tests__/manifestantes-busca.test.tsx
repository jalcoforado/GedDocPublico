/**
 * Busca de manifestante no servidor (Novo processo e Balcão).
 *
 * Defeito de origem (2026-09-28): as duas telas pediam
 * `manifestantes.list({ page_size: 500 })`, o backend aceita até 200 e
 * respondia 422 — o combo ficava vazio para qualquer usuário.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const list = vi.fn();
const get = vi.fn();
vi.mock("@/lib/api", () => ({ api: { manifestantes: { list: (p: unknown) => list(p), get: (id: number) => get(id) } } }));

import { Combobox } from "@/components/ui/combobox";
import { useManifestantesBusca } from "@/lib/manifestantes";

const MARIA = { id: 1, nome: "Maria Souza", cpf_cnpj: "12345678909" };
const JOAO = { id: 2, nome: "João Lima", cpf_cnpj: "98765432100" };

function Tela({ inicial = null as number | null }) {
  const [valor, setValor] = useState<number | null>(inicial);
  const b = useManifestantesBusca(valor);
  return (
    <Combobox
      options={b.options}
      selectedOption={b.selectedOption}
      onQueryChange={b.onQueryChange}
      value={valor}
      onChange={(v) => setValor(typeof v === "number" ? v : null)}
    />
  );
}

function renderizar(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  list.mockReset();
  get.mockReset();
  list.mockImplementation(async (p: { q?: string }) => ({
    items: !p.q ? [MARIA, JOAO] : [MARIA, JOAO].filter((m) => (m.nome + m.cpf_cnpj).toLowerCase().includes(p.q!.toLowerCase().replace(/\D/g, "") || p.q!.toLowerCase())),
    total: 2, page: 1, page_size: 20,
  }));
});

describe("busca de manifestante no servidor", () => {
  it("nunca pede page_size acima do teto do backend (200)", async () => {
    renderizar(<Tela />);
    await waitFor(() => expect(list).toHaveBeenCalled());
    for (const [p] of list.mock.calls) expect((p as { page_size: number }).page_size).toBeLessThanOrEqual(200);
  });

  it("o que se digita vira `q` da API e o resultado aparece sem filtro local", async () => {
    renderizar(<Tela />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.type(screen.getByPlaceholderText("Buscar…"), "123.456");
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: "123.456" })));
    // o servidor achou Maria pelo CPF sem máscara; o combo não pode escondê-la
    await waitFor(() => expect(screen.getByRole("option", { name: /Maria Souza/ })).toBeInTheDocument());
  });

  it("o selecionado continua no gatilho quando a busca muda", async () => {
    renderizar(<Tela />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(await screen.findByRole("option", { name: /Maria Souza/ }));
    expect(screen.getByRole("combobox")).toHaveTextContent("Maria Souza");
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.type(screen.getByPlaceholderText("Buscar…"), "joão");
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("combobox")).toHaveTextContent("Maria Souza");
  });

  it("valor vindo de fora (rascunho restaurado) é buscado por id", async () => {
    list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    get.mockResolvedValue({ id: 77, nome: "Do Rascunho", cpf_cnpj: null });
    renderizar(<Tela inicial={77} />);
    await waitFor(() => expect(get).toHaveBeenCalledWith(77));
    await waitFor(() => expect(screen.getByRole("combobox")).toHaveTextContent("Do Rascunho"));
  });
});

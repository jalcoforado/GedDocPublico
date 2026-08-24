/**
 * Export contábil (Onda C2, C2.1) — tela de lotes.
 *
 * Cobre:
 *  C1. lista os lotes gerados (número, período, eventos, gerado em/por);
 *  C2. "Gerar lote" chama o POST com a data-limite escolhida;
 *  C3. 409 "nada a exportar" vira mensagem amigável, não erro genérico;
 *  C4. cada lote tem link de download apontando para a rota do arquivo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ContabilPage from "@/app/(app)/m/pagamentos/contabil/page";

const listarLotesMock = vi.fn();
const gerarLoteMock = vi.fn();
const arquivoUrlMock = vi.fn((loteId: number) => `/api/v2/pagamentos/contabil/lotes/${loteId}/arquivo`);

vi.mock("@/lib/api", async () => {
  const actual: any = await vi.importActual("@/lib/api");
  return {
    ...actual,
    api: {
      pagamentos: {
        contabil: {
          listarLotes: () => listarLotesMock(),
          gerarLote: (ate: string) => gerarLoteMock(ate),
          arquivoUrl: (loteId: number) => arquivoUrlMock(loteId),
        },
      },
    },
  };
});

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

const LOTE = {
  id: 1,
  numero: 3,
  periodo_inicio: "2026-08-01",
  periodo_fim: "2026-08-15",
  formato_versao: "neutro-csv-v1",
  qtd_eventos: 12,
  hash_conteudo: "abc123",
  id_usuario: 7,
  gerado_em: "2026-08-16T10:00:00",
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ContabilPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  listarLotesMock.mockResolvedValue([LOTE]);
});

describe("Export contábil — lotes", () => {
  it("lista os lotes com número, período, eventos e gerado em", async () => {
    renderPage();

    const celula = await screen.findByText("Lote 3");
    const linha = celula.closest("tr");
    expect(linha).not.toBeNull();
    expect(within(linha!).getByText("12")).toBeInTheDocument();
  });

  it("mostra estado vazio quando não há lotes ainda", async () => {
    listarLotesMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/nenhum lote/i)).toBeInTheDocument();
  });

  it("cada lote tem link de download apontando para a rota do arquivo", async () => {
    renderPage();
    await screen.findByText("Lote 3");

    const link = screen.getByRole("link", { name: /baixar csv do lote 3/i });
    expect(link).toHaveAttribute("href", "/api/v2/pagamentos/contabil/lotes/1/arquivo");
  });

  it('"Gerar lote" chama o POST com a data-limite escolhida', async () => {
    gerarLoteMock.mockResolvedValue({ ...LOTE, id: 2, numero: 4 });
    renderPage();
    await screen.findByText("Lote 3");

    fireEvent.click(screen.getByRole("button", { name: /gerar lote/i }));

    const dialog = (await screen.findByText("Gerar lote de export contábil")).closest(
      "[role=dialog]",
    ) as HTMLElement;
    fireEvent.change(within(dialog).getByLabelText(/data-limite/i), {
      target: { value: "2026-08-20" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /^Gerar$/i }));

    await waitFor(() => expect(gerarLoteMock).toHaveBeenCalledWith("2026-08-20"));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalled());
  });

  it('409 "nada a exportar" vira mensagem amigável, não erro genérico', async () => {
    const { ApiError } = await import("@/lib/api");
    gerarLoteMock.mockRejectedValue(
      new ApiError("Nada a exportar: nenhum evento pendente até a data informada.", 409),
    );
    renderPage();
    await screen.findByText("Lote 3");

    fireEvent.click(screen.getByRole("button", { name: /gerar lote/i }));
    const dialog = (await screen.findByText("Gerar lote de export contábil")).closest(
      "[role=dialog]",
    ) as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: /^Gerar$/i }));

    await waitFor(() =>
      expect(toastError).toHaveBeenCalledWith(
        "Nada a exportar: nenhum evento pendente até a data informada.",
      ),
    );
    // Não é o fallback genérico de outros erros.
    expect(toastError).not.toHaveBeenCalledWith(expect.stringMatching(/^Erro \d/));
  });
});

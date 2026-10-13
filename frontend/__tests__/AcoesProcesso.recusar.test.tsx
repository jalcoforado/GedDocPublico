/**
 * Recusar encaminhamento, no detalhe do processo: só com encaminhamento
 * pendente, e só com motivo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const recusarMock = vi.fn((_id: number, _motivo: string) => Promise.resolve({}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      processos: {
        ...actual.api.processos,
        recusarEncaminhamento: (id: number, motivo: string) => recusarMock(id, motivo),
      },
    },
  };
});

vi.mock("@/components/ArquivarDialog", () => ({ ArquivarDialog: () => null }));

import { AcoesProcesso } from "@/components/AcoesProcesso";
import type { ProcessoDetail } from "@/lib/api";

function processo(pendente: boolean): ProcessoDetail {
  return {
    id: 77,
    numero_processo: "2026/000077",
    ativo: true,
    movimentacoes: [
      {
        id: 1,
        acao_flag: "ENCAMINHAMENTO",
        encaminhamento: {
          id: 9, unidade_origem: "Secretaria de Obras", unidade_destino: "Procuradoria",
          prioridade: "Normal", quantidade_folhas: 0, data_prazo: null,
          recebido: !pendente, data_hora_recebimento: null, cancelado: false,
        },
      },
    ],
  } as unknown as ProcessoDetail;
}

function abrir(pendente = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AcoesProcesso processo={processo(pendente)} />
    </QueryClientProvider>,
  );
}

beforeEach(() => recusarMock.mockClear());
afterEach(cleanup);

describe("recusar encaminhamento", () => {
  it("sem encaminhamento pendente não há o que recusar", () => {
    abrir(false);
    expect(screen.getByRole("button", { name: "Recusar" })).toBeDisabled();
  });

  it("exige motivo: só espaço ou texto curto não libera a confirmação", () => {
    abrir();
    fireEvent.click(screen.getByRole("button", { name: "Recusar" }));

    const confirmar = screen.getByRole("button", { name: "Confirmar recusa" });
    expect(confirmar).toBeDisabled();
    // Diz para onde o processo volta.
    expect(screen.getByText("Secretaria de Obras")).toBeInTheDocument();

    const motivo = screen.getByLabelText("Motivo da recusa");
    fireEvent.change(motivo, { target: { value: "      " } });
    expect(confirmar).toBeDisabled();
    fireEvent.change(motivo, { target: { value: "não" } });
    expect(confirmar).toBeDisabled();
    expect(recusarMock).not.toHaveBeenCalled();
  });

  it("envia o motivo sem espaços nas pontas e fecha", async () => {
    abrir();
    fireEvent.click(screen.getByRole("button", { name: "Recusar" }));
    fireEvent.change(screen.getByLabelText("Motivo da recusa"), {
      target: { value: "  Não é da competência desta unidade.  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar recusa" }));

    await waitFor(() =>
      expect(recusarMock).toHaveBeenCalledWith(77, "Não é da competência desta unidade."),
    );
    await waitFor(() => expect(screen.queryByLabelText("Motivo da recusa")).toBeNull());
  });

  it("erro do servidor aparece no diálogo, que continua aberto", async () => {
    recusarMock.mockRejectedValueOnce(new Error("Nenhum encaminhamento pendente para este processo"));
    abrir();
    fireEvent.click(screen.getByRole("button", { name: "Recusar" }));
    fireEvent.change(screen.getByLabelText("Motivo da recusa"), {
      target: { value: "Faltam os documentos." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar recusa" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nenhum encaminhamento pendente");
    expect(screen.getByLabelText("Motivo da recusa")).toBeInTheDocument();
  });
});

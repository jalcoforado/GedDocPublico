/**
 * Desarquivar (SI-60, RF-01): o botão só existe para processo arquivado e para
 * quem tem a transação `processo_desarquivar`; a justificativa é obrigatória.
 * Processo arquivado não oferece encaminhar nem arquivar de novo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const desarquivarMock = vi.fn((_id: number, _justificativa: string) => Promise.resolve({}));
const canMock = vi.fn((_codigo: string, _action?: string) => true);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      processos: {
        ...actual.api.processos,
        desarquivar: (id: number, j: string) => desarquivarMock(id, j),
      },
    },
  };
});
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: (c: string, a?: string) => canMock(c, a) }),
}));
vi.mock("@/components/ArquivarDialog", () => ({ ArquivarDialog: () => null }));

import { AcoesProcesso } from "@/components/AcoesProcesso";
import type { ProcessoDetail } from "@/lib/api";

function processo(arquivado: boolean): ProcessoDetail {
  return {
    id: 88,
    numero_processo: "2026/000088",
    ativo: true,
    arquivado,
    // O arquivamento antigo continua na linha do tempo depois de desarquivar:
    // a tela não pode decidir por ele.
    movimentacoes: [{ id: 1, acao_flag: "ARQUIVAMENTO", encaminhamento: null }],
  } as unknown as ProcessoDetail;
}

function abrir(arquivado: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AcoesProcesso processo={processo(arquivado)} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  desarquivarMock.mockClear();
  canMock.mockReset();
  canMock.mockReturnValue(true);
});
afterEach(cleanup);

describe("desarquivar", () => {
  it("arquivado: oferece desarquivar, e não encaminhar nem arquivar", () => {
    abrir(true);
    expect(screen.getByRole("button", { name: "Desarquivar" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: "Arquivar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Encaminhar" })).toBeDisabled();
    expect(canMock).toHaveBeenCalledWith("processo_desarquivar", undefined);
  });

  it("sem a permissão específica o botão não aparece", () => {
    canMock.mockImplementation((c: string) => c !== "processo_desarquivar");
    abrir(true);
    expect(screen.queryByRole("button", { name: "Desarquivar" })).toBeNull();
  });

  it("desarquivado (arquivamento só no histórico) volta a arquivar e encaminhar", () => {
    abrir(false);
    expect(screen.queryByRole("button", { name: "Desarquivar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Arquivar" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Encaminhar" })).toBeEnabled();
  });

  it("exige justificativa e manda o texto sem espaços nas pontas", async () => {
    abrir(true);
    fireEvent.click(screen.getByRole("button", { name: "Desarquivar" }));
    fireEvent.click(screen.getByRole("button", { name: "Desarquivar processo" }));
    expect(await screen.findByText(/pelo menos 5 letras/)).toBeInTheDocument();
    expect(desarquivarMock).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Justificativa/), {
      target: { value: "  Documento novo  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Desarquivar processo" }));
    await waitFor(() => expect(desarquivarMock).toHaveBeenCalledWith(88, "Documento novo"));
  });
});

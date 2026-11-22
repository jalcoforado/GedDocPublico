/**
 * Cancelar recebimento (SI-61, RF-02): o botão aparece só quando o servidor diz
 * que há recebimento a desfazer E quem consulta tem a transação
 * `processo_cancelar_recebimento`; bloqueado, fica desabilitado e mostra o
 * motivo; a justificativa é obrigatória.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const cancelarMock = vi.fn((_id: number, _j: string) => Promise.resolve({}));
const canMock = vi.fn((_codigo: string, _action?: string) => true);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      processos: {
        ...actual.api.processos,
        cancelarRecebimento: (id: number, j: string) => cancelarMock(id, j),
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

function processo(extra: Partial<ProcessoDetail>): ProcessoDetail {
  return {
    id: 91,
    numero_processo: "2026/000091",
    ativo: true,
    arquivado: false,
    movimentacoes: [],
    ...extra,
  } as unknown as ProcessoDetail;
}

function abrir(extra: Partial<ProcessoDetail>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <AcoesProcesso processo={processo(extra)} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  cancelarMock.mockClear();
  canMock.mockReset();
  canMock.mockReturnValue(true);
});
afterEach(cleanup);

describe("cancelar recebimento", () => {
  it("sem recebimento a desfazer, o botão não existe", () => {
    abrir({ pode_cancelar_recebimento: null });
    expect(screen.queryByRole("button", { name: "Cancelar recebimento" })).toBeNull();
  });

  it("sem a permissão específica, o botão não existe", () => {
    canMock.mockImplementation((c: string) => c !== "processo_cancelar_recebimento");
    abrir({ pode_cancelar_recebimento: true });
    expect(screen.queryByRole("button", { name: "Cancelar recebimento" })).toBeNull();
  });

  it("bloqueado: desabilitado e com o motivo à vista", () => {
    const motivo = "Depois do recebimento o processo já recebeu despacho.";
    abrir({ pode_cancelar_recebimento: false, motivo_cancelar_recebimento: motivo });
    expect(screen.getByRole("button", { name: "Cancelar recebimento" })).toBeDisabled();
    expect(screen.getByText(motivo)).toBeInTheDocument();
  });

  it("exige justificativa e manda o texto sem espaços nas pontas", async () => {
    abrir({ pode_cancelar_recebimento: true });
    fireEvent.click(screen.getByRole("button", { name: "Cancelar recebimento" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelamento" }));
    expect(await screen.findByText(/pelo menos 5 letras/)).toBeInTheDocument();
    expect(cancelarMock).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Justificativa/), {
      target: { value: "  Recebido por engano  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar cancelamento" }));
    await waitFor(() => expect(cancelarMock).toHaveBeenCalledWith(91, "Recebido por engano"));
  });
});

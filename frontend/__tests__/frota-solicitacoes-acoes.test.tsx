/**
 * Solicitações de veículo: a coluna Ações mostra só o próximo passo do fluxo
 * e manda o resto para o ⋯. Antes eram até cinco botões empilhados, com
 * "Excluir" em vermelho cheio, e as datas vinham com segundos.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";
import type { SolicitacaoVeiculo } from "@/lib/api";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: ["frota"],
    loading: false,
    can: () => true,
  }),
}));

const sol = (
  id: number,
  finalidade: string,
  status: string,
  veiculo: number | null = null,
): SolicitacaoVeiculo =>
  ({
    id,
    finalidade,
    destino: "Sede",
    status,
    id_unidade_solicitante: null,
    data_saida_prevista: "2026-11-11T14:55:43",
    data_retorno_prevista: "2026-11-11T18:30:00",
    quantidade_passageiros: 2,
    necessita_motorista: false,
    id_veiculo_designado: veiculo,
    id_motorista_designado: null,
    data_saida_real: null,
    data_retorno_real: null,
    km_saida: null,
    km_retorno: null,
  }) as unknown as SolicitacaoVeiculo;

const SOLICITACOES = [
  sol(1, "Pedido novo", "solicitada"),
  sol(2, "Aprovada sem veículo", "aprovada"),
  sol(3, "Aprovada com veículo", "aprovada", 10),
  sol(4, "Na rua", "em_uso", 10),
];
const aprovarMock = vi.fn((_id: number) => Promise.resolve({}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      solicitacoes: {
        ...actual.api.solicitacoes,
        listAll: () => Promise.resolve(SOLICITACOES),
        aprovar: (id: number) => aprovarMock(id),
      },
      unidades: { ...actual.api.unidades, list: () => Promise.resolve({ items: [] }) },
      frota: { ...actual.api.frota, listAll: () => Promise.resolve([]) },
      motoristas: { ...actual.api.motoristas, listAll: () => Promise.resolve([]) },
    },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/frota/solicitacoes/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <Pagina />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** A linha da tabela pela finalidade. */
async function linha(finalidade: string) {
  const celula = await screen.findByText(finalidade);
  return within(celula.closest("tr") as HTMLElement);
}

/** Rótulos dos botões à vista na coluna Ações da linha. */
function botoesAVista(l: { getAllByRole: (papel: "button") => HTMLElement[] }) {
  return l.getAllByRole("button").map((b: HTMLElement) => b.getAttribute("aria-label") ?? b.textContent);
}

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => aprovarMock.mockClear());
afterEach(cleanup);

describe("solicitações de veículo — ações da linha", () => {
  it("cada linha mostra só o próximo passo do fluxo; o resto vai para o ⋯", async () => {
    await abrir();
    expect(botoesAVista(await linha("Pedido novo"))).toEqual(["Aprovar", "Mais ações"]);
    expect(botoesAVista(await linha("Aprovada sem veículo"))).toEqual(["Designar", "Mais ações"]);
    expect(botoesAVista(await linha("Aprovada com veículo"))).toEqual([
      "Registrar saída",
      "Mais ações",
    ]);
    // Duas ações cabem à vista — um menu de um item só seria um clique a mais.
    expect(botoesAVista(await linha("Na rua"))).toEqual(["Registrar retorno", "Excluir"]);
  });

  it("as demais ações seguem no ⋯, com as destrutivas por último", async () => {
    await abrir();
    const l = await linha("Pedido novo");
    fireEvent.click(l.getByRole("button", { name: "Mais ações" }));
    expect(screen.getAllByRole("menuitem").map((i) => i.textContent)).toEqual([
      "Rejeitar",
      "Editar",
      "Cancelar",
      "Excluir",
    ]);
  });

  it("o botão à vista executa o passo", async () => {
    await abrir();
    const l = await linha("Pedido novo");
    fireEvent.click(l.getByRole("button", { name: "Aprovar" }));
    await waitFor(() => expect(aprovarMock).toHaveBeenCalledWith(1));
  });

  it("datas sem segundos", async () => {
    await abrir();
    const l = await linha("Pedido novo");
    expect(l.getByText("11/11/2026 14:55")).toBeInTheDocument();
    expect(l.queryByText(/14:55:43/)).toBeNull();
  });
});

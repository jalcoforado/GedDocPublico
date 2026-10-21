/**
 * Unidade ativa no cabeçalho (o "DIRPRE-CDC" do SEI). O que importa pegar:
 *
 * - a unidade aparece, com ou sem troca possível;
 * - com 2+ lotações, trocar chama `trocarLotacao` com o id certo E invalida
 *   as queries — sem isso o painel e as caixas seguem mostrando os números
 *   da unidade anterior, sem erro nenhum;
 * - com uma lotação só, não há botão: um controle que não troca nada engana.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const trocarLotacaoMock = vi.fn().mockResolvedValue(undefined);
let mockUser: Record<string, unknown> | null = null;

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    perms: null,
    loading: false,
    logout: vi.fn(),
    trocarLotacao: trocarLotacaoMock,
  }),
}));

import { UnidadeAtiva } from "@/components/UnidadeAtiva";
import { ToastProvider } from "@/components/ui/toast";

function montar(lotacoes: { id: number; nome: string; principal: boolean }[], ativa: number | null) {
  mockUser = {
    id: 1,
    nome: "Ana Souza",
    email: "ana@x.test",
    id_unidade_trabalho: lotacoes.find((l) => l.principal)?.id ?? null,
    unidade_contexto_id: ativa,
    lotacoes,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // Queries que a troca precisa derrubar: painel da tela inicial, contadores
  // da lateral e a lista de processos.
  for (const chave of [["home-painel"], ["processos-caixas"], ["processos", { caixa: "entrada" }]]) {
    client.setQueryData(chave, { qualquer: true });
  }
  const invalidar = vi.spyOn(client, "invalidateQueries");
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <UnidadeAtiva />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { client, invalidar };
}

afterEach(() => {
  mockUser = null;
  trocarLotacaoMock.mockClear();
});

const DUAS = [
  { id: 10, nome: "SEAS/ASCOI", principal: true },
  { id: 20, nome: "SEAS/CSIN", principal: false },
];

describe("UnidadeAtiva — cabeçalho", () => {
  it("mostra a unidade ativa (a do contexto, não a principal)", () => {
    montar(DUAS, 20);
    expect(screen.getByRole("button", { name: /unidade: seas\/csin/i })).toBeInTheDocument();
    expect(screen.getByText("SEAS/CSIN")).toBeInTheDocument();
  });

  it("sem contexto no token, mostra a principal", () => {
    montar(DUAS, null);
    expect(screen.getByText("SEAS/ASCOI")).toBeInTheDocument();
  });

  it("com várias lotações, trocar chama trocarLotacao com o id certo e invalida as queries", async () => {
    const { client, invalidar } = montar(DUAS, 10);
    fireEvent.click(screen.getByRole("button", { name: /trocar de unidade/i }));
    const grupo = screen.getByRole("radiogroup", { name: /lotação ativa/i });
    expect(within(grupo).getByRole("radio", { name: /SEAS\/ASCOI/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    fireEvent.click(within(grupo).getByRole("radio", { name: /SEAS\/CSIN/i }));

    await waitFor(() => expect(trocarLotacaoMock).toHaveBeenCalledWith(20));
    await waitFor(() => expect(invalidar).toHaveBeenCalled());
    for (const chave of [["home-painel"], ["processos-caixas"], ["processos", { caixa: "entrada" }]]) {
      expect(client.getQueryState(chave)?.isInvalidated, JSON.stringify(chave)).toBe(true);
    }
  });

  it("escolher a unidade que já está ativa não troca nem invalida", async () => {
    const { invalidar } = montar(DUAS, 10);
    fireEvent.click(screen.getByRole("button", { name: /trocar de unidade/i }));
    const grupo = screen.getByRole("radiogroup", { name: /lotação ativa/i });
    fireEvent.click(within(grupo).getByRole("radio", { name: /SEAS\/ASCOI/i }));
    await new Promise((r) => setTimeout(r, 0));
    expect(trocarLotacaoMock).not.toHaveBeenCalled();
    expect(invalidar).not.toHaveBeenCalled();
  });

  it("falha na troca não invalida nada (os números continuam sendo da unidade de antes)", async () => {
    trocarLotacaoMock.mockRejectedValueOnce(new Error("Lotação não pertence a este usuário"));
    const { invalidar } = montar(DUAS, 10);
    fireEvent.click(screen.getByRole("button", { name: /trocar de unidade/i }));
    const grupo = screen.getByRole("radiogroup", { name: /lotação ativa/i });
    fireEvent.click(within(grupo).getByRole("radio", { name: /SEAS\/CSIN/i }));
    await waitFor(() => expect(trocarLotacaoMock).toHaveBeenCalledWith(20));
    expect(await screen.findByText(/não pertence a este usuário/i)).toBeInTheDocument();
    expect(invalidar).not.toHaveBeenCalled();
  });

  it("com uma lotação só, é rótulo: sem botão e sem lista de troca", () => {
    montar([{ id: 10, nome: "Setor Único", principal: true }], 10);
    expect(screen.getByText("Setor Único")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("radiogroup")).toBeNull();
  });

  it("sem lotação nenhuma, não aparece", () => {
    const { client } = montar([], null);
    expect(client).toBeTruthy();
    expect(screen.queryByText(/unidade/i)).toBeNull();
  });
});

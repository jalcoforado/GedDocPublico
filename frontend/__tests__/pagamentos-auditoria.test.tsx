/**
 * Trilha de auditoria de pagamentos.
 *
 * A tela é para quem presta contas: o ato tem de sair em português (não o
 * código gravado), a linha tem de levar à solicitação, e o filtro tem de pedir
 * ao servidor exatamente o recorte escolhido — a filtragem é dele, não da tela.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const LINHAS = [
  { id: 3, id_usuario: 41, nome_usuario: "Otávio Prado", acao: "pagamento.autorizado",
    entidade: "ordem_pagamento", id_entidade: 9, request_id: null, ip: null,
    criado_em: "2026-10-11T14:00:00",
    payload: { numero: "OP-2026-0007", valor_total: "9000.00", debito_ids: [12, 15],
               excecao_saldo: true } },
  { id: 2, id_usuario: 52, nome_usuario: "Teresa Cordeiro", acao: "pagamento.parcela_estornada",
    entidade: "parcela", id_entidade: 77, request_id: "r1", ip: "203.0.113.7",
    criado_em: "2026-10-11T15:30:00",
    payload: { id_debito: 12, valor: "150.50", justificativa: "Pago em duplicidade" } },
  { id: 1, id_usuario: null, nome_usuario: null, acao: "pagamento.conciliado",
    entidade: "conciliacao", id_entidade: 5, request_id: null, ip: null,
    criado_em: "2026-10-11T16:00:00", payload: { valor: "10.00" } },
];

const auditoriaMock = vi.fn((_f?: Record<string, unknown>) =>
  Promise.resolve({ items: LINHAS, total: 3, page: 1, page_size: 50 }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, pagamentos: { ...actual.api.pagamentos, auditoria: auditoriaMock } },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/pagamentos/auditoria/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await screen.findByRole("cell", { name: "Pagamento autorizado" });
}

const ultimaChamada = () => auditoriaMock.mock.calls.at(-1)?.[0] as Record<string, unknown>;

beforeEach(() => auditoriaMock.mockClear());

describe("trilha de auditoria de pagamentos", () => {
  it("mostra de que IP o ato partiu, e nada quando a linha não tem IP", async () => {
    await abrir();
    const linhaDe = (ato: string) =>
      within(screen.getByRole("cell", { name: ato }).closest("tr") as HTMLElement);
    expect(linhaDe("Pagamento estornado").getByText("IP 203.0.113.7")).toBeInTheDocument();
    expect(linhaDe("Pagamento autorizado").queryByText(/^IP /)).toBeNull();
  });

  it("mostra o ato em português, quem praticou e leva às solicitações", async () => {
    await abrir();
    const linha = within(screen.getByRole("cell", { name: "Pagamento autorizado" }).closest("tr") as HTMLElement);
    expect(linha.getByRole("button", { name: "Otávio Prado" })).toBeInTheDocument();
    expect(linha.getByRole("link", { name: "#12" })).toHaveAttribute(
      "href", "/m/pagamentos/solicitacoes/12");
    expect(linha.getByRole("link", { name: "#15" })).toBeInTheDocument();
    expect(linha.getByText(/9\.000,00/)).toBeInTheDocument();
    expect(linha.getByText(/com exceção de saldo/)).toBeInTheDocument();
    // O código gravado não aparece para quem lê.
    expect(screen.queryByText("pagamento.autorizado")).toBeNull();
  });

  it("mostra a justificativa do estorno e 'Sistema' quando não há autor", async () => {
    await abrir();
    const estorno = within(screen.getByRole("cell", { name: "Pagamento estornado" }).closest("tr") as HTMLElement);
    expect(estorno.getByText(/Pago em duplicidade/)).toBeInTheDocument();
    const conciliado = within(screen.getByRole("cell", { name: "Lançamento conciliado" }).closest("tr") as HTMLElement);
    expect(conciliado.getByText("Sistema")).toBeInTheDocument();
  });

  it("filtrar por ato e período pede o recorte ao servidor, com o dia inteiro", async () => {
    await abrir();
    fireEvent.change(screen.getByLabelText("Ato"), { target: { value: "pagamento.parcela_paga" } });
    fireEvent.change(screen.getByLabelText("De"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("Até"), { target: { value: "2026-10-11" } });
    await waitFor(() =>
      expect(ultimaChamada()).toEqual({
        acao: "pagamento.parcela_paga", desde: "2026-10-01T00:00:00",
        ate: "2026-10-11T23:59:59", id_usuario: undefined, page: 1, page_size: 50,
      }),
    );
  });

  it("clicar no nome filtra pelos atos daquela pessoa, e o filtro pode ser removido", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Teresa Cordeiro" }));
    await waitFor(() => expect(ultimaChamada().id_usuario).toBe(52));
    const remover = await screen.findByRole("button", {
      name: "Remover filtro por Teresa Cordeiro",
    });
    fireEvent.click(remover);
    await waitFor(() => expect(ultimaChamada().id_usuario).toBeUndefined());
  });
});

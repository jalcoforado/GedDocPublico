/**
 * Estorno, revogação de liberação e recolhimento de retenção no detalhe.
 *
 * Os três endpoints existiam sem tela. O que se trava aqui é a oferta certa
 * para o estado e o perfil certos, e que nenhuma das duas ações destrutivas
 * sai sem justificativa.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const estado = { perms: [] as string[] };

const estornarMock = vi.fn((_id: number, _j: string) => Promise.resolve({}));
const revogarMock = vi.fn((_id: number, _j: string) => Promise.resolve({}));
const recolherMock = vi.fn(
  (_id: number, _d: { data_recolhimento: string; documento_recolhimento: string }) =>
    Promise.resolve({}),
);

const parcela = (id: number, numero: number, status: string) => ({
  id, id_debito: 20, numero, valor: "500.00", vencimento: "2026-10-30", status,
  data_pagamento: null, forma_pagamento: null, id_movimentacao: null,
  data_prevista_pagamento: null,
});

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        parcelas: {
          ...actual.api.pagamentos.parcelas,
          estornar: estornarMock,
          revogarLiberacao: revogarMock,
        },
        retencoes: {
          ...actual.api.pagamentos.retencoes,
          recolher: recolherMock,
          listarDoDebito: () => Promise.resolve({
            valor_bruto: "1500.00", valor_liquido: "1470.00",
            retencoes: [
              { id: 8, id_debito: 20, tipo: "IRRF", descricao: null, base_calculo: "1500.00",
                aliquota: "1", valor: "15.00", recolhido: false, data_recolhimento: null,
                documento_recolhimento: null, criado_em: "2026-10-01T10:00:00Z", atualizado_em: null },
              { id: 9, id_debito: 20, tipo: "ISS", descricao: null, base_calculo: "1500.00",
                aliquota: "1", valor: "15.00", recolhido: true, data_recolhimento: "2026-10-05",
                documento_recolhimento: "DAM-1", criado_em: "2026-10-01T10:00:00Z", atualizado_em: null },
            ],
          }),
        },
        debitos: {
          ...actual.api.pagamentos.debitos,
          get: () => Promise.resolve({
            id: 20, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 1,
            id_fonte_recursos: 7, id_conta: null, id_conta_pagadora: 3, id_contrato: 4,
            valor_total: "1500.00", competencia: "2026-09", numero_ne: "NE-1", numero_nf: null,
            criticidade: "MEDIA", urgente: false, justificativa_urgencia: null,
            descricao: "Serviço de teste", status: "AUTORIZADO",
            situacao_tramitacao: "AUTORIZADA", situacao_fila: "ELEGIVEL",
            situacao_pagamento: "PAGA_PARCIAL", id_unidade: 1, versao: 1, lock_version: 5,
            id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
            liquidacao_confirmada: true, data_liquidacao: "2026-09-01",
            criado_em: "2026-09-01T10:00:00Z", atualizado_em: null, historico: [],
            parcelas: [parcela(51, 1, "PAGA"), parcela(52, 2, "LIBERADA"), parcela(53, 3, "A_PAGAR")],
          }),
          listarPedidosAjuste: () => Promise.resolve([]),
          listarVersoes: () => Promise.resolve([]),
          listarAnexos: () => Promise.resolve([]),
          listarExcecoes: () => Promise.resolve([]),
          checklist: () => Promise.resolve([]),
          posicaoDebito: () => Promise.reject(new actual.ApiError("Sem posição na fila.", 404)),
        },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

async function abrir() {
  const { DetalheDebitoContent } = await import("@/components/pagamentos/DetalheDebitoContent");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <DetalheDebitoContent id={20} />
    </QueryClientProvider>,
  );
  await screen.findByRole("heading", { name: "Parcelas" });
  await screen.findByText("IRRF");
}

beforeEach(() => {
  estado.perms = [];
  estornarMock.mockClear();
  revogarMock.mockClear();
  recolherMock.mockClear();
});

describe("ações financeiras no detalhe do débito", () => {
  it("tesouraria: estorna só a parcela PAGA, e só com justificativa", async () => {
    estado.perms = ["pagamento_pagar"];
    await abrir();
    expect(screen.getAllByRole("button", { name: /^Estornar pagamento da parcela/ })).toHaveLength(1);
    expect(screen.queryByRole("button", { name: /^Revogar liberação/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Estornar pagamento da parcela 1" }));
    const dialogo = within(await screen.findByRole("dialog"));
    const confirmar = dialogo.getByRole("button", { name: "Estornar pagamento" });
    expect(confirmar).toBeDisabled();
    fireEvent.click(confirmar);
    expect(estornarMock).not.toHaveBeenCalled();

    fireEvent.change(dialogo.getByLabelText(/Justificativa/), {
      target: { value: "Pago em duplicidade" },
    });
    fireEvent.click(confirmar);
    await waitFor(() => expect(estornarMock).toHaveBeenCalledWith(51, "Pago em duplicidade"));
  });

  it("autoridade: revoga só a parcela LIBERADA, e não vê estorno", async () => {
    estado.perms = ["pagamento_autorizar"];
    await abrir();
    expect(screen.queryByRole("button", { name: /^Estornar pagamento da parcela/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Revogar liberação da parcela 2" }));
    const dialogo = within(await screen.findByRole("dialog"));
    fireEvent.change(dialogo.getByLabelText(/Justificativa/), {
      target: { value: "Liberada por engano" },
    });
    fireEvent.click(dialogo.getByRole("button", { name: "Revogar liberação" }));
    await waitFor(() => expect(revogarMock).toHaveBeenCalledWith(52, "Liberada por engano"));
    expect(estornarMock).not.toHaveBeenCalled();
  });

  it("tesouraria: registra o recolhimento só da retenção pendente, com data e documento", async () => {
    estado.perms = ["pagamento_pagar"];
    await abrir();
    expect(screen.getAllByRole("button", { name: /^Registrar recolhimento da retenção/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Registrar recolhimento da retenção IRRF" }));
    const dialogo = within(await screen.findByRole("dialog"));
    const registrar = dialogo.getByRole("button", { name: "Registrar" });
    expect(registrar).toBeDisabled();
    fireEvent.change(dialogo.getByLabelText(/Data do recolhimento/), { target: { value: "2026-10-10" } });
    expect(registrar).toBeDisabled();
    fireEvent.change(dialogo.getByLabelText(/Documento de arrecadação/), { target: { value: "DARF 123" } });
    fireEvent.click(registrar);
    await waitFor(() =>
      expect(recolherMock).toHaveBeenCalledWith(8, {
        data_recolhimento: "2026-10-10", documento_recolhimento: "DARF 123",
      }),
    );
  });

  it("quem só solicita não vê nenhuma das três ações", async () => {
    estado.perms = ["pagamento_solicitar"];
    await abrir();
    expect(screen.queryByRole("button", { name: /^Estornar pagamento/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Revogar liberação/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Registrar recolhimento/ })).toBeNull();
  });
});

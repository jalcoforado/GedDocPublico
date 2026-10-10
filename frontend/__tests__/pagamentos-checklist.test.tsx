/**
 * Conferência de documentos no detalhe da solicitação de pagamento.
 *
 * O que não pode voltar a acontecer: a validação financeira exigir itens
 * marcados (422 no backend) sem que exista onde marcá-los. Era o estado até
 * esta seção existir — o débito criado pela tela não saía de "aguardando
 * validação".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ChecklistItemDebito } from "@/lib/api";

const estado = {
  tramitacao: "AGUARDANDO_VALIDACAO",
  perms: ["pagamento_validar"] as string[],
};

const item = (
  id: number,
  descricao: string,
  obrigatorio: boolean,
  marcado: boolean,
): ChecklistItemDebito => ({
  id_checklist_item: id, descricao, obrigatorio, marcado, observacao: null, atualizado_em: null,
});

let itens: ChecklistItemDebito[] = [];
const checklistMock = vi.fn(() => Promise.resolve(itens));
const marcarMock = vi.fn((_id: number, v: { id_checklist_item: number; marcado: boolean }) => {
  itens = itens.map((i) =>
    i.id_checklist_item === v.id_checklist_item ? { ...i, marcado: v.marcado } : i,
  );
  return Promise.resolve(itens);
});
const validarMock = vi.fn((_id: number, _v: { lock_version: number }) => Promise.resolve({}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        retencoes: {
          ...actual.api.pagamentos.retencoes,
          listarDoDebito: () =>
            Promise.resolve({ valor_bruto: "1000.00", valor_liquido: "1000.00", retencoes: [] }),
        },
        debitos: {
          ...actual.api.pagamentos.debitos,
          get: () => Promise.resolve({
            id: 20, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 1,
            id_fonte_recursos: 1, id_conta: null, id_conta_pagadora: null, id_contrato: null,
            valor_total: "1000.00", competencia: "2026-09", numero_ne: null, numero_nf: null,
            criticidade: "MEDIA", urgente: false, justificativa_urgencia: null,
            descricao: "Serviço de teste", status: "EM_ANALISE",
            situacao_tramitacao: estado.tramitacao, situacao_fila: "REGISTRADA",
            situacao_pagamento: "NAO_INICIADA", id_unidade: 1, versao: 1, lock_version: 3,
            id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
            liquidacao_confirmada: true, data_liquidacao: "2026-09-01",
            criado_em: "2026-09-01T10:00:00Z", atualizado_em: null,
            parcelas: [], historico: [],
          }),
          listarPedidosAjuste: () => Promise.resolve([]),
          listarVersoes: () => Promise.resolve([]),
          listarAnexos: () => Promise.resolve([]),
          listarExcecoes: () => Promise.resolve([]),
          posicaoDebito: () => Promise.reject(new actual.ApiError("Sem posição na fila.", 404)),
          checklist: checklistMock,
          marcarChecklist: marcarMock,
          validar: validarMock,
        },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Validador", is_super_usuario: false },
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
  const titulo = await screen.findByRole("heading", { name: "Conferência de documentos" });
  return within(titulo.closest("section") as HTMLElement);
}

beforeEach(() => {
  estado.tramitacao = "AGUARDANDO_VALIDACAO";
  estado.perms = ["pagamento_validar"];
  itens = [
    item(1, "Nota fiscal atestada", true, false),
    item(2, "Certidão municipal", false, false),
  ];
  checklistMock.mockClear();
  marcarMock.mockClear();
  validarMock.mockClear();
});

describe("conferência de documentos no detalhe do débito", () => {
  it("lista os itens e diz quantos obrigatórios faltam", async () => {
    const secao = await abrir();
    expect(await secao.findByLabelText("Nota fiscal atestada")).not.toBeChecked();
    expect(secao.getByLabelText("Certidão municipal")).toBeInTheDocument();
    expect(secao.getByRole("status")).toHaveTextContent("Falta 1 item obrigatório");
  });

  it("marcar chama o backend e o aviso de pendência some", async () => {
    const secao = await abrir();
    fireEvent.click(await secao.findByLabelText("Nota fiscal atestada"));
    await waitFor(() =>
      expect(marcarMock).toHaveBeenCalledWith(20, { id_checklist_item: 1, marcado: true }),
    );
    await waitFor(() => expect(secao.getByLabelText("Nota fiscal atestada")).toBeChecked());
    expect(secao.getByRole("status")).toHaveTextContent(
      "Todos os itens obrigatórios foram conferidos",
    );
  });

  it("com obrigatório pendente, o diálogo de validar lista o que falta e não confirma", async () => {
    const secao = await abrir();
    await secao.findByLabelText("Nota fiscal atestada");
    fireEvent.click(await screen.findByRole("button", { name: /validar/i }));
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Nota fiscal atestada");
    expect(alerta).not.toHaveTextContent("Certidão municipal");
    const confirmar = screen.getByRole("button", { name: "Confirmar" });
    expect(confirmar).toBeDisabled();
    fireEvent.click(confirmar);
    expect(validarMock).not.toHaveBeenCalled();
  });

  it("com tudo conferido, a validação segue", async () => {
    itens = [item(1, "Nota fiscal atestada", true, true)];
    const secao = await abrir();
    await secao.findByLabelText("Nota fiscal atestada");
    fireEvent.click(await screen.findByRole("button", { name: /validar/i }));
    const confirmar = await screen.findByRole("button", { name: "Confirmar" });
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(confirmar);
    await waitFor(() => expect(validarMock).toHaveBeenCalledWith(20, { lock_version: 3 }));
  });

  it("quem não valida vê os itens, mas não marca", async () => {
    estado.perms = ["pagamento_solicitar"];
    const secao = await abrir();
    expect(await secao.findByLabelText("Nota fiscal atestada")).toBeDisabled();
  });

  it("fora da etapa de validação a conferência é só leitura", async () => {
    estado.tramitacao = "AGUARDANDO_AUTORIDADE";
    const secao = await abrir();
    expect(await secao.findByLabelText("Nota fiscal atestada")).toBeDisabled();
  });
});

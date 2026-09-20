/**
 * F4 (Tesouraria): Central da tesouraria (seleção -> lote -> programar ->
 * enviar -> retorno) e a seção Retenções no detalhe do débito.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ContaBancaria, LoteDetalhe, LotePagamento, Parcela, RetencoesDebito,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const contaPrincipal: ContaBancaria = {
  id: 1, nome: "Conta Principal", banco: "001", agencia: "1", conta: "1234-5",
  id_fonte_recursos: 1, grupo_despesa: "CUSTEIO",
  saldo_inicial: "10000.00", saldo_minimo_alerta: "0", ativa: true,
} as ContaBancaria;

const parcelaElegivel: Parcela = {
  id: 55, id_debito: 20, numero: 1, valor: "1000.00", vencimento: "2026-09-30",
  status: "LIBERADA", data_pagamento: null, forma_pagamento: null, id_movimentacao: null,
  data_prevista_pagamento: "2026-09-25",
};

const loteRascunho: LotePagamento = {
  id: 7, numero: "L-2026-0001", id_conta_pagadora: 1, situacao: "RASCUNHO",
  data_programada: null, valor_total: "1000.00", id_anexo_comprovante: null,
  id_usuario: 1, id_usuario_envio: null, enviado_em: null, processado_em: null,
  criado_em: "2026-09-20T10:00:00Z", atualizado_em: null,
};

const loteEnviadoDetalhe: LoteDetalhe = {
  ...loteRascunho, situacao: "ENVIADO",
  enviado_em: "2026-09-20T12:00:00Z",
  parcelas: [
    { id: 1, id_lote: 7, id_parcela: 55, situacao: "PENDENTE", motivo_falha: null,
      criado_em: "2026-09-20T10:00:00Z", atualizado_em: null },
  ],
};

const retencoesDoDebito: RetencoesDebito = {
  valor_bruto: "1000.00", valor_liquido: "985.00",
  retencoes: [
    { id: 1, id_debito: 20, tipo: "IRRF", descricao: null, base_calculo: "1000.00",
      aliquota: "1.5", valor: "15.00", recolhido: false,
      data_recolhimento: null, documento_recolhimento: null,
      criado_em: "2026-09-20T10:00:00Z", atualizado_em: null },
  ],
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const contasListMock = vi.fn(() => Promise.resolve([contaPrincipal]));
const elegiveisMock = vi.fn(() => Promise.resolve([parcelaElegivel]));
const criarLoteMock = vi.fn(() => Promise.resolve(loteRascunho));
const listarLotesMock = vi.fn(() => Promise.resolve([loteRascunho]));
const obterLoteMock = vi.fn(() => Promise.resolve(loteEnviadoDetalhe));
const processarRetornoMock = vi.fn(() => Promise.resolve(loteEnviadoDetalhe));
const ordensListMock = vi.fn(() => Promise.resolve([]));

const retencoesListarMock = vi.fn(() => Promise.resolve(retencoesDoDebito));
const retencoesCriarMock = vi.fn(() =>
  Promise.resolve(retencoesDoDebito.retencoes[0]));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        cadastros: {
          ...actual.api.pagamentos.cadastros,
          contas: { ...actual.api.pagamentos.cadastros.contas, list: contasListMock },
        },
        ordens: {
          ...actual.api.pagamentos.ordens,
          list: ordensListMock,
          listaCsvUrl: () => "#", listaPdfUrl: () => "#",
        },
        lotes: {
          elegiveis: elegiveisMock,
          criar: criarLoteMock,
          listar: listarLotesMock,
          obter: obterLoteMock,
          adicionarParcela: vi.fn(),
          removerParcela: vi.fn(),
          cancelar: vi.fn(),
          programar: vi.fn(),
          enviar: vi.fn(),
          processarRetorno: processarRetornoMock,
          anexarComprovante: vi.fn(),
          comprovanteDownloadUrl: () => "#",
        },
        retencoes: {
          listarDoDebito: retencoesListarMock,
          criar: retencoesCriarMock,
          atualizar: vi.fn(),
          excluir: vi.fn(),
          recolher: vi.fn(),
          pendentes: vi.fn(() => Promise.resolve([])),
        },
        debitos: {
          ...actual.api.pagamentos.debitos,
          get: () => Promise.resolve({
            id: 20, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 1,
            id_fonte_recursos: 1, id_conta: null, id_conta_pagadora: 1, id_contrato: null,
            valor_total: "1000.00", competencia: "2026-09", numero_ne: null, numero_nf: null,
            criticidade: "MEDIA", urgente: false, justificativa_urgencia: null,
            descricao: "Serviço de teste", status: "AUTORIZADO",
            situacao_tramitacao: "AUTORIZADA", situacao_fila: "ELEGIVEL",
            situacao_pagamento: "PROGRAMADA", id_unidade: 1, versao: 1, lock_version: 1,
            id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
            liquidacao_confirmada: true, data_liquidacao: "2026-09-01",
            criado_em: "2026-09-01T10:00:00Z", atualizado_em: null,
            parcelas: [], historico: [],
          }),
          listarPedidosAjuste: () => Promise.resolve([]),
          listarVersoes: () => Promise.resolve([]),
          listarAnexos: () => Promise.resolve([]),
          posicaoDebito: () => Promise.reject(new actual.ApiError("Sem posição na fila.", 404)),
        },
        caixa: { painel: () => Promise.resolve([]) },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Tesouraria", is_super_usuario: false },
    perms: ["pagamento_pagar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_pagar",
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }),
}));

function renderComQueryClient(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{children}</QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Central da tesouraria
// ---------------------------------------------------------------------------

describe("Central da tesouraria — selecionar e criar lote", () => {
  it("lista contas, mostra elegíveis ao escolher uma e cria o lote com a seleção", async () => {
    const { default: TesourariaPage } = await import(
      "@/app/(app)/m/pagamentos/tesouraria/page"
    );
    renderComQueryClient(<TesourariaPage />);

    await waitFor(() => expect(contasListMock).toHaveBeenCalled());

    const selectConta = screen.getByLabelText(/conta pagadora/i);
    fireEvent.change(selectConta, { target: { value: "1" } });

    await waitFor(() => expect(elegiveisMock).toHaveBeenCalledWith(1));
    expect(await screen.findByText(/débito #20 · parcela 1/i)).toBeInTheDocument();

    const checkbox = screen.getByLabelText(/selecionar parcela 1 do débito #20/i);
    fireEvent.click(checkbox);

    const botaoCriar = await screen.findByRole("button", { name: /criar lote/i });
    fireEvent.click(botaoCriar);

    await waitFor(() =>
      expect(criarLoteMock).toHaveBeenCalledWith({ id_conta_pagadora: 1, parcela_ids: [55] }),
    );
  });

  it("aba Lotes lista o lote e o retorno exige motivo quando marcado como falhou", async () => {
    const { default: TesourariaPage } = await import(
      "@/app/(app)/m/pagamentos/tesouraria/page"
    );
    renderComQueryClient(<TesourariaPage />);

    fireEvent.click(screen.getByRole("tab", { name: /^lotes$/i }));
    await waitFor(() => expect(listarLotesMock).toHaveBeenCalled());

    const linhaLote = await screen.findByText(/L-2026-0001/i);
    fireEvent.click(linhaLote);

    await waitFor(() => expect(obterLoteMock).toHaveBeenCalledWith(7));

    // O lote mockado por `obter` está ENVIADO — aparece o passo de retorno.
    const botaoRegistrar = await screen.findByRole("button", { name: /registrar retorno/i });

    const selectResultado = screen.getByRole("combobox");
    fireEvent.change(selectResultado, { target: { value: "FALHOU" } });

    const inputMotivo = await screen.findByPlaceholderText(/motivo da falha/i);
    fireEvent.change(inputMotivo, { target: { value: "conta encerrada" } });

    fireEvent.click(botaoRegistrar);

    await waitFor(() =>
      expect(processarRetornoMock).toHaveBeenCalledWith(7, [
        { parcela_id: 55, resultado: "FALHOU", motivo_falha: "conta encerrada" },
      ]),
    );
  });
});

// ---------------------------------------------------------------------------
// Retenções no detalhe do débito
// ---------------------------------------------------------------------------

describe("Detalhe da solicitação — seção Retenções (F4)", () => {
  it("mostra bruto/líquido e a lista de retenções lançadas", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={20} />);

    await waitFor(() => expect(retencoesListarMock).toHaveBeenCalledWith(20));
    expect(await screen.findByText("IRRF")).toBeInTheDocument();
    const secao = screen.getByText("Retenções").closest("section") ?? document.body;
    expect(within(secao).getByText(/985,00/)).toBeInTheDocument();
  });

  it("abre o formulário e lança uma retenção nova", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={20} />);

    fireEvent.click(await screen.findByRole("button", { name: /lançar retenção/i }));
    const dialog = await screen.findByRole("heading", { name: "Lançar retenção" });
    expect(dialog).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/^base de cálculo/i), { target: { value: "1000.00" } });
    fireEvent.change(screen.getByLabelText(/^valor/i), { target: { value: "15.00" } });

    fireEvent.click(screen.getByRole("button", { name: /^lançar$/i }));

    await waitFor(() =>
      expect(retencoesCriarMock).toHaveBeenCalledWith(20, expect.objectContaining({
        tipo: "IRRF", base_calculo: "1000.00", valor: "15.00",
      })),
    );
  });
});

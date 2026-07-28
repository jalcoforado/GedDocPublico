import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConciliacaoPage from "@/app/(app)/pagamentos/conciliacao/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    pagamentos: {
      caixa: { painel: vi.fn(), extrato: vi.fn() },
      conciliacao: {
        extratos: vi.fn(),
        importar: vi.fn(),
        lancamentos: vi.fn(),
        sugestoes: vi.fn(),
        baixaAutomatica: vi.fn(),
        conciliar: vi.fn(),
      },
    },
  },
}));

const toastSuccess = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: vi.fn(), info: vi.fn() }),
}));
const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));

const painelMock = api.pagamentos.caixa.painel as ReturnType<typeof vi.fn>;
const movsMock = api.pagamentos.caixa.extrato as ReturnType<typeof vi.fn>;
const extratosMock = api.pagamentos.conciliacao.extratos as ReturnType<typeof vi.fn>;
const lancamentosMock = api.pagamentos.conciliacao.lancamentos as ReturnType<typeof vi.fn>;
const sugestoesMock = api.pagamentos.conciliacao.sugestoes as ReturnType<typeof vi.fn>;
const baixaAutoMock = api.pagamentos.conciliacao.baixaAutomatica as ReturnType<typeof vi.fn>;
const conciliarMock = api.pagamentos.conciliacao.conciliar as ReturnType<typeof vi.fn>;

const CONTA = {
  id_conta: 7, nome: "Conta Movimento", banco: "BB", grupo_despesa: "CUSTEIO",
  saldo_inicial: "0", total_entradas: "0", total_saidas: "0", saldo_atual: "0",
  comprometido: "0", disponivel: "0", saldo_minimo_alerta: "0", abaixo_minimo: false,
};

const EXTRATO = {
  id: 3, id_conta: 7, nome_arquivo: "extrato-julho.csv", formato: "CSV",
  periodo_inicio: "2026-07-01", periodo_fim: "2026-07-31",
  status_processamento: "PROCESSADO", qtd_lancamentos: 2,
  importado_em: "2026-07-28T10:00:00",
};

const LANC_PENDENTE = {
  id: 11, id_extrato: 3, data: "2026-07-10", historico: "TARIFA MANUTENCAO",
  documento: "TAR1", favorecido: "BANCO", valor: "89.90",
  tipo: "DEBITO" as const, conciliado: false,
};

const LANC_CONCILIADO = {
  id: 12, id_extrato: 3, data: "2026-07-11", historico: "PAGAMENTO FORNECEDOR",
  documento: "DOC1", favorecido: "ACME", valor: "1000.00",
  tipo: "DEBITO" as const, conciliado: true,
};

const SUGESTAO_EXATA = {
  id_lancamento: 12, lancamento_data: "2026-07-11",
  lancamento_historico: "PAGAMENTO FORNECEDOR", lancamento_valor: "1000.00",
  id_movimentacao: 55, id_parcela: 9, id_debito: 4, nome_fornecedor: "ACME Ltda",
  movimentacao_data: "2026-07-11", movimentacao_valor: "1000.00",
  tipo_correspondencia: "EXATA" as const,
};

const SUGESTAO_PROVAVEL = {
  ...SUGESTAO_EXATA,
  id_lancamento: 13, id_movimentacao: 56,
  movimentacao_data: "2026-07-09",
  tipo_correspondencia: "PROVAVEL" as const,
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ConciliacaoPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  painelMock.mockResolvedValue([CONTA]);
  movsMock.mockResolvedValue([]);
  extratosMock.mockResolvedValue([EXTRATO]);
  lancamentosMock.mockResolvedValue([LANC_PENDENTE, LANC_CONCILIADO]);
  sugestoesMock.mockResolvedValue([SUGESTAO_EXATA, SUGESTAO_PROVAVEL]);
  baixaAutoMock.mockResolvedValue({ baixas: 1 });
  conciliarMock.mockResolvedValue({ id: 1 });
});

describe("Conciliação bancária", () => {
  it("lista os extratos importados com a conta correspondente", async () => {
    renderPage();
    const celula = await screen.findByText("extrato-julho.csv");
    // Escopado à linha: "Conta Movimento" também aparece na <option> do filtro.
    const linha = celula.closest("tr");
    expect(linha).not.toBeNull();
    expect(within(linha!).getByText("Conta Movimento")).toBeInTheDocument();
  });

  it("só carrega lançamentos e sugestões depois de escolher um extrato", async () => {
    renderPage();
    await screen.findByText("extrato-julho.csv");
    expect(lancamentosMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("extrato-julho.csv"));

    await waitFor(() => expect(lancamentosMock).toHaveBeenCalledWith(3));
    expect(sugestoesMock).toHaveBeenCalledWith(3);
  });

  it("distingue correspondência exata de provável", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("extrato-julho.csv"));

    expect(await screen.findByText("Exata")).toBeInTheDocument();
    expect(screen.getByText("Provável")).toBeInTheDocument();
  });

  it("a baixa automática conta só as exatas e pede confirmação", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("extrato-julho.csv"));

    // Duas sugestões, uma exata — o botão não pode prometer as duas.
    const botao = await screen.findByRole("button", { name: /Baixar 1 exata/i });
    fireEvent.click(botao);

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    await waitFor(() => expect(baixaAutoMock).toHaveBeenCalledWith(3));
  });

  it("oferece conciliação manual apenas para lançamento pendente", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("extrato-julho.csv"));

    await screen.findByText("TARIFA MANUTENCAO");
    // Um pendente e um conciliado na lista → um único botão de manual.
    const botoes = screen.getAllByRole("button", { name: /Conciliar manualmente/i });
    expect(botoes).toHaveLength(1);
  });

  it("concilia a sugestão ligando lançamento e movimentação", async () => {
    renderPage();
    fireEvent.click(await screen.findByText("extrato-julho.csv"));

    const botoes = await screen.findAllByRole("button", { name: /^Conciliar$/i });
    fireEvent.click(botoes[0]);

    await waitFor(() =>
      expect(conciliarMock).toHaveBeenCalledWith({
        id_lancamento: 12,
        id_movimentacao: 55,
      }),
    );
  });
});

/**
 * Task 7 (F2 pagamentos): pendências de ajuste e versões no detalhe, e o
 * bloco de pendências na caixa de trabalho.
 *
 * Duas propriedades do produto ficam cobertas aqui:
 *  1. pedido de ajuste ABERTO bloqueia o reenvio ("Reenviar para análise")
 *     — sem isso a unidade reenviaria e o backend devolveria 409 sem
 *     explicação nenhuma na tela;
 *  2. `minhaFila().pendencias_ajuste` aparece na caixa de trabalho, linkando
 *     para o detalhe do débito — sem isso o responsável só descobre que tem
 *     um ajuste para responder abrindo cada solicitação manualmente.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  AnexoDebitoOut,
  DebitoOut,
  MinhaFila,
  PedidoAjuste,
} from "@/lib/api";

const debitoBase: DebitoOut = {
  id: 1,
  id_fornecedor: 10,
  nome_fornecedor: "Fornecedor Teste",
  id_natureza: 1,
  id_fonte_recursos: 1,
  id_conta: null,
  id_conta_pagadora: null,
  id_contrato: null,
  valor_total: "1000.00",
  competencia: "2026-08",
  numero_ne: null,
  numero_nf: null,
  criticidade: "normal",
  urgente: false,
  justificativa_urgencia: null,
  descricao: "Despesa de teste",
  status: "ativo" as any,
  id_usuario_solicitante: 1,
  liquidacao_confirmada: false,
  data_liquidacao: null,
  criado_em: "2026-08-01T10:00:00Z",
  atualizado_em: null,
  situacao_tramitacao: "AJUSTE_GESTOR",
  situacao_fila: "NAO_REGISTRADA",
  situacao_pagamento: "NAO_INICIADA",
  id_unidade: 1,
  versao: 1,
  lock_version: 3,
  id_gestor_decisor: null,
  id_validador: null,
};

const pedidoAberto: PedidoAjuste = {
  id: 55,
  id_debito: 1,
  versao_debito: 1,
  etapa_solicitante: "GESTOR",
  id_usuario_solicitante: 2,
  motivo: "Falta anexar a nota fiscal",
  descricao: "A nota fiscal não confere com o valor solicitado.",
  transacao_responsavel: "pagamento_solicitar",
  tipo: "NAO_MATERIAL",
  prazo: null,
  campos_relacionados: null,
  situacao: "ABERTO",
  resposta: null,
  id_usuario_resposta: null,
  respondido_em: null,
  resolvido_em: null,
  criado_em: "2026-08-10T09:00:00Z",
};

const getMock = vi.fn(() =>
  Promise.resolve({ ...debitoBase, parcelas: [], historico: [] }),
);
const listarPedidosMock = vi.fn(() => Promise.resolve([pedidoAberto]));
const listarVersoesMock = vi.fn(() => Promise.resolve([]));
const responderAjusteMock = vi.fn();
const solicitarAjusteMock = vi.fn();
const criarPedidoAjusteMock = vi.fn();
const responderPedidoAjusteMock = vi.fn();
const cancelarPedidoAjusteMock = vi.fn();
const listarAnexosMock = vi.fn(() => Promise.resolve([] as AnexoDebitoOut[]));
const uploadAnexoMock = vi.fn(() =>
  Promise.resolve({
    id: 1,
    id_anexo: 900,
    nome: "nota.pdf",
    tamanho: 2048,
    tipo: "pdf",
    versao_debito: 1,
    id_pedido_ajuste: null,
    id_usuario: 1,
    criado_em: "2026-08-11T09:00:00Z",
  }),
);
const removerAnexoMock = vi.fn(() => Promise.resolve());
const anexoDownloadUrlMock = vi.fn((anexoDebitoId: number) => `/api/v2/pagamentos/anexos-debito/${anexoDebitoId}/download`);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      pagamentos: {
        debitos: {
          get: getMock,
          listarPedidosAjuste: listarPedidosMock,
          listarVersoes: listarVersoesMock,
          responderAjuste: responderAjusteMock,
          solicitarAjuste: solicitarAjusteMock,
          criarPedidoAjuste: criarPedidoAjusteMock,
          responderPedidoAjuste: responderPedidoAjusteMock,
          cancelarPedidoAjuste: cancelarPedidoAjusteMock,
          confirmarLiquidacao: vi.fn(),
          listarAnexos: listarAnexosMock,
          uploadAnexo: uploadAnexoMock,
          removerAnexo: removerAnexoMock,
          anexoDownloadUrl: anexoDownloadUrlMock,
        },
        caixa: { painel: () => Promise.resolve([]) },
        minhaFila: () =>
          Promise.resolve({
            solicitar: [],
            validar: [],
            encaminhar: [],
            autorizar: [],
            liberar: [],
            pagar: [],
            pendencias_ajuste: [
              {
                id_pedido: 55,
                id_debito: 1,
                descricao_debito: "Despesa de teste",
                motivo: "Falta anexar a nota fiscal",
                prazo: null,
                criado_em: "2026-08-10T09:00:00Z",
                etapa_solicitante: "GESTOR",
              },
            ],
          } satisfies MinhaFila),
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Solicitante", is_super_usuario: false },
    perms: ["pagamento_solicitar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_solicitar",
  }),
}));

const toastErrorMock = vi.fn();

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: toastErrorMock, info: vi.fn(), warning: vi.fn() }),
}));

function renderComQueryClient(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return { client, ...render(<QueryClientProvider client={client}>{children}</QueryClientProvider>) };
}

describe("Detalhe da solicitação — pendências de ajuste (F2)", () => {
  it("pedido ABERTO bloqueia o botão de reenvio, com o motivo explicado", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    // O motivo também aparece no <option> do seletor "Vincular a pedido de
    // ajuste" (Task 8) — escopo para o texto do card, não qualquer ocorrência.
    await waitFor(() =>
      expect(
        screen.getByText(/falta anexar a nota fiscal/i, { selector: "div" }),
      ).toBeInTheDocument(),
    );

    // Situação do pedido é ícone + texto, não só cor.
    expect(screen.getByText("Aguardando resposta")).toBeInTheDocument();

    const reenviar = screen.getByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).toBeDisabled();
    expect(reenviar).toHaveAttribute("title", expect.stringMatching(/pedido de ajuste em aberto/i));
  });

  it("libera o reenvio quando não há mais pedido ABERTO", async () => {
    listarPedidosMock.mockResolvedValueOnce([
      { ...pedidoAberto, situacao: "RESPONDIDO", resposta: "Nota fiscal anexada." },
    ]);
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    await waitFor(() => expect(screen.getByText("Respondido")).toBeInTheDocument());
    const reenviar = screen.getByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).not.toBeDisabled();
  });

  it("409 no reenvio (pedido ABERTO surgiu entre o carregamento e o clique): mostra o conflito, recarrega os dados e NÃO repete a mutation", async () => {
    // Tela abriu com o único pedido já RESPONDIDO — botão liberado — mas o
    // backend recusa com 409 no exato formato que `lib/api.ts` lança para
    // qualquer resposta HTTP não-ok (ApiError real, não um objeto solto).
    listarPedidosMock.mockResolvedValueOnce([
      { ...pedidoAberto, situacao: "RESPONDIDO", resposta: "Nota fiscal anexada." },
    ]);
    const { ApiError } = await import("@/lib/api");
    responderAjusteMock.mockRejectedValueOnce(
      new ApiError(
        "Há pedido(s) de ajuste ainda não respondido(s): #55: Falta anexar a nota fiscal.",
        409,
      ),
    );

    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    const { client } = renderComQueryClient(<DetalheDebitoContent id={1} />);
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const reenviar = await screen.findByRole("button", { name: /reenviar para análise/i });
    expect(reenviar).not.toBeDisabled();

    fireEvent.click(reenviar);

    // Mensagem de conflito visível ao usuário (via toast).
    await waitFor(() =>
      expect(toastErrorMock).toHaveBeenCalledWith(
        expect.stringMatching(/pedido de ajuste em aberto/i),
      ),
    );

    // Dados recarregados: as três queries do detalhe são invalidadas.
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-debito", 1] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-pedidos-ajuste", 1] }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ["pag-versoes", 1] }),
    );

    // A mutation de reenvio NÃO é repetida automaticamente após o 409.
    expect(responderAjusteMock).toHaveBeenCalledTimes(1);
  });
});

describe("Detalhe da solicitação — documentos do débito (Task 8)", () => {
  it("lista os documentos anexados com nome, tamanho, quem e versão", async () => {
    listarAnexosMock.mockResolvedValueOnce([
      {
        id: 7,
        id_anexo: 900,
        nome: "nota-fiscal.pdf",
        tamanho: 20480,
        tipo: "pdf",
        versao_debito: 1,
        id_pedido_ajuste: null,
        id_usuario: 3,
        criado_em: "2026-08-11T14:30:00Z",
      },
    ]);
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    await waitFor(() => expect(screen.getByText("nota-fiscal.pdf")).toBeInTheDocument());
    expect(screen.getByText("20.0 KB")).toBeInTheDocument();
    expect(screen.getByText("Usuário #3")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /baixar nota-fiscal.pdf/i })).toHaveAttribute(
      "href",
      "/api/v2/pagamentos/anexos-debito/7/download",
    );
  });

  it("envia documento vinculando automaticamente o pedido de ajuste aberto que o usuário pode responder", async () => {
    listarAnexosMock.mockResolvedValueOnce([]);
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    // Espera o pedido ABERTO carregar — é ele que popula o seletor de vínculo.
    await waitFor(() =>
      expect(screen.getByText("Vincular a pedido de ajuste")).toBeInTheDocument(),
    );

    const fileInput = screen.getByLabelText("Arquivo") as HTMLInputElement;
    const arquivo = new File(["conteudo"], "nota.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [arquivo] } });

    const enviar = screen.getByRole("button", { name: /enviar documento/i });
    expect(enviar).not.toBeDisabled();
    fireEvent.click(enviar);

    await waitFor(() =>
      expect(uploadAnexoMock).toHaveBeenCalledWith(1, arquivo, undefined, 55),
    );
  });

  it("remoção mostra resumo de impacto antes de confirmar, e só remove no clique de confirmação", async () => {
    listarAnexosMock.mockResolvedValueOnce([
      {
        id: 7,
        id_anexo: 900,
        nome: "nota-fiscal.pdf",
        tamanho: 20480,
        tipo: "pdf",
        versao_debito: 1,
        id_pedido_ajuste: null,
        id_usuario: 3,
        criado_em: "2026-08-11T14:30:00Z",
      },
    ]);
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={1} />);

    const removerLinha = await screen.findByRole("button", { name: /remover nota-fiscal.pdf/i });
    fireEvent.click(removerLinha);

    expect(removerAnexoMock).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Remover documento" })).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/será removido desta solicitação e deixará de aparecer/i),
    ).toBeInTheDocument();

    const confirmar = screen.getByRole("button", { name: /^remover documento$/i });
    fireEvent.click(confirmar);

    await waitFor(() => expect(removerAnexoMock).toHaveBeenCalledWith(1, 7));
  });
});

describe("Caixa de pagamentos — pendências para você responder (F2)", () => {
  it("lista a pendência de ajuste e linka para o detalhe do débito", async () => {
    const { default: PagamentosHomePage } = await import("@/app/(app)/m/pagamentos/page");
    renderComQueryClient(<PagamentosHomePage />);

    await waitFor(() =>
      expect(screen.getByText("Pendências para você responder")).toBeInTheDocument(),
    );
    const link = await screen.findByRole("link", {
      name: /despesa de teste.*falta anexar a nota fiscal/i,
    });
    expect(link).toHaveAttribute("href", "/m/pagamentos/solicitacoes/1");
  });
});

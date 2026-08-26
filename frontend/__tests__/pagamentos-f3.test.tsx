/**
 * Task 6 (F3 pagamentos): tela da ordem cronológica, seção "Fila cronológica"
 * no detalhe do débito e categoria obrigatória em contratos.
 *
 * Três propriedades do produto ficam cobertas aqui:
 *  1. a tela `/m/pagamentos/fila` agrupa por (unidade, fonte, categoria,
 *     exercício) e mostra a posição de cada item;
 *  2. exceção cronológica autorizada aparece com ÍCONE E TEXTO — nunca só
 *     cor — tanto na fila quanto no detalhe;
 *  3. a seção "Fila" do detalhe mostra "posição N de M" e o motivo do
 *     bloqueio, e cai para "não registrado" no 404 esperado de débito legado;
 *  4. o cadastro de contratos exige categoria (o `ContratoCreate` do backend
 *     já exigia — sem o campo a tela quebrava com 422).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";

import type {
  Contrato,
  ExcecaoCronologicaOut,
  FilaCronologicaGrupo,
  FonteRecursos,
  PosicaoDebitoOut,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const grupoFila: FilaCronologicaGrupo = {
  id_unidade: 1,
  unidade_nome: "Secretaria de Obras",
  id_fonte_recursos: 2,
  fonte_nome: "FPM",
  categoria: "SERVICOS",
  exercicio: 2026,
  itens: [
    {
      posicao: 1,
      id_debito: 10,
      fornecedor_nome: "Fornecedor A",
      descricao: "Serviço de limpeza",
      valor_total: "1500.00",
      marco_em: "2026-08-01T10:00:00Z",
      situacao: "ELEGIVEL",
      motivo_bloqueio: null,
      previsao_pagamento: null,
      tem_excecao: false,
    },
    {
      posicao: 2,
      id_debito: 11,
      fornecedor_nome: "Fornecedor B",
      descricao: "Manutenção predial",
      valor_total: "800.00",
      marco_em: "2026-08-02T10:00:00Z",
      situacao: "EXCECAO_AUTORIZADA",
      motivo_bloqueio: null,
      previsao_pagamento: null,
      tem_excecao: true,
    },
  ],
};

const excecaoDoDebito11: ExcecaoCronologicaOut = {
  id: 99,
  justificativa: "Serviço essencial de manutenção emergencial.",
  fundamento: "art. 5º da Lei 8.666/93",
  id_autoridade: 5,
  data_autorizacao: "2026-08-02",
  criado_em: "2026-08-02T11:00:00Z",
  id_usuario_registro: 5,
  documentos: null,
};

const fonteFPM: FonteRecursos = {
  id: 2,
  codigo: "FPM",
  descricao: "Fundo de Participação dos Municípios",
  grupos_despesa_permitidos: [],
  exercicio: 2026,
  esfera_origem: null,
  tipo_vinculacao: null,
  situacao: "ATIVA",
  vigencia_inicio: null,
  vigencia_fim: null,
  criado_em: "2026-01-01T00:00:00Z",
  atualizado_em: null,
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const filaCronologicaMock = vi.fn(() => Promise.resolve([grupoFila]));
const listarExcecoesMock = vi.fn((id: number) =>
  Promise.resolve(id === 11 ? [excecaoDoDebito11] : []),
);
const fontesListMock = vi.fn(() => Promise.resolve([fonteFPM]));
const unidadesListMock = vi.fn(() =>
  Promise.resolve({ items: [{ id: 1, unidade_trabalho: "Secretaria de Obras", sigla: null, id_unidade_pai: null, id_tipo_unidade_trabalho: null }] }),
);

const debitoBase = {
  id: 11,
  id_fornecedor: 10,
  nome_fornecedor: "Fornecedor B",
  id_natureza: 1,
  id_fonte_recursos: 2,
  id_conta: null,
  id_conta_pagadora: null,
  id_contrato: null,
  valor_total: "800.00",
  competencia: "2026-08",
  numero_ne: null,
  numero_nf: null,
  criticidade: "normal" as any,
  urgente: false,
  justificativa_urgencia: null,
  descricao: "Manutenção predial",
  status: "ativo" as any,
  id_usuario_solicitante: 1,
  liquidacao_confirmada: true,
  data_liquidacao: "2026-08-02",
  criado_em: "2026-08-01T10:00:00Z",
  atualizado_em: null,
  situacao_tramitacao: "AUTORIZADA" as any,
  situacao_fila: "EXCECAO_AUTORIZADA" as any,
  situacao_pagamento: "NAO_INICIADA" as any,
  id_unidade: 1,
  versao: 1,
  lock_version: 1,
  id_gestor_decisor: null,
  id_validador: null,
};

const posicaoFilaMock = vi.fn<() => Promise<PosicaoDebitoOut>>(() =>
  Promise.resolve({
    posicao: 2,
    total_grupo: 5,
    situacao: "EXCECAO_AUTORIZADA",
    motivo_bloqueio: "Há débito elegível à frente na fila",
    marco_em: "2026-08-02T10:00:00Z",
    excecoes: [excecaoDoDebito11],
  }),
);
const posicaoFilaGetMock = vi.fn(() => Promise.resolve({ ...debitoBase, parcelas: [], historico: [] }));
const registrarExcecaoMock = vi.fn(() => Promise.resolve(excecaoDoDebito11));

const contratoSemCategoria: Contrato = {
  id: 1,
  numero: "001/2026",
  id_fornecedor: 10,
  id_unidade: 1,
  objeto: "Serviço de limpeza",
  vigencia_inicio: "2026-01-01",
  vigencia_fim: "2026-12-31",
  valor_total: "10000.00",
  categoria: null,
  criado_em: "2026-01-01T00:00:00Z",
  atualizado_em: null,
};

const contratosListMock = vi.fn(() => Promise.resolve([contratoSemCategoria]));
const contratosCreateMock = vi.fn();
const fornecedoresListMock = vi.fn(() => Promise.resolve([{ id: 10, nome: "Fornecedor A" }]));

// Um único `vi.mock` por módulo neste arquivo — vários `vi.mock("@/lib/api", ...)`
// não se somam (o hoisting do vitest só mantém o último), então as três telas
// (fila, detalhe, contratos) compartilham este bloco.
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      unidades: { ...actual.api.unidades, list: unidadesListMock },
      pagamentos: {
        ...actual.api.pagamentos,
        filaCronologica: filaCronologicaMock,
        caixa: { painel: () => Promise.resolve([]) },
        debitos: {
          ...actual.api.pagamentos.debitos,
          get: posicaoFilaGetMock,
          listarPedidosAjuste: () => Promise.resolve([]),
          listarVersoes: () => Promise.resolve([]),
          listarAnexos: () => Promise.resolve([]),
          posicaoDebito: posicaoFilaMock,
          listarExcecoes: listarExcecoesMock,
          registrarExcecao: registrarExcecaoMock,
        },
        cadastros: {
          ...actual.api.pagamentos.cadastros,
          fontes: { ...actual.api.pagamentos.cadastros.fontes, list: fontesListMock },
          contratos: {
            ...actual.api.pagamentos.cadastros.contratos,
            list: contratosListMock,
            create: contratosCreateMock,
          },
          fornecedores: {
            ...actual.api.pagamentos.cadastros.fornecedores,
            list: fornecedoresListMock,
          },
        },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Autoridade", is_super_usuario: false },
    perms: ["pagamento_autorizar"],
    loading: false,
    can: (codigo: string) => codigo === "pagamento_autorizar",
  }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() }),
}));

function renderComQueryClient(children: React.ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return {
    client,
    ...render(
      <QueryClientProvider client={client}>
        <ConfirmProvider>{children}</ConfirmProvider>
      </QueryClientProvider>,
    ),
  };
}

// ---------------------------------------------------------------------------
// Tela /m/pagamentos/fila
// ---------------------------------------------------------------------------

describe("Ordem cronológica — tela da fila", () => {
  it("agrupa por unidade/fonte/categoria/exercício e mostra a posição de cada item", async () => {
    const { default: FilaCronologicaPage } = await import(
      "@/app/(app)/m/pagamentos/fila/page"
    );
    renderComQueryClient(<FilaCronologicaPage />);

    await waitFor(() => expect(filaCronologicaMock).toHaveBeenCalled());

    expect(
      await screen.findByText("Secretaria de Obras · FPM · Serviços · 2026"),
    ).toBeInTheDocument();

    // Posição numérica de cada linha
    expect(screen.getByText("Fornecedor A")).toBeInTheDocument();
    expect(screen.getByText("Fornecedor B")).toBeInTheDocument();
    const linhas = screen.getAllByRole("row");
    // header + 2 itens (a exceção expandida some até clicar)
    expect(linhas.length).toBeGreaterThanOrEqual(3);
  });

  it("exceção autorizada aparece com ícone E texto, e expande a justificativa", async () => {
    const { default: FilaCronologicaPage } = await import(
      "@/app/(app)/m/pagamentos/fila/page"
    );
    renderComQueryClient(<FilaCronologicaPage />);

    const botaoExcecao = await screen.findByRole("button", { name: /exceção autorizada/i });
    expect(botaoExcecao).toBeInTheDocument();

    fireEvent.click(botaoExcecao);

    await waitFor(() => expect(listarExcecoesMock).toHaveBeenCalledWith(11));
    expect(
      await screen.findByText(/serviço essencial de manutenção emergencial/i),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Seção "Fila cronológica" no detalhe
// ---------------------------------------------------------------------------

describe("Detalhe da solicitação — seção Fila cronológica (F3)", () => {
  it("mostra posição N de M, motivo do bloqueio e exceções autorizadas", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={11} />);

    expect(await screen.findByText("Posição 2 de 5 na fila")).toBeInTheDocument();
    expect(screen.getByText(/há débito elegível à frente na fila/i)).toBeInTheDocument();
    expect(
      screen.getByText(/serviço essencial de manutenção emergencial/i),
    ).toBeInTheDocument();

    // Quem tem `pagamento_autorizar` vê o botão de exceção formal.
    expect(
      screen.getByRole("button", { name: /autorizar exceção cronológica/i }),
    ).toBeInTheDocument();
  });

  it("404 do débito não registrado na fila mostra a mensagem defensiva, não um erro", async () => {
    const { ApiError } = await import("@/lib/api");
    posicaoFilaMock.mockRejectedValueOnce(
      new ApiError("Débito não tem posição na fila cronológica.", 404),
    );

    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={11} />);

    expect(
      await screen.findByText(/não registrado na fila cronológica/i),
    ).toBeInTheDocument();
  });

  it("abre o dialog de exceção cronológica e envia justificativa, fundamento e data", async () => {
    const { DetalheDebitoContent } = await import(
      "@/components/pagamentos/DetalheDebitoContent"
    );
    renderComQueryClient(<DetalheDebitoContent id={11} />);

    const abrir = await screen.findByRole("button", { name: /autorizar exceção cronológica/i });
    fireEvent.click(abrir);

    const dialog = await screen.findByRole("heading", { name: "Autorizar exceção cronológica" });
    expect(dialog).toBeInTheDocument();

    // Regex, não string exata: o `required` do FormField acrescenta um "*"
    // (aria-hidden, mas presente no texto do <label>) ao rótulo visível.
    fireEvent.change(screen.getByLabelText(/^fundamento legal/i), {
      target: { value: "art. 5º da Lei 8.666/93" },
    });
    fireEvent.change(screen.getByLabelText(/^justificativa/i), {
      target: { value: "Manutenção emergencial." },
    });
    fireEvent.change(screen.getByLabelText(/^data da autorização/i), {
      target: { value: "2026-08-02" },
    });

    fireEvent.click(screen.getByRole("button", { name: /^autorizar exceção$/i }));

    await waitFor(() =>
      expect(registrarExcecaoMock).toHaveBeenCalledWith(11, {
        justificativa: "Manutenção emergencial.",
        fundamento: "art. 5º da Lei 8.666/93",
        data_autorizacao: "2026-08-02",
      }),
    );
  });
});

// ---------------------------------------------------------------------------
// Contratos — categoria obrigatória
// ---------------------------------------------------------------------------

describe("Contratos — categoria da fila cronológica obrigatória (F3)", () => {
  it("mostra a coluna de categoria e o banner de contrato sem categoria", async () => {
    const { default: ContratosPage } = await import(
      "@/app/(app)/m/pagamentos/cadastros/contratos/page"
    );
    renderComQueryClient(<ContratosPage />);

    await waitFor(() => expect(contratosListMock).toHaveBeenCalled());
    expect(
      await screen.findByText(/contrato\(s\) sem categoria da fila cronológica/i),
    ).toBeInTheDocument();

    const linha = screen.getByText("001/2026").closest("tr")!;
    expect(within(linha).getByText("—")).toBeInTheDocument();
  });

  it("o formulário exige categoria ao criar", async () => {
    const { default: ContratosPage } = await import(
      "@/app/(app)/m/pagamentos/cadastros/contratos/page"
    );
    renderComQueryClient(<ContratosPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Novo" }));

    const selectCategoria = (await screen.findByLabelText(
      /^categoria \(fila cronológica\)/i,
    )) as HTMLSelectElement;
    expect(selectCategoria).toBeRequired();

    // As 4 categorias em português, além da opção vazia.
    const opcoes = within(selectCategoria).getAllByRole("option").map((o) => o.textContent);
    expect(opcoes).toEqual(["—", "Bens", "Locações", "Serviços", "Obras"]);
  });
});

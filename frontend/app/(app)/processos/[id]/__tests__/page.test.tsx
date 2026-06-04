import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProcessoDetailPage from "@/app/(app)/processos/[id]/page";
import type { ProcessoDetail } from "@/lib/api";

// =============================================================================
// Mocks de dependencias externas
// =============================================================================

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    api: {
      processos: {
        get: vi.fn(),
        checklistDocumentos: vi.fn(),
        listarComplementacoes: vi.fn(),
        solicitarComplementacao: vi.fn(),
        cancelarComplementacao: vi.fn(),
      },
      jobs: { processoCompleto: vi.fn() },
    },
    processoCapaUrl: vi.fn((id: number, inline = true) =>
      `/api/v2/processos/${id}/capa.pdf?inline=${inline}`,
    ),
    etiquetaUnicaUrl: vi.fn((id: number, inline = true) =>
      `/api/v2/processos/${id}/etiqueta.pdf?inline=${inline}`,
    ),
    etiquetaDuplaUrl: vi.fn((id: number, inline = true) =>
      `/api/v2/processos/${id}/etiqueta-dupla.pdf?inline=${inline}`,
    ),
    processoCompletoUrl: vi.fn((id: number, inline = true) =>
      `/api/v2/processos/${id}/completo.pdf?inline=${inline}`,
    ),
    comprovanteUrl: vi.fn(() => "/comprovante"),
  };
});

// Tab atual controlavel: testes ajustam currentTabParam pra mudar a
// aba renderizada (o componente le `searchParams.get("tab")`).
let currentTabParam: string | null = null;
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "42" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () =>
    new URLSearchParams(currentTabParam ? `tab=${currentTabParam}` : ""),
}));

// Auth com TODAS as permissoes — depois testes especificos sobrescrevem.
const canMock = vi.fn(() => true);
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: canMock, user: { id: 1, nome: "Admin" } }),
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

// Stubs leves para subarvores grandes — checamos so que renderizam.
vi.mock("@/components/AcoesProcesso", () => ({
  AcoesProcesso: () => <div data-testid="acoes-processo" />,
}));
vi.mock("@/components/AnexosProcesso", () => ({
  AnexosProcesso: () => <div data-testid="anexos-processo" />,
}));
vi.mock("@/components/ProcessoTrail", () => ({
  ProcessoTrail: () => <div data-testid="processo-trail" />,
}));
vi.mock("@/components/ProcessoWorkflowPanel", () => ({
  ProcessoWorkflowPanel: () => <div data-testid="processo-workflow" />,
}));
vi.mock("@/components/ProcessoApensados", () => ({
  ProcessoApensados: () => <div data-testid="apensados" />,
}));
vi.mock("@/components/ProcessoVolumes", () => ({
  ProcessoVolumes: () => <div data-testid="volumes" />,
}));
vi.mock("@/components/AssinaturasProcesso", () => ({
  AssinaturasProcesso: () => <div data-testid="assinaturas" />,
}));
vi.mock("@/components/ClassificarSigiloDialog", () => ({
  ClassificarSigiloDialog: () => (
    <div data-testid="classificar-sigilo-dialog" />
  ),
}));
vi.mock("@/components/PdfViewerDialog", () => ({
  PdfViewerDialog: ({
    title,
    src,
    downloadUrl,
  }: {
    title: string;
    src: string;
    downloadUrl: string;
  }) => (
    <div data-testid="pdf-viewer-dialog">
      <span data-testid="pdf-viewer-title">{title}</span>
      <span data-testid="pdf-viewer-src">{src}</span>
      <span data-testid="pdf-viewer-download">{downloadUrl}</span>
    </div>
  ),
}));
vi.mock("@/components/SolicitarComplementacaoDialog", () => ({
  SolicitarComplementacaoDialog: () => null,
}));
vi.mock("@/components/CancelarComplementacaoDialog", () => ({
  CancelarComplementacaoDialog: () => null,
}));
vi.mock("@/components/ComplementacoesHistoricoLista", () => ({
  ComplementacoesHistoricoLista: () => null,
}));
vi.mock("@/components/ComplementacaoAbertaCard", () => ({
  ComplementacaoAbertaCard: () => null,
}));
vi.mock("@/components/ui/rich-text-editor", () => ({
  RichTextView: ({ html }: { html: string }) => (
    <div data-testid="rich-text-view">{html}</div>
  ),
}));

// Imports DEPOIS dos mocks — pra obter os mocks resolvidos.
import { api, processoCapaUrl, etiquetaUnicaUrl, etiquetaDuplaUrl,
         processoCompletoUrl } from "@/lib/api";

const getMock = api.processos.get as ReturnType<typeof vi.fn>;
const checklistMock = api.processos.checklistDocumentos as ReturnType<typeof vi.fn>;
const complementacoesMock = api.processos.listarComplementacoes as ReturnType<typeof vi.fn>;

// =============================================================================
// Fixtures
// =============================================================================

function processo(overrides: Partial<ProcessoDetail> = {}): ProcessoDetail {
  return {
    id: 42,
    numero_processo: "P000042/2026",
    nup: null,
    numero_origem: null,
    data_hora_abertura: "2026-05-01T12:00:00",
    ativo: true,
    publico: true,
    nivel_sigilo: "ostensivo",
    externo: false,
    assunto: "Iluminação pública",
    tipo_processo: "Manifestação",
    manifestante: "João da Silva",
    manifestante_cpf_cnpj: "111.222.333-44",
    unidade_proprietaria: "Protocolo Geral",
    local_atual: "Protocolo Geral",
    observacao: null,
    corpo: "Solicito reparo da iluminação.",
    virtual: false,
    migrado: false,
    id_processo_pai: null,
    sigilo_fundamento_legal: null,
    sigilo_autoridade: null,
    sigilo_prazo_anos: null,
    sigilo_data_classificacao: null,
    sigilo_data_desclassificacao: null,
    movimentacoes: [],
    anexos: [],
    prazo: {
      status: "sem_prazo",
      prazo_servico_dias_snapshot: null,
      prazo_previsto_em: null,
      dias_restantes: null,
      dias_atraso: null,
      concluido_em: null,
      origem: null,
    },
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ProcessoDetailPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  canMock.mockReturnValue(true);
  currentTabParam = null; // default = aba "visao"
  checklistMock.mockResolvedValue({
    id_processo: 42,
    id_servico: 1,
    status_documental: "completo",
    obrigatorios_total: 0,
    obrigatorios_enviados: 0,
    itens: [],
    complementacao_aberta: null,
  });
  complementacoesMock.mockResolvedValue([]);
});

// =============================================================================
// PageHeader actions — D-PRINT-MENU
// =============================================================================

describe("Detalhe servidor — PageHeader", () => {
  it("renderiza badge 'Em tramitação' quando processo ativo (helper Fase A)", async () => {
    getMock.mockResolvedValue(processo({ ativo: true }));
    renderPage();
    expect(
      await screen.findByText(/^Em tramitação$/i),
    ).toBeInTheDocument();
  });

  it("renderiza badge 'Encerrado' quando processo inativo", async () => {
    getMock.mockResolvedValue(processo({ ativo: false }));
    renderPage();
    expect(await screen.findByText(/^Encerrado$/i)).toBeInTheDocument();
  });

  it("badge Externo aparece quando externo=true", async () => {
    getMock.mockResolvedValue(processo({ externo: true }));
    renderPage();
    expect(await screen.findByText(/^Externo$/i)).toBeInTheDocument();
  });

  it("badge de sigilo aparece quando publico=false", async () => {
    getMock.mockResolvedValue(
      processo({ publico: false, nivel_sigilo: "reservado" }),
    );
    renderPage();
    expect(await screen.findByText(/^Reservado$/i)).toBeInTheDocument();
  });

  it("PDF completo segue visível como botão primário", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    expect(
      await screen.findByRole("button", { name: /PDF completo/i }),
    ).toBeInTheDocument();
  });

  it("ActionsMenu 'Imprimir' substitui os 4 botões antigos", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    // Botão trigger do menu.
    const trigger = await screen.findByRole("button", { name: /^Imprimir/i });
    expect(trigger).toBeInTheDocument();
    // Itens antigos do header NÃO existem mais como botões soltos.
    expect(screen.queryByRole("button", { name: /^Capa$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Etiqueta$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Dupla$/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /^Em fila$/i })).toBeNull();
  });

  it("ActionsMenu abre e expõe 4 itens (Capa / Etiqueta / Etiqueta dupla / Gerar PDF em background)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: /^Imprimir/i }),
    );
    expect(
      screen.getByRole("menuitem", { name: /^Capa$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /^Etiqueta$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /^Etiqueta dupla$/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: /Gerar PDF em background/i }),
    ).toBeInTheDocument();
  });

  it("clicar em 'Capa' dispara setViewer com processoCapaUrl(42, …)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: /^Imprimir/i }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: /^Capa$/i }));

    // PdfViewerDialog stub renderiza os atributos chave.
    expect(processoCapaUrl).toHaveBeenCalledWith(42);
    expect(processoCapaUrl).toHaveBeenCalledWith(42, false);
    expect(await screen.findByTestId("pdf-viewer-title")).toHaveTextContent(
      /Capa — P000042\/2026/i,
    );
  });

  it("clicar em 'Etiqueta' usa etiquetaUnicaUrl(42)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: /^Imprimir/i }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: /^Etiqueta$/i }));
    expect(etiquetaUnicaUrl).toHaveBeenCalledWith(42);
  });

  it("clicar em 'Etiqueta dupla' usa etiquetaDuplaUrl(42)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    await userEvent.click(
      await screen.findByRole("button", { name: /^Imprimir/i }),
    );
    fireEvent.click(
      screen.getByRole("menuitem", { name: /^Etiqueta dupla$/i }),
    );
    expect(etiquetaDuplaUrl).toHaveBeenCalledWith(42);
  });

  it("'PDF completo' (botão primário) usa processoCompletoUrl(42)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /PDF completo/i }),
    );
    expect(processoCompletoUrl).toHaveBeenCalledWith(42);
  });

  it("ClassificarSigiloDialog continua presente (separado do menu)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    expect(
      await screen.findByTestId("classificar-sigilo-dialog"),
    ).toBeInTheDocument();
  });
});

// =============================================================================
// Layout limpo — remoções de duplicação
// =============================================================================

describe("Detalhe servidor — limpeza de duplicações", () => {
  it("CardHeader Visão geral NÃO repete 'aberto em' (já está no PageHeader)", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    await screen.findByRole("button", { name: /^Imprimir/i });
    // "Aberto em" deve aparecer só 1 vez (na description do PageHeader).
    const matches = screen.queryAllByText(/aberto em/i);
    expect(matches.length).toBeLessThanOrEqual(1);
  });

  it("CardHeader Visão geral NÃO repete linha 'Prazo previsto'", async () => {
    getMock.mockResolvedValue(
      processo({
        prazo: {
          status: "dentro_do_prazo",
          prazo_servico_dias_snapshot: 30,
          prazo_previsto_em: "2026-07-01T00:00:00",
          dias_restantes: 12,
          dias_atraso: null,
          concluido_em: null,
          origem: "servico",
        },
      }),
    );
    renderPage();
    await screen.findByRole("button", { name: /^Imprimir/i });
    // "Prazo previsto" como dt foi removido — badge do header já mostra.
    expect(screen.queryByText(/^Prazo previsto$/i)).toBeNull();
  });

  it("Card Visão geral mostra título 'Visão geral'", async () => {
    getMock.mockResolvedValue(processo());
    renderPage();
    expect(
      await screen.findByRole("heading", { name: /Visão geral/i }),
    ).toBeInTheDocument();
  });
});

// =============================================================================
// EmptyState em movimentações vazias
// =============================================================================

describe("Detalhe servidor — estados vazios", () => {
  it("movimentações vazias na tab Movimentações → EmptyState", async () => {
    currentTabParam = "movimentacoes";
    getMock.mockResolvedValue(processo({ movimentacoes: [] }));
    renderPage();
    expect(
      await screen.findByText(/Sem movimentações registradas/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Use 'Ações de tramitação'/i),
    ).toBeInTheDocument();
  });

  it("erro ao carregar processo → EmptyState 'Não foi possível carregar'", async () => {
    getMock.mockRejectedValue(new Error("Boom"));
    renderPage();
    expect(
      await screen.findByText(/Não foi possível carregar este processo/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Boom/)).toBeInTheDocument();
  });
});

// =============================================================================
// ChecklistDocumentosCard em modo servidor
// =============================================================================

describe("Detalhe servidor — Checklist em modo servidor", () => {
  it("aba Documentos: ChecklistDocumentosCard mantém microcopy 'Documentos exigidos'", async () => {
    currentTabParam = "documentos";
    getMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue({
      id_processo: 42,
      id_servico: 1,
      status_documental: "pendente",
      obrigatorios_total: 1,
      obrigatorios_enviados: 0,
      itens: [
        { key: "rg", nome: "RG", obrigatorio: true, descricao: null,
          enviado: false, anexos: [] },
      ],
      complementacao_aberta: null,
    });
    renderPage();
    // Servidor (modo="servidor" explícito): título técnico preservado.
    expect(
      await screen.findByRole("heading", { name: /Documentos exigidos/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Documentos necessários")).toBeNull();
  });

  it("podeAtualizar=true: botão 'Solicitar complementação' aparece quando não há complementação aberta", async () => {
    currentTabParam = "documentos";
    canMock.mockReturnValue(true);
    getMock.mockResolvedValue(processo());
    renderPage();
    expect(
      await screen.findByRole("button", { name: /Solicitar complementação/i }),
    ).toBeInTheDocument();
  });

  it("podeAtualizar=false: botão 'Solicitar complementação' NÃO aparece", async () => {
    currentTabParam = "documentos";
    canMock.mockReturnValue(false);
    getMock.mockResolvedValue(processo());
    renderPage();
    await screen.findByRole("heading", { name: /Documentos exigidos/i });
    expect(
      screen.queryByRole("button", { name: /Solicitar complementação/i }),
    ).toBeNull();
  });
});

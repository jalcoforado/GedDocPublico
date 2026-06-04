import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CidadaoProcessoDetailPage from "@/app/cidadao/processos/[id]/page";
import type {
  ChecklistDocumentosResponse,
  CidadaoProcessoDetail,
  ComplementacaoOut,
} from "@/lib/api";
import { api } from "@/lib/api";

// =============================================================================
// Mocks
// =============================================================================

vi.mock("@/lib/api", () => ({
  api: {
    cidadao: {
      getProcesso: vi.fn(),
      checklistDocumentos: vi.fn(),
      listarComplementacoes: vi.fn(),
      responderComplementacao: vi.fn(),
      uploadAnexo: vi.fn(),
    },
  },
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "42" }),
}));
vi.mock("@/lib/cidadao-auth", () => ({
  useRequireCidadao: () => ({
    cidadao: { id: 1, nome: "Maria", cpf_cnpj: "111", email: null,
                telefone: null, telefone_whatsapp: false, ativo: true },
    loading: false,
  }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const getProcessoMock = api.cidadao.getProcesso as ReturnType<typeof vi.fn>;
const checklistMock = api.cidadao.checklistDocumentos as ReturnType<typeof vi.fn>;
const complementacoesMock = api.cidadao.listarComplementacoes as ReturnType<typeof vi.fn>;
const uploadMock = api.cidadao.uploadAnexo as ReturnType<typeof vi.fn>;

// =============================================================================
// Fixtures
// =============================================================================

function processo(overrides: Partial<CidadaoProcessoDetail> = {}): CidadaoProcessoDetail {
  return {
    id: 42,
    numero_processo: "P000042/2026",
    nup: null,
    data_hora_abertura: "2026-05-01T12:00:00",
    assunto: "Iluminação pública",
    tipo_processo: "Manifestação",
    local_atual: "Protocolo Geral",
    ativo: true,
    publico: true,
    observacao: null,
    corpo: "Solicito reparo da iluminação.",
    especie_nome: null,
    ccd_codigo: null,
    ccd_nome: null,
    movimentacoes: [],
    anexos: [],
    prazo: { status: "sem_previsao", prazo_estimado_em: null },
    ...overrides,
  };
}

function checklist(
  overrides: Partial<ChecklistDocumentosResponse> = {},
): ChecklistDocumentosResponse {
  return {
    id_processo: 42,
    id_servico: 1,
    status_documental: "completo",
    obrigatorios_total: 0,
    obrigatorios_enviados: 0,
    itens: [],
    complementacao_aberta: null,
    ...overrides,
  };
}

function complementacao(
  overrides: Partial<ComplementacaoOut> = {},
): ComplementacaoOut {
  return {
    id: 7,
    status: "aberta",
    mensagem: "Envie comprovante de residência atualizado.",
    documentos_solicitados: [
      { key: "comp", nome: "Comprovante", descricao: null, enviado: false },
    ],
    motivo_cancelamento: null,
    id_usuario_solicitante: 100,
    criado_em: "2026-05-10T09:00:00",
    atualizado_em: null,
    nome_solicitante: "Servidor X",
    respondido_em: null,
    cancelado_em: null,
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <CidadaoProcessoDetailPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  complementacoesMock.mockResolvedValue([]);
});

// =============================================================================
// Próximos passos — 4 cenários
// =============================================================================

describe("Detalhe cidadão — ProximosPassosCard", () => {
  it("complementação aberta → mensagem 'Responda à solicitação de complementação documental'", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(
      checklist({
        status_documental: "parcial",
        complementacao_aberta: complementacao(),
      }),
    );
    renderPage();
    await screen.findByText("P000042/2026");
    expect(
      await screen.findByText(
        /Responda à solicitação de complementação documental/i,
      ),
    ).toBeInTheDocument();
  });

  it("checklist pendente → mensagem 'Envie os documentos pendentes…'", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(
      checklist({
        status_documental: "pendente",
        obrigatorios_total: 2,
        obrigatorios_enviados: 0,
      }),
    );
    renderPage();
    await screen.findByText("P000042/2026");
    expect(
      await screen.findByText(/Envie os documentos pendentes/i),
    ).toBeInTheDocument();
  });

  it("processo encerrado → 'Sua solicitação foi concluída'", async () => {
    getProcessoMock.mockResolvedValue(processo({ ativo: false }));
    checklistMock.mockResolvedValue(checklist({ status_documental: "completo" }));
    renderPage();
    await screen.findByText("P000042/2026");
    expect(await screen.findByText(/foi concluída/i)).toBeInTheDocument();
  });

  it("fallback (ativo + checklist completo) → 'Acompanhe o andamento da solicitação'", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(checklist({ status_documental: "completo" }));
    renderPage();
    await screen.findByText("P000042/2026");
    expect(
      await screen.findByText(/Acompanhe o andamento da solicitação/i),
    ).toBeInTheDocument();
  });
});

// =============================================================================
// Linguagem cidadã + helpers Fase A
// =============================================================================

describe("Detalhe cidadão — linguagem e UI", () => {
  it("checklist usa 'Documentos necessários' (modo cidadão)", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(
      checklist({
        status_documental: "pendente",
        obrigatorios_total: 1,
        obrigatorios_enviados: 0,
        itens: [
          { key: "rg", nome: "RG", obrigatorio: true, descricao: null,
            enviado: false, anexos: [] },
        ],
      }),
    );
    renderPage();
    await screen.findByText("P000042/2026");
    expect(screen.getByText("Documentos necessários")).toBeInTheDocument();
    expect(screen.queryByText("Documentos exigidos")).toBeNull();
  });

  it("badge status em andamento (cidadão) usa label 'Em andamento'", async () => {
    getProcessoMock.mockResolvedValue(processo({ ativo: true }));
    checklistMock.mockResolvedValue(checklist());
    renderPage();
    await screen.findByText("P000042/2026");
    expect(screen.getByText(/^Em andamento$/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Em tramitação$/i)).toBeNull();
  });

  it("badge status concluído usa label 'Concluído' (D-LINGUAGEM-ENCERRADO)", async () => {
    getProcessoMock.mockResolvedValue(processo({ ativo: false }));
    checklistMock.mockResolvedValue(checklist());
    renderPage();
    await screen.findByText("P000042/2026");
    expect(screen.getByText(/^Concluído$/i)).toBeInTheDocument();
  });

  it("anexos vazios → EmptyState (não <p>Nenhum…</p>)", async () => {
    getProcessoMock.mockResolvedValue(processo({ anexos: [] }));
    checklistMock.mockResolvedValue(checklist());
    renderPage();
    await screen.findByText("P000042/2026");
    expect(screen.getByText(/Sem anexos públicos/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Quando o servidor anexar documentos/i),
    ).toBeInTheDocument();
  });

  it("movimentações vazias → EmptyState 'Sem movimentações ainda'", async () => {
    getProcessoMock.mockResolvedValue(processo({ movimentacoes: [] }));
    checklistMock.mockResolvedValue(checklist());
    renderPage();
    await screen.findByText("P000042/2026");
    expect(
      screen.getByText(/Sem movimentações ainda/i),
    ).toBeInTheDocument();
  });

  it("local_atual nulo → 'Aguardando triagem'", async () => {
    getProcessoMock.mockResolvedValue(processo({ local_atual: null }));
    checklistMock.mockResolvedValue(checklist());
    renderPage();
    await screen.findByText("P000042/2026");
    expect(screen.getByText(/Aguardando triagem/i)).toBeInTheDocument();
  });

  it("prazo cidadão NUNCA expõe contagem de dias", async () => {
    getProcessoMock.mockResolvedValue(
      processo({
        prazo: {
          status: "proximo_do_prazo",
          prazo_estimado_em: "2026-06-10T00:00:00",
        },
      }),
    );
    checklistMock.mockResolvedValue(checklist());
    const { container } = renderPage();
    await screen.findByText("P000042/2026");

    // Badge: rotula como "Próximo do prazo" sem sufixo numérico.
    const badge = screen.getByText(/Próximo do prazo/i);
    expect(badge.textContent).not.toMatch(/\(\d+\s*d\.?\)/);
    expect(badge.textContent).not.toMatch(/\d+\s*d\.?$/);

    // Tela inteira: nenhum "(N d.)" ou "atrasado em N dias".
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\(\d+\s*d\.?\)/);
    expect(text).not.toMatch(/atrasado em \d+/i);
  });

  it("nenhum render contém termos vetados", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(
      checklist({
        status_documental: "pendente",
        obrigatorios_total: 1,
        obrigatorios_enviados: 0,
        itens: [
          { key: "rg", nome: "RG", obrigatorio: true, descricao: null,
            enviado: false, anexos: [] },
        ],
        complementacao_aberta: complementacao(),
      }),
    );
    complementacoesMock.mockResolvedValue([complementacao({ status: "respondida" })]);
    const { container } = renderPage();
    await screen.findByText("P000042/2026");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bSLA\b/i);
    expect(text).not.toMatch(/garantia|garantido/i);
    expect(text).not.toMatch(/prazo legal/i);
    expect(text).not.toMatch(/deferid[oa]|indeferid[oa]/i);
  });
});

// =============================================================================
// Regressão: contrato de upload preservado
// =============================================================================

describe("Detalhe cidadão — regressão de upload (contrato com backend)", () => {
  it("Anexar via checklist chama api.cidadao.uploadAnexo com (id, file, file.name, key)", async () => {
    getProcessoMock.mockResolvedValue(processo());
    checklistMock.mockResolvedValue(
      checklist({
        status_documental: "pendente",
        obrigatorios_total: 1,
        obrigatorios_enviados: 0,
        itens: [
          { key: "rg", nome: "RG", obrigatorio: true, descricao: null,
            enviado: false, anexos: [] },
        ],
      }),
    );
    uploadMock.mockResolvedValue({ id: 1 });

    renderPage();
    await screen.findByText("P000042/2026");

    // Abre dialog clicando no botão "Anexar" do item RG.
    fireEvent.click(screen.getByRole("button", { name: /^Anexar$/i }));
    // Dialog presente.
    expect(await screen.findByText(/Anexar: RG/i)).toBeInTheDocument();

    // Seleciona arquivo.
    const fakeFile = new File(["x"], "rg.pdf", { type: "application/pdf" });
    const input = document.getElementById(
      "checklist-file",
    ) as HTMLInputElement;
    Object.defineProperty(input, "files", { value: [fakeFile] });
    fireEvent.change(input);

    // Envia.
    fireEvent.click(screen.getByRole("button", { name: /^Enviar$/i }));

    await waitFor(() => expect(uploadMock).toHaveBeenCalledTimes(1));
    // Contrato com backend: id, file, file.name (descricao), key.
    expect(uploadMock.mock.calls[0]).toEqual([42, fakeFile, "rg.pdf", "rg"]);
  });
});

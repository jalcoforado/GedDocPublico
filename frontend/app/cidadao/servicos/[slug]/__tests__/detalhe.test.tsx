import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ServicoDetalhePage from "@/app/cidadao/servicos/[slug]/page";
import { portalApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({ portalApi: { servico: vi.fn(), servicos: vi.fn(), abrirPorServico: vi.fn() } }));
vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "certidao-iptu" }),
  useRouter: () => ({ push: vi.fn() }),
}));

const servicoMock = portalApi.servico as ReturnType<typeof vi.fn>;

function base(overrides: Record<string, unknown> = {}) {
  return {
    nome: "Certidão de IPTU", slug: "certidao-iptu", descricao_curta: "Emissão",
    descricao_detalhada: "Detalhes da certidão", publico_alvo: "Contribuintes",
    instrucoes_cidadao: "Traga seus dados", prazo_estimado_dias: 5,
    unidade_responsavel: "Protocolo Geral",
    documentos_exigidos: [{ nome: "RG", obrigatorio: true, descricao: null }],
    categoria: "Tributos", destaque: false, ordem_exibicao: 0,
    texto_confirmacao: null, solicitar_habilitado: true, ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ServicoDetalhePage />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("Detalhe público do serviço (PR 4b)", () => {
  it("exibe documentos exigidos e botão Solicitar quando habilitado", async () => {
    servicoMock.mockResolvedValue(base({ solicitar_habilitado: true }));
    renderPage();
    expect(await screen.findByText("Certidão de IPTU")).toBeInTheDocument();
    expect(screen.getByText("Documentos exigidos")).toBeInTheDocument();
    expect(screen.getByText("RG")).toBeInTheDocument();
    expect(screen.getByText("Traga seus dados")).toBeInTheDocument();
    const btn = screen.getByRole("button", { name: /^Solicitar serviço$/i });
    expect(btn).not.toBeDisabled();
  });

  it("botão desabilitado quando indisponível", async () => {
    servicoMock.mockResolvedValue(base({ solicitar_habilitado: false }));
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByRole("button", { name: /Solicitação indisponível/i })).toBeDisabled();
  });
});

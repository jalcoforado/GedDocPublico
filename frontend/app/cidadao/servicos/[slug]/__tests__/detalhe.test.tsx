import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ServicoDetalhePage from "@/app/cidadao/servicos/[slug]/page";
import { portalApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({ portalApi: { servico: vi.fn(), servicos: vi.fn(), abrirPorServico: vi.fn() } }));
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "certidao-iptu" }),
  useRouter: () => ({ push: pushMock }),
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

beforeEach(() => {
  vi.clearAllMocks();
  pushMock.mockReset();
});

describe("Detalhe público do serviço (PR 4b)", () => {
  it("exibe documentos necessários e botão Solicitar quando habilitado", async () => {
    servicoMock.mockResolvedValue(base({ solicitar_habilitado: true }));
    renderPage();
    expect(await screen.findByText("Certidão de IPTU")).toBeInTheDocument();
    expect(screen.getByText("Documentos necessários")).toBeInTheDocument();
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

  // ===== UX-1 Fase B =====

  it("UX-1: prazo aparece no formato 'até N dias'", async () => {
    servicoMock.mockResolvedValue(base({ prazo_estimado_dias: 10 }));
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText(/Prazo estimado: até 10 dias/i)).toBeInTheDocument();
  });

  it("UX-1: instruções aparecem sob 'Como solicitar'", async () => {
    servicoMock.mockResolvedValue(base({ instrucoes_cidadao: "Traga seus dados" }));
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText("Como solicitar")).toBeInTheDocument();
  });

  it("UX-1: indisponível mostra aviso explicativo no corpo, não só botão", async () => {
    servicoMock.mockResolvedValue(base({ solicitar_habilitado: false }));
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(
      screen.getByText(/pausado pela prefeitura/i),
    ).toBeInTheDocument();
  });

  it("UX-1: erro 404 mostra EmptyState e link para voltar", async () => {
    servicoMock.mockRejectedValue(new Error("404"));
    renderPage();
    expect(
      await screen.findByText(/Serviço não encontrado/i),
    ).toBeInTheDocument();
    // Existem 2 links com mesmo label: o do topo e o do EmptyState (action).
    const links = screen.getAllByRole("link", {
      name: /Voltar à Carta de Serviços/i,
    });
    expect(links.length).toBeGreaterThanOrEqual(2);
    expect(links[0]).toHaveAttribute("href", "/cidadao/servicos");
  });

  it("UX-1: público-alvo é apresentado com microcopy cidadã 'Para quem é este serviço'", async () => {
    servicoMock.mockResolvedValue(base({ publico_alvo: "Contribuintes" }));
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText(/Para quem é este serviço/i)).toBeInTheDocument();
    expect(screen.queryByText(/Público-alvo/i)).toBeNull();
  });

  it("UX-1: nenhum render contém termos vetados", async () => {
    servicoMock.mockResolvedValue(base());
    const { container } = renderPage();
    await screen.findByText("Certidão de IPTU");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bSLA\b/i);
    expect(text).not.toMatch(/garantia|garantido/i);
    expect(text).not.toMatch(/prazo legal/i);
    expect(text).not.toMatch(/deferid[oa]|indeferid[oa]/i);
  });
});

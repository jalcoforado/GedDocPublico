import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ServicosPublicosPage from "@/app/cidadao/servicos/page";
import { portalApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  portalApi: { servicos: vi.fn(), servico: vi.fn() },
}));

const servicosMock = portalApi.servicos as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ServicosPublicosPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

function servico(overrides: Record<string, unknown> = {}) {
  return {
    nome: "Certidão de IPTU", slug: "certidao-iptu", descricao_curta: "Emissão rápida",
    descricao_detalhada: null, publico_alvo: null, instrucoes_cidadao: null,
    prazo_estimado_dias: 5, unidade_responsavel: "Protocolo Geral",
    documentos_exigidos: [{ nome: "RG", obrigatorio: true, descricao: null }],
    categoria: "Tributos", destaque: true, ordem_exibicao: 0,
    texto_confirmacao: null, solicitar_habilitado: true, ...overrides,
  };
}

describe("Portal público — Carta de Serviços", () => {
  it("renderiza serviços ativos retornados (inativos não vêm do backend)", async () => {
    servicosMock.mockResolvedValue([servico()]);
    renderPage();

    expect(await screen.findByText("Certidão de IPTU")).toBeInTheDocument();
    expect(screen.getByText("Emissão rápida")).toBeInTheDocument();
    expect(screen.getByText(/Protocolo Geral/)).toBeInTheDocument();
    expect(screen.getByText("RG")).toBeInTheDocument();
    expect(screen.queryByText("Serviço Inativo")).toBeNull();
  });

  it("serviço habilitado mostra link Solicitar serviço (PR 4b)", async () => {
    servicosMock.mockResolvedValue([servico({ solicitar_habilitado: true })]);
    renderPage();
    const link = await screen.findByRole("link", { name: /Solicitar serviço/i });
    expect(link).toHaveAttribute("href", "/cidadao/servicos/certidao-iptu");
  });

  it("serviço indisponível mostra botão desabilitado (PR 4b)", async () => {
    servicosMock.mockResolvedValue([servico({ solicitar_habilitado: false })]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    const btn = screen.getByRole("button", { name: /Solicitação indisponível/i });
    expect(btn).toBeDisabled();
  });

  it("mostra vazio quando não há serviços", async () => {
    servicosMock.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/Nenhum serviço disponível/i)).toBeInTheDocument();
  });
});

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

describe("Portal público — Carta de Serviços (PR 4a)", () => {
  it("renderiza serviços ativos retornados (inativos não vêm do backend)", async () => {
    // O endpoint público só retorna ativos; o mock reflete esse contrato.
    servicosMock.mockResolvedValue([
      {
        nome: "Certidão de IPTU", slug: "certidao-iptu", descricao_curta: "Emissão rápida",
        descricao_detalhada: null, publico_alvo: null, instrucoes_cidadao: null,
        prazo_estimado_dias: 5, unidade_responsavel: "Protocolo Geral",
        documentos_exigidos: [{ nome: "RG", obrigatorio: true, descricao: null }],
        categoria: "Tributos", destaque: true, ordem_exibicao: 0, solicitar_habilitado: false,
      },
    ]);
    renderPage();

    expect(await screen.findByText("Certidão de IPTU")).toBeInTheDocument();
    expect(screen.getByText("Emissão rápida")).toBeInTheDocument();
    expect(screen.getByText(/Protocolo Geral/)).toBeInTheDocument();
    expect(screen.getByText("RG")).toBeInTheDocument();
    // serviço inativo não está na resposta → não aparece
    expect(screen.queryByText("Serviço Inativo")).toBeNull();
    // abertura é PR 4b — botão desabilitado
    const btn = screen.getByRole("button", { name: /Solicitação disponível em breve/i });
    expect(btn).toBeDisabled();
  });

  it("mostra vazio quando não há serviços", async () => {
    servicosMock.mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/Nenhum serviço disponível/i)).toBeInTheDocument();
  });
});

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
    expect(
      await screen.findByText(/Nenhum serviço disponível no momento/i),
    ).toBeInTheDocument();
    // EmptyState — confirma microcopy explicativa.
    expect(
      screen.getByText(/A prefeitura ainda não publicou serviços/i),
    ).toBeInTheDocument();
  });

  // ===== UX-1 Fase B =====

  it("UX-1: enquanto carrega, mostra skeletons (não <p>Carregando…</p>)", () => {
    // Promise pendurada — nunca resolve.
    servicosMock.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.queryByText(/Carregando/i)).toBeNull();
    expect(screen.getByTestId("servicos-loading")).toBeInTheDocument();
  });

  it("UX-1: card exibe prazo em formato 'até N dias' (plural)", async () => {
    servicosMock.mockResolvedValue([servico({ prazo_estimado_dias: 30 })]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText(/Prazo estimado: até 30 dias/i)).toBeInTheDocument();
  });

  it("UX-1: card exibe prazo singular 'até 1 dia'", async () => {
    servicosMock.mockResolvedValue([servico({ prazo_estimado_dias: 1 })]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText(/Prazo estimado: até 1 dia(?!s)/i)).toBeInTheDocument();
  });

  it("UX-1: card exibe legenda '* obrigatório' quando há doc obrigatório", async () => {
    servicosMock.mockResolvedValue([
      servico({
        documentos_exigidos: [{ nome: "RG", obrigatorio: true, descricao: null }],
      }),
    ]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText(/obrigatório$/i)).toBeInTheDocument();
    // <abbr title="Documento obrigatório">
    expect(
      screen.getByTitle(/Documento obrigatório/i),
    ).toBeInTheDocument();
  });

  it("UX-1: card NÃO mostra legenda quando todos docs são opcionais", async () => {
    servicosMock.mockResolvedValue([
      servico({
        documentos_exigidos: [{ nome: "RG", obrigatorio: false, descricao: null }],
      }),
    ]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.queryByText(/^\* obrigatório$/i)).toBeNull();
  });

  it("UX-1: usa 'Documentos necessários' (não 'Documentos exigidos')", async () => {
    servicosMock.mockResolvedValue([servico()]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.getByText("Documentos necessários")).toBeInTheDocument();
    expect(screen.queryByText("Documentos exigidos")).toBeNull();
  });

  it("UX-1: botão Solicitar é renderizado como link (Button asChild)", async () => {
    servicosMock.mockResolvedValue([servico({ solicitar_habilitado: true })]);
    renderPage();
    const link = await screen.findByRole("link", { name: /Solicitar serviço/i });
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/cidadao/servicos/certidao-iptu");
    // Classes do <Button> migraram pro <a>.
    expect(link.className).toContain("inline-flex");
  });

  it("UX-1: botão indisponível tem título explicativo (não jurídico)", async () => {
    servicosMock.mockResolvedValue([servico({ solicitar_habilitado: false })]);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    const btn = screen.getByRole("button", { name: /Solicitação indisponível/i });
    expect(btn).toHaveAttribute(
      "title",
      expect.stringMatching(/pausado pela prefeitura/i),
    );
  });

  it("UX-1: nenhum render contém termos vetados (SLA, garantia, deferido)", async () => {
    servicosMock.mockResolvedValue([servico()]);
    const { container } = renderPage();
    await screen.findByText("Certidão de IPTU");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bSLA\b/i);
    expect(text).not.toMatch(/garantia|garantido/i);
    expect(text).not.toMatch(/prazo legal/i);
    expect(text).not.toMatch(/deferid[oa]|indeferid[oa]/i);
  });
});

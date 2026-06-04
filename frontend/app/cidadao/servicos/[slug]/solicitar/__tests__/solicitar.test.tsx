import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SolicitarServicoPage from "@/app/cidadao/servicos/[slug]/solicitar/page";
import { portalApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  portalApi: { servico: vi.fn(), abrirPorServico: vi.fn() },
}));
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => ({ slug: "certidao-iptu" }),
  useRouter: () => ({ push: pushMock }),
}));
vi.mock("@/lib/cidadao-auth", () => ({
  useRequireCidadao: () => ({ cidadao: { id: 1, nome: "Maria" }, loading: false }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const servicoMock = portalApi.servico as ReturnType<typeof vi.fn>;
const abrirMock = portalApi.abrirPorServico as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <SolicitarServicoPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  pushMock.mockReset();
  servicoMock.mockResolvedValue({
    nome: "Certidão de IPTU", slug: "certidao-iptu", descricao_curta: null,
    descricao_detalhada: null, publico_alvo: null, instrucoes_cidadao: null,
    prazo_estimado_dias: null, unidade_responsavel: "Protocolo Geral",
    documentos_exigidos: [{ nome: "RG", obrigatorio: true, descricao: null }],
    categoria: null, destaque: false, ordem_exibicao: 0,
    texto_confirmacao: "Você receberá um número de protocolo.", solicitar_habilitado: true,
  });
});

describe("Solicitar serviço (PR 4b)", () => {
  it("envia a solicitação e navega para o comprovante", async () => {
    abrirMock.mockResolvedValue({ id: 42, numero_processo: "P000042/2026", nup: null });
    renderPage();

    // documentos como orientação
    expect(await screen.findByText("Documentos necessários")).toBeInTheDocument();

    const corpo = screen.getByLabelText(/Descreva sua solicitação/i);
    fireEvent.change(corpo, { target: { value: "Preciso de uma certidão de IPTU para o imóvel." } });
    fireEvent.click(screen.getByRole("button", { name: /Avançar/i }));

    // passo de confirmação mostra texto_confirmacao
    expect(await screen.findByText(/receberá um número de protocolo/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Confirmar e enviar/i }));

    await waitFor(() => expect(abrirMock).toHaveBeenCalled());
    // UX-1: body preservado intacto — contrato com backend.
    expect(abrirMock.mock.calls[0][0]).toBe("certidao-iptu");
    expect(abrirMock.mock.calls[0][1].corpo).toContain("certidão de IPTU");
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/cidadao/processos/42"));
  });

  // ===== UX-1 Fase B =====

  it("UX-1: 'Avançar' fica desabilitado até atingir o mínimo de caracteres", async () => {
    renderPage();
    await screen.findByText("Documentos necessários");
    const corpo = screen.getByLabelText(/Descreva sua solicitação/i);
    const avancar = screen.getByRole("button", { name: /Avançar/i });

    expect(avancar).toBeDisabled();
    fireEvent.change(corpo, { target: { value: "curto" } });
    expect(avancar).toBeDisabled();
    fireEvent.change(corpo, { target: { value: "agora com mais de dez" } });
    expect(avancar).not.toBeDisabled();
  });

  it("UX-1: contador mostra progresso atual / mínimo (10)", async () => {
    renderPage();
    await screen.findByText("Documentos necessários");
    const corpo = screen.getByLabelText(/Descreva sua solicitação/i);
    expect(screen.getByText("0/10")).toBeInTheDocument();
    fireEvent.change(corpo, { target: { value: "alguma coisa aqui" } });
    expect(screen.getByText("17/10")).toBeInTheDocument();
  });

  it("UX-1: 'Voltar' no passo 2 retorna ao passo 1 sem perder corpo", async () => {
    renderPage();
    await screen.findByText("Documentos necessários");
    const corpo = screen.getByLabelText(/Descreva sua solicitação/i);
    fireEvent.change(corpo, { target: { value: "Algum texto longo o suficiente" } });
    fireEvent.click(screen.getByRole("button", { name: /Avançar/i }));
    await screen.findByRole("button", { name: /Confirmar e enviar/i });
    fireEvent.click(screen.getByRole("button", { name: /^Voltar$/i }));
    // De volta ao passo 1 — o texto deve continuar lá.
    const c2 = screen.getByLabelText(/Descreva sua solicitação/i) as HTMLTextAreaElement;
    expect(c2.value).toContain("Algum texto");
  });

  it("UX-1: aviso de indisponível inclui link para Meus processos", async () => {
    servicoMock.mockResolvedValue({
      nome: "X", slug: "certidao-iptu", descricao_curta: null,
      descricao_detalhada: null, publico_alvo: null, instrucoes_cidadao: null,
      prazo_estimado_dias: null, unidade_responsavel: null,
      documentos_exigidos: null, categoria: null, destaque: false,
      ordem_exibicao: 0, texto_confirmacao: null, solicitar_habilitado: false,
    });
    renderPage();
    expect(
      await screen.findByText(/pausado pela prefeitura/i),
    ).toBeInTheDocument();
    const meusProcessos = screen.getByRole("link", {
      name: /Meus processos/i,
    });
    expect(meusProcessos).toHaveAttribute("href", "/cidadao/processos");
  });

  it("UX-1: nenhum render contém termos vetados", async () => {
    const { container } = renderPage();
    await screen.findByText("Documentos necessários");
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bSLA\b/i);
    expect(text).not.toMatch(/garantia|garantido/i);
    expect(text).not.toMatch(/prazo legal/i);
    expect(text).not.toMatch(/deferid[oa]|indeferid[oa]/i);
  });
});

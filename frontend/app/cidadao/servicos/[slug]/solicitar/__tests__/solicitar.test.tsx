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
    expect(await screen.findByText("Documentos exigidos")).toBeInTheDocument();

    const corpo = screen.getByLabelText(/Descreva sua solicitação/i);
    fireEvent.change(corpo, { target: { value: "Preciso de uma certidão de IPTU para o imóvel." } });
    fireEvent.click(screen.getByRole("button", { name: /Avançar/i }));

    // passo de confirmação mostra texto_confirmacao
    expect(await screen.findByText(/receberá um número de protocolo/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Confirmar e enviar/i }));

    await waitFor(() => expect(abrirMock).toHaveBeenCalled());
    expect(abrirMock.mock.calls[0][0]).toBe("certidao-iptu");
    expect(abrirMock.mock.calls[0][1].corpo).toContain("certidão de IPTU");
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/cidadao/processos/42"));
  });
});

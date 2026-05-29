import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConfiguracoesPage from "@/app/(app)/configuracoes/page";
import { api, tenantsApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { unidades: { list: vi.fn() } },
  tenantsApi: {
    me: vi.fn(),
    onboarding: vi.fn(),
    updateInstitucional: vi.fn(),
    updateNupConfig: vi.fn(),
  },
}));

const canMock = vi.fn();
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: canMock }) }));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const meMock = tenantsApi.me as ReturnType<typeof vi.fn>;
const onboardingMock = tenantsApi.onboarding as ReturnType<typeof vi.fn>;
const updateMock = tenantsApi.updateInstitucional as ReturnType<typeof vi.fn>;
const unidadesMock = api.unidades.list as ReturnType<typeof vi.fn>;

const TENANT = {
  id: 1, slug: "sobral", nome: "Prefeitura X", plano: "basico",
  cor_primaria: null, logo_url: null, codigo_orgao_nup: null, usar_nup_federal: false,
  sigla: null, email_institucional: null, telefone_institucional: null,
  endereco: null, site_oficial: null, horario_atendimento: null,
  texto_boas_vindas_portal: null, id_unidade_padrao: null,
};

const ONBOARDING = {
  total: 2, concluidos: 1, pendentes: 1,
  itens: [
    { chave: "unidades", rotulo: "Unidade de trabalho cadastrada", concluido: false },
    { chave: "assinatura", rotulo: "Módulo de assinatura habilitado", concluido: true },
  ],
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ConfiguracoesPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  meMock.mockResolvedValue(TENANT);
  onboardingMock.mockResolvedValue(ONBOARDING);
  unidadesMock.mockResolvedValue({ items: [{ id: 10, unidade_trabalho: "Protocolo", sigla: null, id_unidade_pai: null, id_tipo_unidade_trabalho: null }], total: 1, page: 1, page_size: 200 });
});

describe("ConfiguracoesPage — PR 3b", () => {
  it("salva só campos institucionais (sem id/slug/plano)", async () => {
    canMock.mockReturnValue(true);
    updateMock.mockResolvedValue({ ...TENANT, email_institucional: "novo@pmn.gov.br" });
    renderPage();

    const email = (await screen.findByLabelText(/E-mail institucional/i)) as HTMLInputElement;
    fireEvent.change(email, { target: { value: "novo@pmn.gov.br" } });
    fireEvent.click(screen.getByRole("button", { name: /Salvar dados institucionais/i }));

    await waitFor(() => expect(updateMock).toHaveBeenCalled());
    const payload = updateMock.mock.calls[0][0];
    expect(payload.nome).toBe("Prefeitura X");
    expect(payload.email_institucional).toBe("novo@pmn.gov.br");
    for (const proibido of ["id", "slug", "plano", "ativo", "limite_usuarios", "cnpj"]) {
      expect(payload).not.toHaveProperty(proibido);
    }
  });

  it("modo leitura quando sem permissão", async () => {
    canMock.mockReturnValue(false);
    renderPage();
    const email = (await screen.findByLabelText(/E-mail institucional/i)) as HTMLInputElement;
    expect(email).toBeDisabled();
    expect(screen.getByRole("button", { name: /Salvar dados institucionais/i })).toBeDisabled();
  });

  it("checklist exibe itens e deep-link para pendência", async () => {
    canMock.mockReturnValue(true);
    renderPage();
    expect(await screen.findByText("Unidade de trabalho cadastrada")).toBeInTheDocument();
    expect(screen.getByText("Módulo de assinatura habilitado")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: /Configurar/i });
    expect(link).toHaveAttribute("href", "/unidades-trabalho");
  });
});

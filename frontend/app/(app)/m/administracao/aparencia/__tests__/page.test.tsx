/**
 * Aparência: cor fora do formato só acusa depois de sair do campo, e o
 * salvar não manda para o backend (que responderia 422) — mostra o campo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AparenciaPage from "@/app/(app)/m/administracao/aparencia/page";
import { tenantsApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  tenantsApi: { me: vi.fn(), updateInstitucional: vi.fn() },
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: () => true }) }));
vi.mock("@/lib/branding", () => ({ useRecarregarBranding: () => vi.fn() }));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const TENANT = {
  id: 1, slug: "x", nome: "Prefeitura X", plano: "basico",
  cor_primaria: null, cor_destaque: null, cor_lateral: null, cor_titulos: null,
  fonte_titulos: null,
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <AparenciaPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (tenantsApi.me as ReturnType<typeof vi.fn>).mockResolvedValue(TENANT);
  (tenantsApi.updateInstitucional as ReturnType<typeof vi.fn>).mockResolvedValue(TENANT);
});

describe("AparenciaPage", () => {
  it("cor incompleta: sem erro enquanto digita, erro ao sair; salvar foca e não envia", async () => {
    renderPage();
    const campo = await screen.findByLabelText("Cor primária");
    fireEvent.change(campo, { target: { value: "#1a2" } });
    expect(screen.queryByText(/Use o formato #RRGGBB/)).not.toBeInTheDocument();
    fireEvent.blur(campo);
    expect(await screen.findByText(/Use o formato #RRGGBB/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Salvar aparência" }));
    expect(tenantsApi.updateInstitucional).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(campo);
  });

  it("cor válida salva só os campos do tema", async () => {
    renderPage();
    const campo = await screen.findByLabelText("Cor primária");
    fireEvent.change(campo, { target: { value: "#1a2b3c" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar aparência" }));
    await waitFor(() =>
      expect(tenantsApi.updateInstitucional).toHaveBeenCalledWith({
        cor_primaria: "#1a2b3c",
        cor_destaque: null,
        cor_lateral: null,
        cor_titulos: null,
        fonte_titulos: null,
      }),
    );
  });
});

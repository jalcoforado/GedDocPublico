import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ValidarAcao } from "@/components/AssinaturasProcesso";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { assinaturas: { validar: vi.fn() } },
  assinaturaComprovanteUrl: (id: number) => `/api/v2/assinaturas/${id}/comprovante.pdf`,
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

function renderAcao() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ValidarAcao aaId={7} />
    </QueryClientProvider>,
  );
}

describe("ValidarAcao", () => {
  beforeEach(() => vi.clearAllMocks());

  it("validação íntegra mostra mensagem e toast de sucesso", async () => {
    (api.assinaturas.validar as ReturnType<typeof vi.fn>).mockResolvedValue({
      legado: false,
      integro: true,
    });
    const u = userEvent.setup();
    renderAcao();
    await u.click(screen.getByRole("button", { name: /validar/i }));
    expect(await screen.findByText(/íntegra/i)).toBeInTheDocument();
    expect(api.assinaturas.validar).toHaveBeenCalledWith(7);
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("documento alterado mostra mensagem e toast de erro", async () => {
    (api.assinaturas.validar as ReturnType<typeof vi.fn>).mockResolvedValue({
      legado: false,
      integro: false,
    });
    const u = userEvent.setup();
    renderAcao();
    await u.click(screen.getByRole("button", { name: /validar/i }));
    expect(await screen.findByText(/alterado/i)).toBeInTheDocument();
    expect(toastError).toHaveBeenCalled();
  });

  it("link de comprovante presente", () => {
    (api.assinaturas.validar as ReturnType<typeof vi.fn>).mockResolvedValue({
      legado: false,
      integro: true,
    });
    renderAcao();
    const link = screen.getByRole("link", { name: /comprovante/i });
    expect(link).toHaveAttribute(
      "href",
      "/api/v2/assinaturas/7/comprovante.pdf",
    );
  });
});

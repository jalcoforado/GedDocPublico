import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TrocarSenhaCard } from "@/components/TrocarSenhaCard";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: { alterarSenha: vi.fn() } }));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TrocarSenhaCard />
    </QueryClientProvider>,
  );
}

describe("TrocarSenhaCard", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sucesso: chama api e mostra toast", async () => {
    (api.alterarSenha as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const u = userEvent.setup();
    renderCard();
    await u.type(screen.getByLabelText(/^Senha atual/i), "velha123");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() =>
      expect(api.alterarSenha).toHaveBeenCalledWith("velha123", "nova-senha-1"),
    );
    expect(toastSuccess).toHaveBeenCalled();
  });

  it("erro do backend (senha atual incorreta) renderiza alerta", async () => {
    (api.alterarSenha as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("Senha atual incorreta"),
    );
    const u = userEvent.setup();
    renderCard();
    await u.type(screen.getByLabelText(/^Senha atual/i), "errada");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Senha atual incorreta");
  });

  it("validação local: confirmação não confere (não chama api)", async () => {
    const u = userEvent.setup();
    renderCard();
    await u.type(screen.getByLabelText(/^Senha atual/i), "velha123");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "diferente-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/confere/i);
    expect(api.alterarSenha).not.toHaveBeenCalled();
  });
});

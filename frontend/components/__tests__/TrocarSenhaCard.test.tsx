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
    // O erro mora sob o campo da confirmação (padrão de formulário), e o
    // foco vai para ele.
    const confirma = screen.getByLabelText(/^Confirmar/i);
    expect(await screen.findByText(/não confere/i)).toBeInTheDocument();
    expect(confirma).toHaveAttribute("aria-invalid", "true");
    expect(document.activeElement).toBe(confirma);
    expect(api.alterarSenha).not.toHaveBeenCalled();
  });

  it("regras da nova senha se marcam ao vivo; erro de tamanho só depois de sair do campo", async () => {
    const u = userEvent.setup();
    renderCard();
    const regras = screen.getByRole("list", { name: /Regras da nova senha/i });
    expect(regras).toHaveTextContent(/Pelo menos 8 caracteres — pendente/);

    await u.type(screen.getByLabelText(/^Nova senha/i), "curta");
    expect(screen.queryByText(/ao menos 8 caracteres/i)).not.toBeInTheDocument();
    await u.tab();
    expect(await screen.findByText(/ao menos 8 caracteres/i)).toBeInTheDocument();

    await u.type(screen.getByLabelText(/^Nova senha/i), "-mais");
    expect(regras).toHaveTextContent(/Pelo menos 8 caracteres — atendida/);
    await u.type(screen.getByLabelText(/^Confirmar/i), "curta-mais");
    expect(regras).toHaveTextContent(/igual à nova senha — atendida/);
  });

  // SEC-1 Commit 5 — props opcionais.

  it("SEC-1: onSuccess é chamado após sucesso quando passado", async () => {
    (api.alterarSenha as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const onSuccess = vi.fn();
    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <TrocarSenhaCard onSuccess={onSuccess} />
      </QueryClientProvider>,
    );
    const u = userEvent.setup();
    await u.type(screen.getByLabelText(/^Senha atual/i), "velha123");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalled());
  });

  it("SEC-1: successMessage customiza o toast quando passado", async () => {
    (api.alterarSenha as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <TrocarSenhaCard successMessage="Tudo certo." />
      </QueryClientProvider>,
    );
    const u = userEvent.setup();
    await u.type(screen.getByLabelText(/^Senha atual/i), "velha123");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith("Tudo certo."));
  });

  it("SEC-1 regressão: sem props funciona como antes (toast padrão, sem onSuccess)", async () => {
    (api.alterarSenha as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    const u = userEvent.setup();
    renderCard();
    await u.type(screen.getByLabelText(/^Senha atual/i), "velha123");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        "Senha alterada. Você já pode assinar normalmente.",
      ),
    );
  });
});

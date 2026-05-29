import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ValidacaoPublicaCard } from "@/components/ValidacaoPublicaCard";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    assinaturas: {
      evidencias: vi.fn(),
      revogarValidacaoPublica: vi.fn(),
    },
  },
  assinaturaComprovanteUrl: (id: number) => `/api/v2/assinaturas/${id}/comprovante.pdf`,
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

const canMock = vi.fn(() => true);
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: canMock }),
}));

const evidenciasMock = api.assinaturas.evidencias as ReturnType<typeof vi.fn>;
const revogarMock = api.assinaturas.revogarValidacaoPublica as ReturnType<typeof vi.fn>;

const ATIVA = {
  id_assinatura_anexo: 7,
  codigo_validacao: "TOKEN123",
  validacao_publica_url: "https://sobral.aprimora.local/validar/TOKEN123",
  validacao_publica_status: "ativa",
};

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ValidacaoPublicaCard aaId={7} defaultOpen />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  canMock.mockReturnValue(true);
  Object.defineProperty(navigator, "clipboard", {
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
    configurable: true,
  });
});

describe("ValidacaoPublicaCard", () => {
  it("renderiza status, código e URL quando ativa", async () => {
    evidenciasMock.mockResolvedValue(ATIVA);
    renderCard();
    expect(await screen.findByText("TOKEN123")).toBeInTheDocument();
    expect(screen.getByText(/validação pública ativa/i)).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /sobral\.aprimora\.local\/validar\/TOKEN123/i }),
    ).toBeInTheDocument();
  });

  it("copiar código dá feedback 'copiado'", async () => {
    evidenciasMock.mockResolvedValue(ATIVA);
    const u = userEvent.setup();
    renderCard();
    await screen.findByText("TOKEN123");
    await u.click(screen.getByRole("button", { name: /copiar código/i }));
    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(expect.stringMatching(/copiado/i)),
    );
  });

  it("botão revogar só aparece com permissão", async () => {
    evidenciasMock.mockResolvedValue(ATIVA);
    canMock.mockReturnValue(false);
    renderCard();
    await screen.findByText("TOKEN123");
    expect(
      screen.queryByRole("button", { name: /revogar validação pública/i }),
    ).not.toBeInTheDocument();
  });

  it("não expõe código quando bloqueada por sigilo", async () => {
    evidenciasMock.mockResolvedValue({
      ...ATIVA,
      validacao_publica_status: "bloqueada_sigilo",
    });
    renderCard();
    expect(await screen.findByText(/bloqueada por sigilo/i)).toBeInTheDocument();
    expect(screen.queryByText("TOKEN123")).not.toBeInTheDocument();
  });

  it("confirmação envia motivo opcional, revoga e muda o status", async () => {
    evidenciasMock.mockResolvedValueOnce(ATIVA).mockResolvedValue({
      ...ATIVA,
      validacao_publica_status: "revogada",
    });
    revogarMock.mockResolvedValue({ id_assinatura_anexo: 7, validacao_publica_revogada: true });
    const u = userEvent.setup();
    renderCard();
    await u.click(await screen.findByRole("button", { name: /revogar validação pública/i }));
    const dialog = await screen.findByRole("dialog");
    // fireEvent (não userEvent.type): o focus-trap do Dialog interfere no type.
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "documento substituido" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /^Revogar$/ }));
    await waitFor(() =>
      expect(revogarMock).toHaveBeenCalledWith(7, "documento substituido"),
    );
    // status muda após revogação (refetch das evidências)
    expect(await screen.findByText(/validação pública revogada/i)).toBeInTheDocument();
  });

  it("revoga sem motivo (motivo opcional)", async () => {
    evidenciasMock.mockResolvedValue(ATIVA);
    revogarMock.mockResolvedValue({ id_assinatura_anexo: 7, validacao_publica_revogada: true });
    const u = userEvent.setup();
    renderCard();
    await u.click(await screen.findByRole("button", { name: /revogar validação pública/i }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /^Revogar$/ }));
    await waitFor(() => expect(revogarMock).toHaveBeenCalledWith(7, undefined));
  });
});

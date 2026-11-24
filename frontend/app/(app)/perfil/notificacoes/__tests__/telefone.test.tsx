/**
 * Telefone do WhatsApp em Preferências de notificações: aceita o número
 * digitado do jeito comum, grava só "+" e dígitos (como antes) e mostra para
 * onde os avisos vão; erro só depois de sair do campo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreferenciasNotificacoesPage from "@/app/(app)/perfil/notificacoes/page";
import { notificacoesApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  notificacoesApi: {
    getPreferencias: vi.fn(),
    getTelefone: vi.fn(),
    setPreferenciaEvento: vi.fn(),
    setTelefone: vi.fn(),
    whatsappTest: vi.fn(),
  },
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <PreferenciasNotificacoesPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (notificacoesApi.getPreferencias as ReturnType<typeof vi.fn>).mockResolvedValue([
    { evento: "processo_recebido", label: "Processo recebido", in_app: true, email: false, whatsapp: false },
  ]);
  (notificacoesApi.getTelefone as ReturnType<typeof vi.fn>).mockResolvedValue({ telefone: null });
  (notificacoesApi.setTelefone as ReturnType<typeof vi.fn>).mockImplementation(async (t: string | null) => ({
    telefone: t,
  }));
});

describe("Preferências de notificações — telefone", () => {
  it("número digitado com máscara grava só dígitos e diz para onde os avisos vão", async () => {
    renderPage();
    const tel = (await screen.findByLabelText(/Celular com WhatsApp/i)) as HTMLInputElement;
    fireEvent.change(tel, { target: { value: "+55 (88) 99999-8888" } });
    expect(tel.value).toBe("+5588999998888");
    expect(screen.getByText("Os avisos vão para +55 (88) 99999-8888.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Salvar telefone/i }));
    await waitFor(() => expect(notificacoesApi.setTelefone).toHaveBeenCalledWith("+5588999998888"));
  });

  it("número curto: erro só ao sair do campo, e salvar não envia", async () => {
    renderPage();
    const tel = await screen.findByLabelText(/Celular com WhatsApp/i);
    fireEvent.change(tel, { target: { value: "123" } });
    expect(screen.queryByText(/Use só números/i)).not.toBeInTheDocument();
    fireEvent.blur(tel);
    expect(await screen.findByText(/Use só números/i)).toBeInTheDocument();
    expect(tel).toHaveAttribute("aria-invalid", "true");
    fireEvent.click(screen.getByRole("button", { name: /Salvar telefone/i }));
    expect(notificacoesApi.setTelefone).not.toHaveBeenCalled();
  });

  it("cada caixa da matriz tem nome: canal e evento", async () => {
    renderPage();
    expect(await screen.findByRole("checkbox", { name: "E-mail — Processo recebido" })).not.toBeChecked();
  });
});

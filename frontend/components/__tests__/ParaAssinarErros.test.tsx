import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ParaAssinarPage from "@/app/(app)/para-assinar/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    assinaturas: {
      minhasPendentes: vi.fn(),
      assinar: vi.fn(),
      recusar: vi.fn(),
    },
  },
  anexoInlineUrl: (id: number) => `/inline/${id}`,
  anexoDownloadUrl: (id: number) => `/dl/${id}`,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const pendencia = {
  id_assinatura_anexo: 11,
  id_anexo: 5,
  anexo_descricao: "Doc X",
  id_solicitacao: 3,
  id_processo: 9,
  numero_processo: "P000001/2026",
  nome_solicitante: "Fulano",
  dt_inicio: new Date().toISOString(),
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ParaAssinarPage />
    </QueryClientProvider>,
  );
}

async function abrirEAssinar(u: ReturnType<typeof userEvent.setup>) {
  await screen.findByText("Doc X");
  await u.click(screen.getByRole("button", { name: /^assinar$/i }));
  await u.type(screen.getByLabelText(/^senha/i), "qualquer-coisa");
  await u.click(screen.getByRole("button", { name: /confirmar assinatura/i }));
}

describe("ParaAssinar — tratamento de erro do assinar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.assinaturas.minhasPendentes as ReturnType<typeof vi.fn>).mockResolvedValue([
      pendencia,
    ]);
  });

  it("409 (senha legada) renderiza a orientação de atualizar senha", async () => {
    (api.assinaturas.assinar as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error(
        "Para assinar documentos, sua senha precisa ser atualizada para o padrão atual de segurança. Saia do sistema e faça login novamente.",
      ),
    );
    const u = userEvent.setup();
    renderPage();
    await abrirEAssinar(u);
    expect(await screen.findByRole("alert")).toHaveTextContent(/atualizada/i);
  });

  it("429 (throttle) renderiza a mensagem de muitas tentativas", async () => {
    (api.assinaturas.assinar as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error("Muitas tentativas malsucedidas. Tente novamente em alguns minutos."),
    );
    const u = userEvent.setup();
    renderPage();
    await abrirEAssinar(u);
    expect(await screen.findByRole("alert")).toHaveTextContent(/muitas tentativas/i);
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlataformaGate } from "@/components/admin/PlataformaGate";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { admin: { me: vi.fn() } },
}));

const meMock = api.admin.me as ReturnType<typeof vi.fn>;

function renderGate() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <PlataformaGate>
        <div>CONTEUDO PLATAFORMA</div>
      </PlataformaGate>
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("PlataformaGate", () => {
  it("renderiza o conteúdo para admin de plataforma", async () => {
    meMock.mockResolvedValue({ email: "ops@x.com", is_platform_admin: true });
    renderGate();
    expect(await screen.findByText("CONTEUDO PLATAFORMA")).toBeInTheDocument();
  });

  it("não expõe o painel para não-plataforma (acesso restrito)", async () => {
    meMock.mockResolvedValue({ email: "su@prefeitura.gov.br", is_platform_admin: false });
    renderGate();
    expect(await screen.findByText(/acesso restrito/i)).toBeInTheDocument();
    expect(screen.queryByText("CONTEUDO PLATAFORMA")).not.toBeInTheDocument();
  });
});

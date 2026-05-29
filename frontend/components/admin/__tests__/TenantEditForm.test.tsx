import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantEditForm } from "@/components/admin/TenantEditForm";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { admin: { tenants: { detalhe: vi.fn(), editar: vi.fn() } } },
}));

const toastSuccess = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: vi.fn(), info: vi.fn() }),
}));

const detalheMock = api.admin.tenants.detalhe as ReturnType<typeof vi.fn>;
const editarMock = api.admin.tenants.editar as ReturnType<typeof vi.fn>;

const TENANT = {
  id: 1, slug: "sobral", nome: "Prefeitura de Sobral", cnpj: null, id_cidade: null,
  ativo: true, plano: "basico", cor_primaria: null, logo_url: null,
  codigo_orgao_nup: null, usar_nup_federal: false, limite_usuarios: null,
  limite_armazenamento_mb: null, criado_em: "2026-01-01T00:00:00", atualizado_em: null,
  modulos: ["protocolo"],
};

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TenantEditForm tenantId={1} />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("TenantEditForm", () => {
  it("slug é exibido mas NÃO é editável", async () => {
    detalheMock.mockResolvedValue(TENANT);
    renderForm();
    const slug = (await screen.findByDisplayValue("sobral")) as HTMLInputElement;
    expect(slug).toHaveAttribute("readonly");
    expect(slug).toBeDisabled();
  });

  it("salvar envia os campos permitidos (sem slug)", async () => {
    detalheMock.mockResolvedValue(TENANT);
    editarMock.mockResolvedValue({ ...TENANT, nome: "Sobral Editada" });
    renderForm();
    const nome = (await screen.findByDisplayValue("Prefeitura de Sobral")) as HTMLInputElement;
    fireEvent.change(nome, { target: { value: "Sobral Editada" } });
    fireEvent.click(screen.getByRole("button", { name: /salvar/i }));
    await waitFor(() => expect(editarMock).toHaveBeenCalled());
    const [, payload] = editarMock.mock.calls[0];
    expect(payload.nome).toBe("Sobral Editada");
    expect(payload).not.toHaveProperty("slug");
  });
});

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TenantsAdmin } from "@/components/admin/TenantsAdmin";
import { api } from "@/lib/api";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/api", () => ({
  api: {
    admin: {
      tenants: {
        list: vi.fn(),
        criar: vi.fn(),
        ativar: vi.fn(),
        desativar: vi.fn(),
      },
    },
  },
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

const listMock = api.admin.tenants.list as ReturnType<typeof vi.fn>;
const criarMock = api.admin.tenants.criar as ReturnType<typeof vi.fn>;
const desativarMock = api.admin.tenants.desativar as ReturnType<typeof vi.fn>;

const TENANT = {
  id: 1, slug: "sobral", nome: "Prefeitura de Sobral", cnpj: null, id_cidade: null,
  ativo: true, plano: "basico", cor_primaria: null, logo_url: null,
  codigo_orgao_nup: null, usar_nup_federal: false, limite_usuarios: 50,
  limite_armazenamento_mb: null, criado_em: "2026-01-01T00:00:00", atualizado_em: null,
  modulos: ["protocolo"],
};

function renderAdmin() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TenantsAdmin />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe("TenantsAdmin", () => {
  it("lista tenants com slug, plano e status", async () => {
    listMock.mockResolvedValue([TENANT]);
    renderAdmin();
    expect(await screen.findByText("sobral")).toBeInTheDocument();
    expect(screen.getByText("Prefeitura de Sobral")).toBeInTheDocument();
    expect(screen.getByText("Ativo")).toBeInTheDocument();
  });

  it("desativar chama a API com o id", async () => {
    listMock.mockResolvedValue([TENANT]);
    desativarMock.mockResolvedValue({ ...TENANT, ativo: false });
    renderAdmin();
    await screen.findByText("sobral");
    fireEvent.click(screen.getByRole("button", { name: /desativar/i }));
    await waitFor(() => expect(desativarMock).toHaveBeenCalledWith(1));
  });

  it("criar tenant exibe a senha temporária uma única vez", async () => {
    listMock.mockResolvedValue([]);
    criarMock.mockResolvedValue({
      tenant: { ...TENANT, id: 2, slug: "fortaleza", nome: "Fortaleza" },
      admin_email: "adm@fortaleza.local",
      senha_temporaria: "TMP-senha-123",
      aviso: "Exibida uma única vez.",
    });
    const u = userEvent.setup();
    renderAdmin();
    await u.click(await screen.findByRole("button", { name: /nova prefeitura/i }));
    const dialog = await screen.findByRole("dialog");
    // fireEvent.change: evita o focus-trap do Dialog com userEvent.type
    fireEvent.change(within(dialog).getByPlaceholderText(/fortaleza/i), { target: { value: "fortaleza" } });
    const inputs = within(dialog).getAllByRole("textbox");
    // nome, e-mail, nome admin, cpf — preenche os obrigatórios restantes
    fireEvent.change(inputs[1], { target: { value: "Prefeitura de Fortaleza" } });
    fireEvent.change(inputs[2], { target: { value: "adm@fortaleza.local" } });
    fireEvent.change(inputs[3], { target: { value: "Administrador" } });
    fireEvent.change(inputs[4], { target: { value: "12345678901" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /^Criar$/ }));
    await waitFor(() => expect(criarMock).toHaveBeenCalled());
    expect(await screen.findByText("TMP-senha-123")).toBeInTheDocument();
  });
});

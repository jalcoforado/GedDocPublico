import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsuariosPage from "@/app/(app)/m/administracao/usuarios/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    usuarios: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      remove: vi.fn(),
      setGrupos: vi.fn(),
      setUnidades: vi.fn(),
      resetarSenha: vi.fn(),
    },
    unidades: { list: vi.fn() },
    grupos: { list: vi.fn() },
  },
  NIVEL_SIGILO_LABEL: {
    ostensivo: "Ostensivo", interno: "Interno", reservado: "Reservado",
    secreto: "Secreto", ultrassecreto: "Ultrassecreto",
  },
}));

const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: () => true, perms: { is_super_usuario: false } }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const listMock = api.usuarios.list as ReturnType<typeof vi.fn>;
const resetMock = api.usuarios.resetarSenha as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <UsuariosPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  confirmMock.mockResolvedValue(true);
  listMock.mockResolvedValue({
    items: [{ id: 5, nome: "Maria", email: "m@x.gov.br", cpf: "11111111111", id_unidade_trabalho: null, cargo: null, ativo: true, nivel_acesso_sigilo: "interno" }],
    total: 1, page: 1, page_size: 20,
  });
  (api.unidades.list as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  (api.grupos.list as ReturnType<typeof vi.fn>).mockResolvedValue([]);
});

describe("UsuariosPage — reset de senha (PR 3b)", () => {
  it("exibe a senha temporária uma única vez após confirmar", async () => {
    resetMock.mockResolvedValue({
      id_usuario: 5,
      senha_temporaria: "TempABC123xyz",
      aviso: "Copie agora: esta senha temporária só é exibida uma vez.",
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /Resetar senha/i }));

    await waitFor(() => expect(resetMock).toHaveBeenCalledWith(5));
    const senha = await screen.findByText("TempABC123xyz");
    expect(senha).toBeInTheDocument();
    expect(screen.getAllByText("TempABC123xyz")).toHaveLength(1);
    expect(screen.getByText(/não será exibida novamente/i)).toBeInTheDocument();
  });
});

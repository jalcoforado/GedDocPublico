/**
 * SEC-1 follow-up — copy/payload do campo "Nova senha" no dialog de edição.
 *
 * Cobre 3 cenários:
 *   1. Quando o dialog abre em modo edição, a copy avisa que a senha é
 *      temporária e dispara troca obrigatória no próximo acesso.
 *   2. Salvar sem preencher senha não envia o campo `senha` no payload do PUT.
 *   3. Salvar com senha preenchida envia `senha` no payload do PUT (contrato
 *      preservado — backend cuida da regra de senha temporária).
 *
 * Não testa o efeito da flag aqui — isso é coberto pelo pytest do follow-up
 * e pelo spec Playwright do SEC-1.
 */
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
    ostensivo: "Ostensivo",
    interno: "Interno",
    reservado: "Reservado",
    secreto: "Secreto",
    ultrassecreto: "Ultrassecreto",
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
const getMock = api.usuarios.get as ReturnType<typeof vi.fn>;
const updateMock = api.usuarios.update as ReturnType<typeof vi.fn>;
const setGruposMock = api.usuarios.setGrupos as ReturnType<typeof vi.fn>;

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

const USUARIO_DETAIL = {
  id: 5,
  nome: "Maria",
  email: "m@x.gov.br",
  cpf: "11111111111",
  id_unidade_trabalho: null,
  cargo: "Analista",
  ativo: true,
  nivel_acesso_sigilo: "interno" as const,
  grupos: [],
  unidades_extras: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  confirmMock.mockResolvedValue(true);
  listMock.mockResolvedValue({
    items: [
      {
        id: 5,
        nome: "Maria",
        email: "m@x.gov.br",
        cpf: "11111111111",
        id_unidade_trabalho: null,
        cargo: "Analista",
        ativo: true,
        nivel_acesso_sigilo: "interno",
      },
    ],
    total: 1,
    page: 1,
    page_size: 20,
  });
  getMock.mockResolvedValue(USUARIO_DETAIL);
  updateMock.mockResolvedValue(USUARIO_DETAIL);
  setGruposMock.mockResolvedValue(USUARIO_DETAIL);
  (api.unidades.list as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [],
    total: 0,
    page: 1,
    page_size: 200,
  });
  (api.grupos.list as ReturnType<typeof vi.fn>).mockResolvedValue([]);
});

async function abrirDialogEdicao() {
  fireEvent.click(await screen.findByRole("button", { name: /Editar/i }));
  await waitFor(() => expect(getMock).toHaveBeenCalledWith(5));
  // Dialog renderizado após resolver get(5)
  await screen.findByRole("dialog");
}

describe("UsuariosPage — edição: copy e payload da senha (SEC-1 follow-up)", () => {
  it("copy informa que a senha é temporária e força troca no próximo acesso", async () => {
    renderPage();
    await abrirDialogEdicao();
    expect(
      screen.getByLabelText(/Nova senha temporária/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/obrigado a alterá-la no próximo acesso/i),
    ).toBeInTheDocument();
  });

  it("salvar sem preencher senha NÃO envia o campo senha no payload", async () => {
    renderPage();
    await abrirDialogEdicao();
    // Altera o cargo para garantir que houve alguma alteração detectável.
    // `fireEvent.change` em vez de `userEvent.type` porque o input é
    // controlado por estado React que recria via spread a cada keystroke —
    // userEvent.type acaba descartando caracteres em condições de corrida
    // com o re-render do diálogo.
    const cargo = screen.getByLabelText(/^Cargo$/i) as HTMLInputElement;
    fireEvent.change(cargo, { target: { value: "Coordenador" } });

    fireEvent.click(screen.getByRole("button", { name: /Salvar/i }));

    await waitFor(() => expect(updateMock).toHaveBeenCalled());
    const [, payload] = updateMock.mock.calls[0];
    expect(payload).toMatchObject({ cargo: "Coordenador" });
    expect(payload).not.toHaveProperty("senha");
  });

  it("salvar com senha preenchida envia `senha` no payload do PUT", async () => {
    renderPage();
    await abrirDialogEdicao();
    const senha = screen.getByLabelText(
      /Nova senha temporária/i,
    ) as HTMLInputElement;
    fireEvent.change(senha, { target: { value: "temp-admin-123" } });

    fireEvent.click(screen.getByRole("button", { name: /Salvar/i }));

    await waitFor(() => expect(updateMock).toHaveBeenCalled());
    const [id, payload] = updateMock.mock.calls[0];
    expect(id).toBe(5);
    expect(payload).toMatchObject({ senha: "temp-admin-123" });
  });
});

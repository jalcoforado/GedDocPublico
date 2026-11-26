/**
 * Formulário de cadastro de usuário no padrão de formulário (2026-11-10):
 * erro só depois da tentativa, foco no primeiro inválido, CPF com máscara na
 * tela e só dígitos no payload, e os dois caminhos de acesso (senha
 * temporária × convite por e-mail) mandando o mesmo que mandavam antes.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
      resetarSenha: vi.fn(),
      reenviarConvite: vi.fn(),
    },
    unidades: { list: vi.fn() },
    grupos: { list: vi.fn() },
  },
  organogramaApi: { tree: vi.fn().mockResolvedValue([]) },
  NIVEL_SIGILO_LABEL: {
    ostensivo: "Ostensivo", interno: "Interno", reservado: "Reservado",
    secreto: "Secreto", ultrassecreto: "Ultrassecreto",
  },
}));

const branding = vi.hoisted(() => ({ conta_por_email: false }));
vi.mock("@/lib/branding", () => ({ useBranding: () => branding }));

vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => vi.fn().mockResolvedValue(true) }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: () => true, perms: { is_super_usuario: false } }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const createMock = api.usuarios.create as ReturnType<typeof vi.fn>;

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

async function abrirNovo() {
  fireEvent.click(await screen.findByRole("button", { name: /Novo usuário/i }));
  return screen.findByRole("dialog");
}

beforeEach(() => {
  vi.clearAllMocks();
  branding.conta_por_email = false;
  (api.usuarios.list as ReturnType<typeof vi.fn>).mockResolvedValue({
    items: [], total: 0, page: 1, page_size: 20,
  });
  (api.grupos.list as ReturnType<typeof vi.fn>).mockResolvedValue([
    { id: 1, grupo: "Protocolo", id_nivel: 1, id_sistema: 1 },
  ]);
  createMock.mockResolvedValue({ id: 9, email: "ana@pm.gov.br" });
});

describe("UsuariosPage — formulário de cadastro", () => {
  it("abre sem nenhum erro à vista", async () => {
    renderPage();
    const dialog = await abrirNovo();
    expect(within(dialog).queryByText(/Informe o nome/i)).not.toBeInTheDocument();
    expect(dialog.querySelector('[aria-invalid="true"]')).toBeNull();
  });

  it("erro aparece ao sair do campo vazio, com a instrução de conserto", async () => {
    renderPage();
    const dialog = await abrirNovo();
    const nome = within(dialog).getByLabelText(/^Nome completo/i);
    fireEvent.blur(nome);
    expect(await within(dialog).findByText("Informe o nome completo.")).toBeInTheDocument();
    expect(nome).toHaveAttribute("aria-invalid", "true");
    // Os campos ainda não visitados continuam limpos.
    expect(within(dialog).getByLabelText(/^CPF/i)).not.toHaveAttribute("aria-invalid", "true");
  });

  it("enviar vazio mostra os erros, foca o primeiro e não chama a API", async () => {
    renderPage();
    const dialog = await abrirNovo();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cadastrar usuário" }));
    expect(await within(dialog).findByText("Informe o nome completo.")).toBeInTheDocument();
    expect(within(dialog).getByText("Informe o CPF.")).toBeInTheDocument();
    expect(within(dialog).getByText(/Defina a senha temporária/i)).toBeInTheDocument();
    expect(document.activeElement).toBe(within(dialog).getByLabelText(/^Nome completo/i));
    expect(createMock).not.toHaveBeenCalled();
  });

  it("CPF aparece com máscara e segue só com dígitos; senha temporária vai no payload", async () => {
    renderPage();
    const dialog = await abrirNovo();
    fireEvent.change(within(dialog).getByLabelText(/^Nome completo/i), { target: { value: "Ana Lima" } });
    fireEvent.change(within(dialog).getByLabelText(/^E-mail/i), { target: { value: "ana@pm.gov.br" } });
    const cpf = within(dialog).getByLabelText(/^CPF/i) as HTMLInputElement;
    fireEvent.change(cpf, { target: { value: "12345678901" } });
    expect(cpf.value).toBe("123.456.789-01");
    fireEvent.change(within(dialog).getByLabelText(/^Senha temporária/i), { target: { value: "temp-123" } });
    fireEvent.click(within(dialog).getByLabelText("Protocolo"));
    fireEvent.click(within(dialog).getByRole("button", { name: "Cadastrar usuário" }));

    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(createMock.mock.calls[0][0]).toMatchObject({
      nome: "Ana Lima",
      email: "ana@pm.gov.br",
      cpf: "12345678901",
      senha: "temp-123",
      grupos: [1],
    });
  });

  it("com conta por e-mail: sem campo de senha e o cadastro vai sem senha", async () => {
    branding.conta_por_email = true;
    renderPage();
    const dialog = await abrirNovo();
    expect(within(dialog).queryByLabelText(/Senha temporária/i)).not.toBeInTheDocument();
    expect(within(dialog).getByText("Acesso por convite")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText(/^Nome completo/i), { target: { value: "Ana Lima" } });
    fireEvent.change(within(dialog).getByLabelText(/^E-mail/i), { target: { value: "ana@pm.gov.br" } });
    fireEvent.change(within(dialog).getByLabelText(/^CPF/i), { target: { value: "123.456.789-01" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cadastrar e enviar convite" }));

    await waitFor(() => expect(createMock).toHaveBeenCalled());
    const payload = createMock.mock.calls[0][0];
    expect(payload.cpf).toBe("12345678901");
    expect(payload).not.toHaveProperty("senha");
  });
});

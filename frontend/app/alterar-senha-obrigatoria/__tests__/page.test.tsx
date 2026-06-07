/**
 * SEC-1 Commit 5 — tela /alterar-senha-obrigatoria.
 *
 * Cobre:
 *  C1. Renderiza mensagem correta e form para usuário flagged.
 *  C2. Não renderiza sidebar/layout principal (tela standalone).
 *  C3. Usuário não autenticado (api.me rejeita) → /login.
 *  C4. Usuário sem flag (api.me retorna flag=false) → /home.
 *  C5. Troca de senha com sucesso → /home (via onSuccess).
 *  C6. Senha não fica visível no DOM após submit/erro/limpeza.
 *  C7. Logout → /login.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AlterarSenhaObrigatoriaPage from "@/app/alterar-senha-obrigatoria/page";

const routerReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace, push: vi.fn() }),
}));

const apiMe = vi.fn();
const apiAlterarSenha = vi.fn();
const apiLogout = vi.fn();
vi.mock("@/lib/api", async () => {
  const actual: any = await vi.importActual("@/lib/api");
  return {
    ...actual,
    api: {
      me: () => apiMe(),
      alterarSenha: (a: string, n: string) => apiAlterarSenha(a, n),
      logout: () => apiLogout(),
    },
  };
});

const toastSuccess = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

beforeEach(() => {
  routerReplace.mockReset();
  apiMe.mockReset();
  apiAlterarSenha.mockReset();
  apiLogout.mockReset();
  toastSuccess.mockReset();
});

afterEach(() => {
  // nada
});

function flaggedMe() {
  return {
    id: 1,
    nome: "Usuario Teste",
    email: "teste@local",
    cargo: null,
    id_unidade_trabalho: null,
    must_change_password: true,
  };
}

describe("/alterar-senha-obrigatoria", () => {
  it("C1: renderiza mensagem e form quando usuário tem flag=true", async () => {
    apiMe.mockResolvedValue(flaggedMe());
    render(<AlterarSenhaObrigatoriaPage />);
    expect(
      await screen.findByText(/altere sua senha temporária antes de continuar/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /troca de senha obrigatória/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/senha atual/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Nova senha/i)).toBeInTheDocument();
  });

  it("C2: NÃO renderiza Sidebar/Header do layout principal", async () => {
    apiMe.mockResolvedValue(flaggedMe());
    render(<AlterarSenhaObrigatoriaPage />);
    await screen.findByText(/altere sua senha temporária/i);
    // O Sidebar tem role=navigation e Header tem role=banner.
    // Como a página está fora do (app), nada disso deve existir.
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByRole("banner")).not.toBeInTheDocument();
  });

  it("C3: api.me rejeita → router.replace('/login')", async () => {
    const { ApiError } = await import("@/lib/api");
    apiMe.mockRejectedValue(new ApiError("Unauthorized", 401));
    render(<AlterarSenhaObrigatoriaPage />);
    await waitFor(() =>
      expect(routerReplace).toHaveBeenCalledWith("/login"),
    );
  });

  it("C4: usuário sem flag → router.replace('/home')", async () => {
    apiMe.mockResolvedValue({
      ...flaggedMe(),
      must_change_password: false,
    });
    render(<AlterarSenhaObrigatoriaPage />);
    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/home"));
  });

  it("C5: troca com sucesso → router.replace('/home')", async () => {
    apiMe.mockResolvedValue(flaggedMe());
    apiAlterarSenha.mockResolvedValue(undefined);
    const u = userEvent.setup();
    render(<AlterarSenhaObrigatoriaPage />);
    await u.type(await screen.findByLabelText(/senha atual/i), "temp-pass");
    await u.type(screen.getByLabelText(/^Nova senha/i), "nova-senha-1");
    await u.type(screen.getByLabelText(/^Confirmar/i), "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() =>
      expect(apiAlterarSenha).toHaveBeenCalledWith("temp-pass", "nova-senha-1"),
    );
    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/home"));
  });

  it("C6: senha é limpa do DOM após troca com sucesso", async () => {
    apiMe.mockResolvedValue(flaggedMe());
    apiAlterarSenha.mockResolvedValue(undefined);
    const u = userEvent.setup();
    render(<AlterarSenhaObrigatoriaPage />);
    const atual = (await screen.findByLabelText(
      /senha atual/i,
    )) as HTMLInputElement;
    const nova = screen.getByLabelText(/^Nova senha/i) as HTMLInputElement;
    const conf = screen.getByLabelText(/^Confirmar/i) as HTMLInputElement;
    await u.type(atual, "temp-pass");
    await u.type(nova, "nova-senha-1");
    await u.type(conf, "nova-senha-1");
    await u.click(screen.getByRole("button", { name: /alterar senha/i }));
    await waitFor(() => expect(apiAlterarSenha).toHaveBeenCalled());
    await waitFor(() => expect(atual.value).toBe(""));
    expect(nova.value).toBe("");
    expect(conf.value).toBe("");
  });

  it("C7: botão Sair chama logout e redireciona para /login", async () => {
    apiMe.mockResolvedValue(flaggedMe());
    apiLogout.mockResolvedValue(undefined);
    const u = userEvent.setup();
    render(<AlterarSenhaObrigatoriaPage />);
    await u.click(await screen.findByRole("button", { name: /sair/i }));
    await waitFor(() => expect(apiLogout).toHaveBeenCalled());
    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/login"));
  });
});

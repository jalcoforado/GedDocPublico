/**
 * Login do servidor com 2FA por e-mail (0136) e "Não lembro a senha".
 *
 * A senha certa NÃO leva para dentro quando o backend pede o código: a tela
 * troca para o passo do código, e só a resposta de `/auth/login/2fa` (com a
 * sessão) faz o redirect. "Não lembro a senha" pede o link por e-mail — não
 * mostra mais o recado "peça ao administrador".
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const routerPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
}));

const apiLogin = vi.fn();
const login2fa = vi.fn();
const esqueciSenha = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    login: (e: string, s: string) => apiLogin(e, s),
    conta: {
      login2fa: (d: string, c: string, l: boolean) => login2fa(d, c, l),
      reenviarCodigo: vi.fn(),
      esqueciSenha: (e: string) => esqueciSenha(e),
    },
  },
}));

// A conta por e-mail nasce desligada (2026-11-09); cada teste diz se a quer.
const branding = { nome: "Aprimora Test", cor_primaria: null, logo_url: null, conta_por_email: true };
vi.mock("@/lib/branding", () => ({
  useBranding: () => branding,
}));

const SESSAO = {
  access_token: "tok",
  token_type: "bearer",
  expires_in: 3600,
  usuario_id: 1,
  usuario_email: "x@x",
  nome: "X",
  must_change_password: false,
};

beforeEach(() => {
  routerPush.mockReset();
  apiLogin.mockReset();
  login2fa.mockReset();
  esqueciSenha.mockReset();
  branding.conta_por_email = true;
});

describe("login com código por e-mail", () => {
  it("senha certa sem computador lembrado: pede o código e só entra com ele", async () => {
    apiLogin.mockResolvedValue({
      ...SESSAO,
      access_token: null,
      requer_2fa: true,
      desafio: "desafio-1",
      email_mascarado: "ad•••@prefeitura.gov.br",
    });
    login2fa.mockResolvedValue(SESSAO);
    const u = userEvent.setup();
    render(<LoginPage />);

    await u.click(screen.getByRole("button", { name: /entrar como servidor/i }));
    expect(await screen.findByText("ad•••@prefeitura.gov.br")).toBeInTheDocument();
    expect(routerPush).not.toHaveBeenCalled();

    const entrar = screen.getByRole("button", { name: "Entrar" });
    expect(entrar).toBeDisabled();
    await u.type(screen.getByLabelText("Código de verificação"), "12a3456");
    expect(screen.getByLabelText("Código de verificação")).toHaveValue("123456");
    await u.click(entrar);

    // "Lembrar este computador" vem marcado: é o que a maioria quer.
    await waitFor(() => expect(login2fa).toHaveBeenCalledWith("desafio-1", "123456", true));
    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/home"));
  });

  it("código errado mostra o erro e continua no passo do código", async () => {
    apiLogin.mockResolvedValue({ ...SESSAO, access_token: null, requer_2fa: true, desafio: "d" });
    login2fa.mockRejectedValue(new Error("Código inválido ou expirado."));
    const u = userEvent.setup();
    render(<LoginPage />);
    await u.click(screen.getByRole("button", { name: /entrar como servidor/i }));
    await u.type(await screen.findByLabelText("Código de verificação"), "000000");
    await u.click(screen.getByRole("button", { name: "Entrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Código inválido ou expirado.");
    expect(screen.getByLabelText("Código de verificação")).toHaveValue("");
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("computador lembrado: a resposta já traz a sessão e entra direto", async () => {
    apiLogin.mockResolvedValue({ ...SESSAO, requer_2fa: false });
    const u = userEvent.setup();
    render(<LoginPage />);
    await u.click(screen.getByRole("button", { name: /entrar como servidor/i }));
    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/home"));
    expect(login2fa).not.toHaveBeenCalled();
  });
});

describe("não lembro a senha", () => {
  it("pede o link por e-mail e mostra o aviso neutro do backend", async () => {
    esqueciSenha.mockResolvedValue({ detail: "Se houver uma conta com esse e-mail, enviamos um link." });
    const u = userEvent.setup();
    render(<LoginPage />);

    await u.click(screen.getByRole("button", { name: "Não lembro a senha" }));
    expect(screen.queryByText(/peça a redefinição/i)).toBeNull();
    const campo = screen.getByPlaceholderText("E-mail");
    await u.clear(campo);
    await u.type(campo, "maria@prefeitura.gov.br");
    await u.click(screen.getByRole("button", { name: "Enviar link" }));

    await waitFor(() => expect(esqueciSenha).toHaveBeenCalledWith("maria@prefeitura.gov.br"));
    expect(await screen.findByRole("status")).toHaveTextContent("Se houver uma conta");
    expect(apiLogin).not.toHaveBeenCalled();
  });

  it("com a conta por e-mail desligada, o link não aparece", () => {
    branding.conta_por_email = false;
    render(<LoginPage />);
    expect(screen.queryByRole("button", { name: "Não lembro a senha" })).toBeNull();
  });
});

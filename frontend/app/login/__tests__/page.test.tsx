/**
 * SEC-1 Commit 6 — login redireciona conforme must_change_password.
 *
 * Cobre a otimização do Commit 6 (pular o passo extra por /modulos quando o
 * backend já sinaliza a flag direto no LoginResponse) e, desde a F2 Task 5,
 * o novo destino do login bem-sucedido: o launcher de módulos, não mais o
 * dashboard fixo /home. O guard do AuthProvider (Commit 5) continua como
 * defesa em profundidade.
 *
 * Os campos visuais/hero do LoginPage não são testados aqui — fora do
 * escopo desta unidade.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

const routerPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: vi.fn() }),
}));

const apiLogin = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { login: (e: string, s: string) => apiLogin(e, s) },
}));

vi.mock("@/lib/branding", () => ({
  useBranding: () => ({ nome: "Aprimora Test", cor_primaria: null, logo_url: null }),
}));

beforeEach(() => {
  routerPush.mockReset();
  apiLogin.mockReset();
});

afterEach(() => {
  // nada
});

function loginResponse(opts: { flag: boolean }) {
  return {
    access_token: "tok",
    token_type: "bearer",
    expires_in: 3600,
    usuario_id: 1,
    usuario_email: "x@x",
    nome: "X",
    must_change_password: opts.flag,
  };
}

describe("LoginPage SEC-1 redirect", () => {
  it("usuário NÃO flagged → router.push('/modulos')", async () => {
    apiLogin.mockResolvedValue(loginResponse({ flag: false }));
    const u = userEvent.setup();
    render(<LoginPage />);
    // Em dev as credenciais vêm pré-preenchidas; só submetemos.
    await u.click(screen.getByRole("button", { name: /entrar/i }));
    await waitFor(() => expect(apiLogin).toHaveBeenCalled());
    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/modulos"));
  });

  it("usuário FLAGGED → router.push('/alterar-senha-obrigatoria')", async () => {
    apiLogin.mockResolvedValue(loginResponse({ flag: true }));
    const u = userEvent.setup();
    render(<LoginPage />);
    await u.click(screen.getByRole("button", { name: /entrar/i }));
    await waitFor(() => expect(apiLogin).toHaveBeenCalled());
    await waitFor(() =>
      expect(routerPush).toHaveBeenCalledWith("/alterar-senha-obrigatoria"),
    );
  });

  it("falha (api.login rejeita) → não navega e mostra erro", async () => {
    apiLogin.mockRejectedValue(new Error("Credenciais inválidas"));
    const u = userEvent.setup();
    render(<LoginPage />);
    await u.click(screen.getByRole("button", { name: /entrar/i }));
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/credenciais/i),
    );
    expect(routerPush).not.toHaveBeenCalled();
  });
});

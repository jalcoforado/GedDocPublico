/**
 * Sem esta mudanca o launcher existe e ninguem chega nele. Com ela, a troca de
 * senha obrigatoria continua tendo precedencia — e requisito de seguranca
 * (SEC-1) e nao pode ser atropelada pela porta de entrada nova.
 *
 * Mocka `@/lib/api` (nao `@/lib/auth`) porque e isso que `app/login/page.tsx`
 * chama de verdade — o login nao passa pelo AuthProvider.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: push }),
  useSearchParams: () => new URLSearchParams(),
}));

const login = vi.fn();
vi.mock("@/lib/api", () => ({ api: { login: (...a: unknown[]) => login(...a) } }));

import LoginPage from "@/app/login/page";

async function submeter() {
  render(<LoginPage />);
  fireEvent.change(screen.getByLabelText(/e-?mail/i), { target: { value: "a@b.test" } });
  // selector: "input" — "senha" solto tambem casa com o aria-label do botao
  // de mostrar/ocultar senha ("Mostrar senha"), que nao e o campo.
  fireEvent.change(screen.getByLabelText(/senha/i, { selector: "input" }), {
    target: { value: "x" },
  });
  fireEvent.click(screen.getByRole("button", { name: /entrar/i }));
}

describe("destino apos o login", () => {
  // push/login sao vi.fn() de escopo de modulo — sem limpar, a chamada do
  // primeiro teste vaza pro historico do segundo (spy acumula entre `it`s).
  afterEach(() => {
    push.mockClear();
    login.mockClear();
  });

  it("vai para o launcher", async () => {
    login.mockResolvedValue({ must_change_password: false });
    await submeter();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/modulos"));
  });

  it("troca de senha obrigatoria tem precedencia sobre o launcher", async () => {
    login.mockResolvedValue({ must_change_password: true });
    await submeter();
    await waitFor(() => expect(push).toHaveBeenCalledWith("/alterar-senha-obrigatoria"));
    expect(push).not.toHaveBeenCalledWith("/modulos");
  });
});

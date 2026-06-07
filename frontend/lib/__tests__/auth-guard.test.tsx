/**
 * SEC-1 Commit 5 — guard no AuthProvider via /auth/me.
 *
 * Cobre:
 *  B1. Usuário com flag=true → router.replace("/alterar-senha-obrigatoria").
 *  B2. Usuário com flag=false → segue fluxo normal (sem redirect).
 *  B3. Usuário com flag=true, já em /alterar-senha-obrigatoria → não redireciona.
 *  B4. Usuário não autenticado (api.me reject) → router.replace("/login").
 *
 * AuthProvider chama `Promise.all([api.me(), api.permissoes()])` no mount.
 * Para evitar re-execução em cada navegação interna, o useEffect tem
 * `[router]` como dep — testado indiretamente: 1 chamada por mount.
 */
import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/lib/auth";

const routerReplace = vi.fn();
const routerPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace, push: routerPush }),
}));

const apiMe = vi.fn();
const apiPermissoes = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { me: () => apiMe(), permissoes: () => apiPermissoes() },
}));

function setLocation(pathname: string) {
  delete (window as any).location;
  (window as any).location = { pathname, assign: vi.fn() };
}

const PERMS_OK = {
  usuario_id: 1,
  is_super_usuario: true,
  nivel_valor: 0,
  permissoes: [],
};

beforeEach(() => {
  routerReplace.mockReset();
  routerPush.mockReset();
  apiMe.mockReset();
  apiPermissoes.mockReset();
});

afterEach(() => {
  // nada
});

describe("AuthProvider guard must_change_password", () => {
  it("B1: usuário flagged é redirecionado para /alterar-senha-obrigatoria", async () => {
    setLocation("/home");
    apiMe.mockResolvedValue({
      id: 1,
      nome: "X",
      email: "x@x",
      cargo: null,
      id_unidade_trabalho: null,
      must_change_password: true,
    });
    apiPermissoes.mockResolvedValue(PERMS_OK);
    render(
      <AuthProvider>
        <div>conteudo</div>
      </AuthProvider>,
    );
    await waitFor(() =>
      expect(routerReplace).toHaveBeenCalledWith("/alterar-senha-obrigatoria"),
    );
  });

  it("B2: usuário sem flag não dispara redirect do gate", async () => {
    setLocation("/home");
    apiMe.mockResolvedValue({
      id: 1,
      nome: "X",
      email: "x@x",
      cargo: null,
      id_unidade_trabalho: null,
      must_change_password: false,
    });
    apiPermissoes.mockResolvedValue(PERMS_OK);
    render(
      <AuthProvider>
        <div>conteudo</div>
      </AuthProvider>,
    );
    await waitFor(() => expect(apiMe).toHaveBeenCalledTimes(1));
    // Pequena espera para garantir que nada veio depois.
    await new Promise((r) => setTimeout(r, 10));
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("B3: usuário flagged JÁ em /alterar-senha-obrigatoria não re-redireciona", async () => {
    setLocation("/alterar-senha-obrigatoria");
    apiMe.mockResolvedValue({
      id: 1,
      nome: "X",
      email: "x@x",
      cargo: null,
      id_unidade_trabalho: null,
      must_change_password: true,
    });
    apiPermissoes.mockResolvedValue(PERMS_OK);
    render(
      <AuthProvider>
        <div>conteudo</div>
      </AuthProvider>,
    );
    await waitFor(() => expect(apiMe).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 10));
    expect(routerReplace).not.toHaveBeenCalledWith(
      "/alterar-senha-obrigatoria",
    );
  });

  it("B4: 401 (api.me reject) continua redirecionando para /login", async () => {
    setLocation("/home");
    apiMe.mockRejectedValue(new Error("Unauthorized"));
    apiPermissoes.mockRejectedValue(new Error("Unauthorized"));
    render(
      <AuthProvider>
        <div>conteudo</div>
      </AuthProvider>,
    );
    await waitFor(() => expect(routerReplace).toHaveBeenCalledWith("/login"));
  });

  it("B5: AuthProvider não dispara me/permissoes em loop por navegação", async () => {
    // React 18 StrictMode roda useEffect 2x em dev/test — aceitar 1 ou 2,
    // mas garantir que NÃO está executando em loop (>2 indicaria que o
    // pathname entrou na dep array por engano, por exemplo).
    setLocation("/home");
    apiMe.mockResolvedValue({
      id: 1,
      nome: "X",
      email: "x@x",
      cargo: null,
      id_unidade_trabalho: null,
      must_change_password: false,
    });
    apiPermissoes.mockResolvedValue(PERMS_OK);
    render(
      <AuthProvider>
        <div>conteudo</div>
      </AuthProvider>,
    );
    await waitFor(() => expect(apiMe).toHaveBeenCalled());
    await new Promise((r) => setTimeout(r, 30));
    expect(apiMe.mock.calls.length).toBeLessThanOrEqual(2);
    expect(apiPermissoes.mock.calls.length).toBeLessThanOrEqual(2);
  });
});

/**
 * LoginPage + cliente de API real (sem mock de `@/lib/api`) — prova em nível
 * de tela que um 401 de credencial errada em /auth/login:
 *  1. NÃO dispara o interceptor de sessão expirada (`window.location.assign`
 *     nunca é chamado);
 *  2. a mensagem de erro do backend chega ao `role="alert"` da tela.
 *
 * Diferença deliberada de `page.test.tsx`: lá `@/lib/api` é mockado (testa
 * só o roteamento pós-login). Aqui só `next/navigation` e `@/lib/branding`
 * são mockados — `fetch` é o único ponto de entrada simulado, então
 * `api.login()` roda de verdade e passa pelo interceptor real de
 * `lib/api.ts`. Ver também `lib/__tests__/api-interceptor-sessao.test.ts`
 * (B2/B2b), que prova por inversão que a supressão de `/auth/login` é o que
 * impede este teste de virar um loop.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";
import { _resetGuardSessaoExpiradaParaTeste } from "@/lib/api";

const routerPush = vi.fn();
const routerReplace = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: routerPush, replace: routerReplace }),
}));

vi.mock("@/lib/branding", () => ({
  useBranding: () => ({ nome: "Aprimora Test", cor_primaria: null, logo_url: null }),
}));

const fetchMock = vi.fn();

function setLocation(pathname: string) {
  delete (window as any).location;
  (window as any).location = { pathname, assign: vi.fn() };
}

beforeEach(() => {
  routerPush.mockReset();
  routerReplace.mockReset();
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  _resetGuardSessaoExpiradaParaTeste();
  setLocation("/login");
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LoginPage com cliente de API real — 401 de credencial errada", () => {
  it("mostra a mensagem do backend e NÃO redireciona (nem router, nem window.location)", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "E-mail ou senha inválidos" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );

    const u = userEvent.setup();
    render(<LoginPage />);
    await u.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /e-mail ou senha inválidos/i,
      ),
    );
    expect(routerPush).not.toHaveBeenCalled();
    expect(routerReplace).not.toHaveBeenCalled();
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});

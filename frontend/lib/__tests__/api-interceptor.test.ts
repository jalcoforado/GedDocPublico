/**
 * SEC-1 Commit 5 — interceptor 403 X-Must-Change-Password em api.ts.
 *
 * Cobre:
 *  A1. 403 + header → redireciona para /alterar-senha-obrigatoria.
 *  A2. 403 sem header → NÃO redireciona.
 *  A3. 403 + header, já em /alterar-senha-obrigatoria → NÃO redireciona.
 *  A4. 403 + header em /login → NÃO redireciona.
 *  A5. 403 + header em /cidadao/* → NÃO redireciona.
 *
 * Estratégia: mock global `fetch` e espía `window.location.assign`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

const fetchMock = vi.fn();

function setLocation(pathname: string) {
  // jsdom permite redefinir `window.location.pathname` via Object.defineProperty
  // ou simplesmente sobrescrever todo o location. Usamos a abordagem mais
  // robusta: substituir o location por um objeto controlado.
  delete (window as any).location;
  (window as any).location = {
    pathname,
    assign: vi.fn(),
  };
}

function mockFetchOnce(status: number, headers: Record<string, string> = {}) {
  fetchMock.mockResolvedValueOnce(
    new Response("{}", {
      status,
      headers: { "content-type": "application/json", ...headers },
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("interceptor 403 X-Must-Change-Password", () => {
  it("A1: 403 + header redireciona para /alterar-senha-obrigatoria", async () => {
    setLocation("/home");
    mockFetchOnce(403, { "x-must-change-password": "true" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).toHaveBeenCalledWith(
      "/alterar-senha-obrigatoria",
    );
  });

  it("A2: 403 sem header NÃO redireciona", async () => {
    setLocation("/home");
    mockFetchOnce(403);
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("A3: 403 + header já em /alterar-senha-obrigatoria NÃO redireciona", async () => {
    setLocation("/alterar-senha-obrigatoria");
    mockFetchOnce(403, { "x-must-change-password": "true" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("A4: 403 + header em /login NÃO redireciona", async () => {
    setLocation("/login");
    mockFetchOnce(403, { "x-must-change-password": "true" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("A5: 403 + header em /cidadao/processos NÃO redireciona", async () => {
    setLocation("/cidadao/processos");
    mockFetchOnce(403, { "x-must-change-password": "true" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("regressão: 200 não dispara o interceptor", async () => {
    setLocation("/home");
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: 1,
          nome: "X",
          email: "x@x",
          cargo: null,
          id_unidade_trabalho: null,
          must_change_password: false,
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    const u = await api.me();
    expect(u.must_change_password).toBe(false);
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("regressão: 401 não dispara o interceptor (só 403)", async () => {
    setLocation("/home");
    mockFetchOnce(401, { "x-must-change-password": "true" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});

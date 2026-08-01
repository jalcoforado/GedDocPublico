/**
 * Sessão expirada — interceptor de 401 em `request()` (lib/api.ts).
 *
 * O token tem TTL de 1h; se expirar em pleno uso (fora da montagem do
 * AuthProvider), as chamadas seguintes tomavam 401 sem tratamento nenhum e
 * os componentes quebravam esperando lista e recebendo objeto de erro
 * (`TypeError: s.map is not a function`). Este arquivo cobre o interceptor
 * que resolve isso — ver `_interceptaSessaoExpirada` em `lib/api.ts`.
 *
 * Casos:
 *  B1. 401 numa chamada comum → redireciona pro /login (admin).
 *  B2. 401 na própria requisição de login (`/auth/login`) → NÃO redireciona
 *      (senão a tela de login vira loop e o usuário nunca vê a mensagem de
 *      credencial inválida).
 *  B3. 401 já em /login → NÃO redireciona (ruído, risco de loop com o
 *      middleware).
 *  B4. 401 no cliente do cidadão (`requestCidadao`, ex. `api.cidadao.me()`)
 *      → NÃO chama assign pro /login do admin. Portal do cidadão é outro
 *      app, outro cookie, outro login.
 *  B5. Vários 401 concorrentes (poll do sino de notificações expirando ao
 *      mesmo tempo) → um único redirect, não um por chamada.
 *
 * Estratégia igual à de api-interceptor.test.ts: mock global `fetch`,
 * espiona `window.location.assign`, sem mockar `@/lib/api` — o objetivo é
 * exercitar `request()`/`requestCidadao()` de verdade.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, notificacoesApi, _resetGuardSessaoExpiradaParaTeste } from "@/lib/api";

const fetchMock = vi.fn();

function setLocation(pathname: string) {
  delete (window as any).location;
  (window as any).location = {
    pathname,
    assign: vi.fn(),
  };
}

function mockFetchOnce(status: number, body: unknown = {}) {
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  fetchMock.mockReset();
  _resetGuardSessaoExpiradaParaTeste();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("interceptor 401 — sessão expirada", () => {
  it("B1: 401 numa chamada comum redireciona pro /login", async () => {
    setLocation("/home");
    mockFetchOnce(401, { detail: "Não autenticado" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).toHaveBeenCalledWith("/login");
    expect(window.location.assign).toHaveBeenCalledTimes(1);
  });

  it("B2: 401 em /auth/login (credencial errada) NÃO redireciona", async () => {
    setLocation("/login");
    mockFetchOnce(401, { detail: "E-mail ou senha inválidos" });
    await expect(api.login("x@x.test", "errada")).rejects.toThrow(
      "E-mail ou senha inválidos",
    );
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("B2b: 401 em /auth/login mesmo fora da tela /login (defesa em profundidade) NÃO redireciona", async () => {
    // path === "/auth/login" é isento independente do pathname corrente —
    // é a própria chamada de login que falhou, não uma sessão que expirou
    // no meio da navegação.
    setLocation("/algum/outro/lugar");
    mockFetchOnce(401, { detail: "E-mail ou senha inválidos" });
    await expect(api.login("x@x.test", "errada")).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("B3: 401 já em /login NÃO redireciona (evita loop)", async () => {
    setLocation("/login");
    mockFetchOnce(401, { detail: "Não autenticado" });
    await expect(api.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("B4: 401 no cliente do cidadão NÃO chama assign pro /login do admin", async () => {
    setLocation("/cidadao/processos");
    mockFetchOnce(401, { detail: "Não autenticado" });
    await expect(api.cidadao.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("B4b: 401 no cliente do cidadão nem quando a página corrente é do admin", async () => {
    // requestCidadao() nunca chama o interceptor de sessão do admin — não
    // importa o pathname corrente, só qual função de request foi usada.
    setLocation("/home");
    mockFetchOnce(401, { detail: "Não autenticado" });
    await expect(api.cidadao.me()).rejects.toThrow();
    expect(window.location.assign).not.toHaveBeenCalled();
  });

  it("B5: vários 401 concorrentes disparam um único redirect", async () => {
    setLocation("/home");
    mockFetchOnce(401, { detail: "Não autenticado" });
    mockFetchOnce(401, { detail: "Não autenticado" });
    mockFetchOnce(401, { detail: "Não autenticado" });
    const chamadas = [
      notificacoesApi.listarMinhas({ limit: 30 }).catch(() => {}),
      api.me().catch(() => {}),
      api.modulos().catch(() => {}),
    ];
    await Promise.all(chamadas);
    expect(window.location.assign).toHaveBeenCalledTimes(1);
    expect(window.location.assign).toHaveBeenCalledWith("/login");
  });

  it("regressão: 200 não dispara o interceptor de sessão", async () => {
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
    await api.me();
    expect(window.location.assign).not.toHaveBeenCalled();
  });
});

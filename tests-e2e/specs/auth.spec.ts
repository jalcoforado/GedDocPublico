import { expect, test } from "@playwright/test";

/**
 * Golden paths de autenticação:
 *  - login admin Python responde com JWT válido
 *  - /me confirma o token
 *  - PHP legacy (porta 8081 do host = `protocolo:80` na network) ainda responde
 *    ao /login dele (não verificamos o conteúdo — só que o servidor está vivo
 *    e não foi quebrado pelas alterações de senha/jwt).
 */

test.describe("Auth admin (Python)", () => {
  test("login + /me", async ({ request }) => {
    const login = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "admin123" },
    });
    expect(login.ok()).toBeTruthy();
    const body = await login.json();
    expect(body.access_token).toBeTruthy();
    expect(body.usuario_email).toBe("admin@local.test");

    const me = await request.get("/api/v2/auth/me", {
      headers: { Authorization: `Bearer ${body.access_token}` },
    });
    expect(me.ok()).toBeTruthy();
    const meBody = await me.json();
    expect(meBody.email).toBe("admin@local.test");
  });

  test("senha errada → 401", async ({ request }) => {
    const r = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "errado" },
    });
    expect(r.status()).toBe(401);
  });
});

test.describe("PHP legacy intocado", () => {
  test("Apache responde no PHP base", async ({ request }) => {
    const phpBase = process.env.PHP_BASE ?? "http://protocolo";
    const r = await request.get(`${phpBase}/`, { maxRedirects: 0 });
    // PHP pode redirecionar pra /login ou retornar 200 — o que importa é que o
    // servidor está vivo (não 502/connection refused).
    expect(r.status(), "PHP em :80 do container protocolo deveria responder").toBeLessThan(500);
  });
});

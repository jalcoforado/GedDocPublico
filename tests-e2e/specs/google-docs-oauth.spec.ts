import {
  expect,
  test,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

/**
 * Google Docs OAuth Flow (PR-F Phases 4-5)
 *
 * Testa a integração UI do OAuth do Google Docs:
 *   - Rádio de "Google Docs" desabilitado sem credenciais
 *   - Texto de helper "Conectar agora" visível
 *   - GoogleConnectDialog abre ao clicar no link "Conectar agora"
 *
 * Testes verificam estado UI, não callback OAuth (requer conta Google real).
 */

const ADMIN_EMAIL = "admin@local.test";
const ADMIN_SENHA = "admin123";
const TEST_PROCESSO_ID = 13407;

async function bridgeApiToNginx(
  page: Page,
  context: BrowserContext,
): Promise<void> {
  /**
   * Frontend usa NEXT_PUBLIC_API_URL=http://localhost:8090/api/v2
   * Dentro do container e2e, localhost:8090 não é alcançável.
   * Esta função intercepta fetch do navegador e reescreve para http://nginx.
   */
  await page.route("**/api/v2/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    if (url.hostname !== "localhost") return route.continue();

    const target = `http://nginx${url.pathname}${url.search}`;
    const cookies = await context.cookies("http://nginx");
    const cookieHeader = cookies
      .map((c) => `${c.name}=${c.value}`)
      .join("; ");
    const headers: Record<string, string> = { ...req.headers() };
    if (cookieHeader) headers["cookie"] = cookieHeader;
    delete headers["host"];
    delete headers["origin"];
    delete headers["referer"];

    try {
      const resp = await route.fetch({
        url: target,
        headers,
        maxRedirects: 0,
      });
      await route.fulfill({ response: resp });
    } catch {
      await route.abort();
    }
  });
}

async function loginAdminInContext(ctx: BrowserContext): Promise<void> {
  /**
   * Faz login admin no contexto do navegador via POST /api/v2/auth/login.
   * Backend grava cookie HttpOnly aprimora_token que middleware do Next aceita.
   */
  const r = await ctx.request.post("/api/v2/auth/login", {
    data: { email: ADMIN_EMAIL, senha: ADMIN_SENHA },
  });
  expect(r.ok(), `admin login falhou: ${await r.text()}`).toBeTruthy();
}

test.describe("Google Docs OAuth Flow", () => {
  test("disable Google Docs radio without credentials", async ({
    page,
    context,
  }) => {
    // Login admin para acessar /processos
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);

    // Navigate to processo with documentos tab
    await page.goto(`/processos/${TEST_PROCESSO_ID}?tab=documentos`);

    // Aguarda o botão "Redigir documento" estar visível
    await expect(
      page.getByRole("button", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Click "Redigir documento" button
    await page.click("button:has-text('Redigir documento')");

    // Aguarda diálogo abrir
    await expect(
      page.getByRole("heading", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 5_000 });

    // Find the Google Docs radio button
    const googleRadio = page.locator('input[value="google"]');

    // Verify it's disabled (sem credenciais = disabled)
    await expect(googleRadio).toBeDisabled();
  });

  test("show connect link when no credentials", async ({
    page,
    context,
  }) => {
    // Login admin
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);

    // Navigate to processo with documentos tab
    await page.goto(`/processos/${TEST_PROCESSO_ID}?tab=documentos`);

    // Aguarda o botão "Redigir documento"
    await expect(
      page.getByRole("button", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Click "Redigir documento" button
    await page.click("button:has-text('Redigir documento')");

    // Aguarda diálogo abrir
    await expect(
      page.getByRole("heading", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 5_000 });

    // Verify helper text appears: "Conectar agora"
    await expect(page.locator("text=Conectar agora")).toBeVisible();
  });

  test("open GoogleConnectDialog when link clicked", async ({
    page,
    context,
  }) => {
    // Login admin
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);

    // Navigate to processo with documentos tab
    await page.goto(`/processos/${TEST_PROCESSO_ID}?tab=documentos`);

    // Aguarda o botão "Redigir documento"
    await expect(
      page.getByRole("button", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 10_000 });

    // Click "Redigir documento" button
    await page.click("button:has-text('Redigir documento')");

    // Aguarda diálogo abrir
    await expect(
      page.getByRole("heading", { name: /Redigir documento/i }),
    ).toBeVisible({ timeout: 5_000 });

    // Click "Conectar agora" link
    await page.click("text=Conectar agora");

    // Verify GoogleConnectDialog opens (título do diálogo)
    await expect(
      page.locator("text=Conectar Conta Google"),
    ).toBeVisible({ timeout: 5_000 });
  });
});

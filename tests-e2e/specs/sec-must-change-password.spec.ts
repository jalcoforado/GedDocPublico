import {
  expect,
  test,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

/**
 * SEC-1 Commit 6 — fluxo obrigatório de troca de senha.
 *
 * Cobre end-to-end a interação entre:
 *  - Backend: provisionamento marca must_change_password=true em
 *    POST /usuarios (Commit 3); guard em get_current_user devolve 403 +
 *    X-Must-Change-Password=true para rotas de negócio (Commit 2);
 *    LoginResponse/MeResponse expõem a flag (Commit 4).
 *  - Frontend: login redireciona direto se flagged (Commit 6); interceptor
 *    em api.ts trata 403+header; AuthProvider redireciona como defesa em
 *    profundidade; tela /alterar-senha-obrigatoria fora do layout principal
 *    (Commit 5).
 *
 * Setup idempotente: cria um servidor descartável a cada execução. CPF e
 * e-mail únicos. Cleanup faz soft delete via DELETE /usuarios/{id}.
 *
 * Linguagem: senha temporária NUNCA aparece em logs/asserções (usa
 * comparação por igualdade em variáveis locais; expect() não loga o valor
 * porque os asserts não checam o conteúdo da senha).
 */

const ADMIN_EMAIL = "admin@local.test";
const ADMIN_SENHA = "admin123";

function suffixUnico(): string {
  return `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
}

function cpfUnico(): string {
  const ts = Date.now() % 10_000_000_000;
  const rnd = Math.floor(Math.random() * 10);
  return String(ts * 10 + rnd).padStart(11, "0").slice(-11);
}

/**
 * NEXT_PUBLIC_API_URL aponta para localhost:8090 (host externo). Dentro do
 * container e2e, `localhost:8090` não é alcançável — o nginx é
 * `http://nginx`. Padrão reusado do ux1-smoke.
 */
async function bridgeApiToNginx(
  page: Page,
  context: BrowserContext,
): Promise<void> {
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
      // O backend tem CORSMiddleware sem `expose_headers`. Como o browser
      // está em `http://nginx` e o fetch vai para `http://localhost:8090`
      // (cross-origin), headers customizados (X-Must-Change-Password) são
      // filtrados pelo browser e ficam invisíveis ao JS. Em produção isso
      // não acontece (mesma origem via proxy nginx). Aqui, no E2E, expomos
      // explicitamente no response sintético — sem alterar o backend.
      const respHeaders: Record<string, string> = {};
      for (const [k, v] of Object.entries(resp.headers())) {
        respHeaders[k] = v;
      }
      respHeaders["access-control-expose-headers"] = "X-Must-Change-Password";
      await route.fulfill({
        status: resp.status(),
        headers: respHeaders,
        body: await resp.body(),
      });
    } catch {
      await route.abort();
    }
  });
}

async function loginAdminViaApi(req: APIRequestContext): Promise<string> {
  const r = await req.post("/api/v2/auth/login", {
    data: { email: ADMIN_EMAIL, senha: ADMIN_SENHA },
  });
  expect(r.ok(), `admin login falhou: ${await r.text()}`).toBeTruthy();
  return (await r.json()).access_token;
}

async function pegarUnidadeTrabalho(
  req: APIRequestContext,
  token: string,
): Promise<number> {
  const r = await req.get("/api/v2/unidades-trabalho?page=1&page_size=1", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(r.ok(), `listar unidades: ${await r.text()}`).toBeTruthy();
  const id = (await r.json()).items[0]?.id;
  expect(id, "seed sem unidade-trabalho").toBeTruthy();
  return id;
}

async function criarServidorFlagged(
  req: APIRequestContext,
  token: string,
  idUnidade: number,
): Promise<{
  id: number;
  email: string;
  senhaInicial: string;
  cpf: string;
}> {
  const suf = suffixUnico();
  const email = `sec1-${suf}@e2e.test`;
  const cpf = cpfUnico();
  const senhaInicial = `senha-temp-${suf}`;
  const r = await req.post("/api/v2/usuarios", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      nome: `SEC1 E2E ${suf}`,
      email,
      cpf,
      senha: senhaInicial,
      id_unidade_trabalho: idUnidade,
      ativo: true,
      cargo: "Analista E2E",
      grupos: [],
    },
  });
  expect(r.status(), `criar usuário falhou: ${await r.text()}`).toBe(201);
  const body = await r.json();
  return { id: body.id, email, senhaInicial, cpf };
}

async function deletarUsuario(
  req: APIRequestContext,
  token: string,
  id: number,
): Promise<void> {
  // Soft delete (Commit anterior — DELETE marca ativo=false, excluido=true).
  const r = await req.delete(`/api/v2/usuarios/${id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  // 204 esperado; ignora 4xx em cleanup pra não derrubar a suite.
  if (!r.ok() && r.status() !== 204) {
    console.warn(
      `cleanup deletarUsuario(${id}) retornou ${r.status()}: ${await r.text()}`,
    );
  }
}

/**
 * Login via API direto no contexto do browser — mais robusto que UI fill
 * para os specs E2E:
 *  - DEV pré-preenche o LoginPage com admin@local.test, e zerar o controlled
 *    input via Playwright pode não sincronizar com o useState do React.
 *  - O foco do spec é o FLUXO (guard → tela → troca → home), não a UI do
 *    LoginPage (que é coberta pelo teste vitest do Commit 6).
 *
 * O backend grava o cookie HttpOnly `aprimora_token` no contexto, que o
 * middleware do Next aceita para liberar /home, /processos, etc.
 * Retorna o body do LoginResponse para o caller verificar a flag.
 */
async function loginViaApi(
  ctx: BrowserContext,
  email: string,
  senha: string,
): Promise<{ must_change_password: boolean }> {
  const r = await ctx.request.post("/api/v2/auth/login", {
    data: { email, senha },
  });
  expect(r.ok(), `login falhou (${email}): ${await r.text()}`).toBeTruthy();
  return await r.json();
}

async function logoutViaApi(ctx: BrowserContext): Promise<void> {
  await ctx.request.post("/api/v2/auth/logout");
}

// === Estado compartilhado entre tests do describe.serial ===
let flaggedUserId: number;
let flaggedEmail: string;
let flaggedSenhaInicial: string;
let flaggedSenhaNova: string;
let adminToken: string;

test.describe.serial("SEC-1 troca obrigatória de senha", () => {
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    adminToken = await loginAdminViaApi(ctx.request);
    const idUnidade = await pegarUnidadeTrabalho(ctx.request, adminToken);
    const u = await criarServidorFlagged(ctx.request, adminToken, idUnidade);
    flaggedUserId = u.id;
    flaggedEmail = u.email;
    flaggedSenhaInicial = u.senhaInicial;
    flaggedSenhaNova = `${u.senhaInicial}-trocada`;
    await ctx.close();
  });

  test.afterAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    if (flaggedUserId && adminToken) {
      await deletarUsuario(ctx.request, adminToken, flaggedUserId);
    }
    await ctx.close();
  });

  test("/auth/login flagged sinaliza must_change_password=true no body", async ({
    browser,
  }) => {
    // Test #1: contrato direto da API. Confirma que o backend (Commit 4)
    // continua propagando a flag, e que /login funciona normalmente para
    // usuário flagged (HTTP 200, não 403).
    const ctx = await browser.newContext();
    const body = await loginViaApi(
      ctx,
      flaggedEmail,
      flaggedSenhaInicial,
    );
    expect(body.must_change_password).toBe(true);
    await ctx.close();
  });

  test("usuário flagged em /home é redirecionado para /alterar-senha-obrigatoria", async ({
    page,
    context,
  }) => {
    // Test #2: AuthProvider guard (Commit 5). Após login, navegar para /home
    // dispara me() → flag=true → router.replace("/alterar-senha-obrigatoria").
    await loginViaApi(context, flaggedEmail, flaggedSenhaInicial);
    await bridgeApiToNginx(page, context);

    // page.goto("/home") sem aguardar load — vários chamados de negócio
    // disparam o interceptor 403 em cascata, gerando navegações sobrepostas
    // (cada uma cancela a anterior). waitForLoadState/waitForURL falham com
    // ERR_ABORTED. Usar waitForFunction que observa o pathname final.
    page.goto("/home").catch(() => {
      /* navegação pode abortar por hard-nav do interceptor — é esperado */
    });
    await page.waitForFunction(
      () => window.location.pathname === "/alterar-senha-obrigatoria",
      undefined,
      { timeout: 20_000 },
    );

    // Mensagem da tela — a página faz outra me() no mount para reconfirmar
    // a flag antes de renderizar o form.
    await expect(
      page.getByRole("heading", { name: /Troca de senha obrigatória/i }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText(/altere sua senha temporária antes de continuar/i),
    ).toBeVisible();

    // Tela standalone — sem Sidebar/Header do layout principal.
    await expect(page.getByRole("navigation")).toHaveCount(0);
    await expect(page.getByRole("banner")).toHaveCount(0);
  });

  test("rota de negócio sem trocar a senha continua bloqueada (sem loop)", async ({
    page,
    context,
  }) => {
    // Test #3: interceptor 403 (Commit 5). Independentemente de qual rota
    // protegida o usuário tenta, o redirect converge para a tela. URL
    // permanece estável depois — sem ping-pong.
    await loginViaApi(context, flaggedEmail, flaggedSenhaInicial);
    await bridgeApiToNginx(page, context);

    await page.goto("/processos");
    await expect(page).toHaveURL(/\/alterar-senha-obrigatoria$/, {
      timeout: 10_000,
    });

    // Aguarda e confirma que NÃO entra em loop.
    await page.waitForTimeout(1500);
    await expect(page).toHaveURL(/\/alterar-senha-obrigatoria$/);
  });

  test("troca de senha bem-sucedida envia para /home e libera rotas", async ({
    page,
    context,
  }) => {
    // Test #4: o caminho completo da saída do estado flagged. Após a troca,
    // /processos abre sem redirect. Backend (Commit 3) zerou a flag.
    await loginViaApi(context, flaggedEmail, flaggedSenhaInicial);
    await bridgeApiToNginx(page, context);

    await page.goto("/alterar-senha-obrigatoria");
    await expect(
      page.getByRole("heading", { name: /Troca de senha obrigatória/i }),
    ).toBeVisible();

    await page.getByLabel(/Senha atual/i).fill(flaggedSenhaInicial);
    await page.getByLabel(/^Nova senha/i).fill(flaggedSenhaNova);
    await page.getByLabel(/^Confirmar/i).fill(flaggedSenhaNova);
    await page.getByRole("button", { name: /alterar senha/i }).click();

    // onSuccess do TrocarSenhaCard → router.replace("/home").
    await expect(page).toHaveURL(/\/home$/, { timeout: 10_000 });

    // Re-login + navegação para /processos não devolve à tela obrigatória.
    await logoutViaApi(context);
    const body = await loginViaApi(
      context,
      flaggedEmail,
      flaggedSenhaNova,
    );
    expect(body.must_change_password).toBe(false);

    await page.goto("/processos");
    await page.waitForLoadState("networkidle");
    await expect(page).not.toHaveURL(/\/alterar-senha-obrigatoria/);
  });

  test("/cidadao/login não dispara o fluxo de troca obrigatória", async ({
    page,
    context,
  }) => {
    // Test #5: portal cidadão usa requestCidadao() — fluxo separado, sem
    // interceptor. Acesso à tela pública não pode disparar redirect.
    await bridgeApiToNginx(page, context);
    await page.goto("/cidadao/login");
    await page.waitForLoadState("networkidle");
    await expect(page).not.toHaveURL(/\/alterar-senha-obrigatoria/);
    await expect(page).toHaveURL(/\/cidadao\/login$/);
  });
});

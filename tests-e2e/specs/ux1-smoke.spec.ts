import {
  expect,
  test,
  type APIRequestContext,
  type BrowserContext,
  type Page,
} from "@playwright/test";

/**
 * UX-1 Fase G — smoke da jornada principal.
 *
 * Cobre as 7 telas refatoradas nas Fases A–F validando que renderizam, os
 * principais blocos visuais existem e não há regressão grosseira:
 *   - Portal público de serviços: /cidadao/servicos
 *   - Detalhe do serviço:        /cidadao/servicos/[slug]
 *   - Formulário de solicitação: /cidadao/servicos/[slug]/solicitar
 *   - Detalhe processo cidadão:  /cidadao/processos/[id]
 *   - Detalhe processo servidor: /processos/[id]
 *   - Dashboard:                 /dashboard
 *   - Catálogo admin:            /servicos
 *
 * Setup mínimo (beforeAll): garante 1 serviço público no catálogo e
 * cadastra 1 cidadão que abre 1 processo via esse serviço — os IDs/slug
 * são compartilhados entre os tests via `describe.serial`.
 *
 * Linguagem cidadã: nas telas cidadãs, garante ausência dos termos
 * vetados (SLA, garantia, garantido, prazo legal, deferido, indeferido).
 * Não aplica ao dashboard/admin (onde "SLA" pré-existente é técnico).
 */

const ADMIN_EMAIL = "admin@local.test";
const ADMIN_SENHA = "admin123";
const SMOKE_SLUG = "ux1-smoke-servico";

function cpfUnico(): string {
  const ts = Date.now() % 10_000_000_000;
  const rnd = Math.floor(Math.random() * 10);
  return String(ts * 10 + rnd).padStart(11, "0").slice(-11);
}

/**
 * O frontend tem `NEXT_PUBLIC_API_URL=http://localhost:8090/api/v2` (URL do
 * host externo). Dentro do container e2e, `localhost:8090` não é alcançável —
 * o nginx é `http://nginx`. Esta função intercepta os fetch do navegador e
 * reescreve para `http://nginx`, anexando os cookies já gravados no contexto
 * (que estão no domínio `nginx`).
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
      // route.fetch faz a request via Playwright e mantém origin transparente
      // para o browser; mais robusto que reconstruir tudo manualmente.
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

async function loginAdminViaApi(req: APIRequestContext): Promise<string> {
  const r = await req.post("/api/v2/auth/login", {
    data: { email: ADMIN_EMAIL, senha: ADMIN_SENHA },
  });
  expect(r.ok(), `admin login falhou: ${await r.text()}`).toBeTruthy();
  return (await r.json()).access_token;
}

async function loginAdminInContext(ctx: BrowserContext): Promise<void> {
  // Faz login admin no contexto do navegador: o backend grava o cookie
  // HttpOnly aprimora_token, que o middleware do Next aceita para liberar
  // /dashboard, /servicos e /processos/*.
  const r = await ctx.request.post("/api/v2/auth/login", {
    data: { email: ADMIN_EMAIL, senha: ADMIN_SENHA },
  });
  expect(r.ok(), `admin login (context) falhou: ${await r.text()}`).toBeTruthy();
}

async function injectCidadaoCookie(
  ctx: BrowserContext,
  cookieValue: string,
): Promise<void> {
  // Reusa o cookie já obtido no beforeAll para evitar estourar o rate-limit
  // do nginx em /cidadao/login (5/min por IP).
  await ctx.addCookies([
    {
      name: "aprimora_cidadao_token",
      value: cookieValue,
      domain: "nginx",
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

async function ensureSmokeServico(
  req: APIRequestContext,
  adminToken: string,
): Promise<{ slug: string; id: number }> {
  const auth = { Authorization: `Bearer ${adminToken}` };

  // Pré-requisitos do backend para `solicitar_habilitado=true` (D-C):
  // canal=portal + id_assunto_padrao + id_unidade_responsavel.
  const assuntosResp = await req.get("/api/v2/assuntos?page=1&page_size=1", {
    headers: auth,
  });
  expect(assuntosResp.ok(), `listar assuntos: ${await assuntosResp.text()}`).toBeTruthy();
  const idAssunto = (await assuntosResp.json()).items[0]?.id;
  expect(idAssunto, "seed sem assuntos").toBeTruthy();

  const unidadesResp = await req.get(
    "/api/v2/unidades-trabalho?page=1&page_size=1",
    { headers: auth },
  );
  expect(unidadesResp.ok(), `listar unidades: ${await unidadesResp.text()}`).toBeTruthy();
  const idUnidade = (await unidadesResp.json()).items[0]?.id;
  expect(idUnidade, "seed sem unidades").toBeTruthy();

  const basePayload = {
    nome: "UX-1 Smoke Servico",
    slug: SMOKE_SLUG,
    descricao_curta: "Serviço criado pelo smoke E2E do UX-1.",
    descricao_detalhada:
      "Serviço usado pelo smoke da Fase G. Não tem efeito operacional — pode ser desativado a qualquer momento.",
    publico_alvo: "qualquer cidadão",
    instrucoes_cidadao: "Descreva sua solicitação no formulário e envie.",
    documentos_exigidos: null,
    prazo_estimado_dias: 5,
    id_unidade_responsavel: idUnidade,
    id_tipo_processo_padrao: null,
    id_assunto_padrao: idAssunto,
    id_especie_documental_padrao: null,
    nivel_sigilo_padrao: "ostensivo",
    canal_entrada_permitido: "portal",
    destaque: true,
    ordem_exibicao: 0,
    categoria: "Smoke",
    texto_confirmacao: "Sua solicitação foi recebida.",
  };

  // Já existe? Busca via admin (que retorna id real).
  const listResp = await req.get("/api/v2/servicos?incluir_inativos=true", {
    headers: auth,
  });
  expect(listResp.ok(), `listar serviços: ${await listResp.text()}`).toBeTruthy();
  const existente = (await listResp.json()).find(
    (s: { slug: string; id: number }) => s.slug === SMOKE_SLUG,
  );

  if (existente) {
    // Garante que está com assunto+unidade (idempotente entre re-runs).
    const upd = await req.put(`/api/v2/servicos/${existente.id}`, {
      headers: auth,
      data: basePayload,
    });
    expect(upd.ok(), `atualizar serviço: ${await upd.text()}`).toBeTruthy();
    return { slug: SMOKE_SLUG, id: existente.id };
  }

  const r = await req.post("/api/v2/servicos", {
    headers: auth,
    data: basePayload,
  });
  expect(r.status(), `criar serviço falhou: ${await r.text()}`).toBe(201);
  const body = await r.json();
  return { slug: body.slug, id: body.id };
}

async function cadastrarCidadao(
  req: APIRequestContext,
): Promise<{ cpf: string; senha: string; token: string }> {
  const cpf = cpfUnico();
  const senha = "smokepw1234";
  const cad = await req.post("/api/v2/cidadao/cadastrar", {
    data: {
      cpf_cnpj: cpf,
      nome: `Smoke Cidadao ${cpf}`,
      email: `${cpf}@ux1smoke.test`,
      senha,
    },
  });
  expect(cad.status(), `cadastro falhou: ${await cad.text()}`).toBe(201);
  const login = await req.post("/api/v2/cidadao/login", {
    data: { cpf_cnpj: cpf, senha },
  });
  expect(login.ok(), `login cidadao falhou: ${await login.text()}`).toBeTruthy();
  return { cpf, senha, token: (await login.json()).access_token };
}

async function abrirProcessoViaServico(
  req: APIRequestContext,
  token: string,
  slug: string,
): Promise<number> {
  const r = await req.post(`/api/v2/cidadao/servicos/${slug}/abrir`, {
    headers: { Authorization: `Bearer ${token}` },
    data: { corpo: "Processo de smoke E2E UX-1 — abertura via portal." },
  });
  expect(r.status(), `abrir processo via serviço: ${await r.text()}`).toBe(201);
  return (await r.json()).id;
}

const TERMOS_VETADOS_CIDADAO: { name: string; re: RegExp }[] = [
  { name: "SLA", re: /\bSLA\b/ },
  { name: "garantia", re: /\bgarantia\b/i },
  { name: "garantido/garantida", re: /\bgarantid[oa]\b/i },
  { name: "prazo legal", re: /\bprazo legal\b/i },
  { name: "deferido/deferida", re: /\bdeferid[oa]\b/i },
  { name: "indeferido/indeferida", re: /\bindeferid[oa]\b/i },
];

async function expectSemTermosVetadosCidadao(page: Page) {
  const text = await page.locator("body").innerText();
  for (const { name, re } of TERMOS_VETADOS_CIDADAO) {
    expect(text, `termo vetado encontrado em tela cidadã: ${name}`).not.toMatch(re);
  }
}

// === Estado compartilhado entre os tests do describe.serial ===
let smokeSlug: string;
let cidadaoToken: string;
let cidadaoProcessoId: number;

test.describe.serial("UX-1 smoke (Fase G)", () => {
  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext();
    const req = ctx.request;

    const adminToken = await loginAdminViaApi(req);
    smokeSlug = (await ensureSmokeServico(req, adminToken)).slug;

    const cid = await cadastrarCidadao(req);
    cidadaoToken = cid.token;
    cidadaoProcessoId = await abrirProcessoViaServico(req, cid.token, smokeSlug);

    await ctx.close();
  });

  test("portal /cidadao/servicos — Carta de Serviços renderiza", async ({
    page,
    context,
  }) => {
    await injectCidadaoCookie(context, cidadaoToken);
    await bridgeApiToNginx(page, context);
    await page.goto("/cidadao/servicos");

    // Título principal.
    await expect(
      page.getByRole("heading", { name: /Carta de Serviços/i, level: 1 }),
    ).toBeVisible();

    // Ou lista com o serviço smoke OU empty state — qualquer um significa
    // que a tela carregou e renderizou seu estado.
    await expect(
      page
        .getByRole("heading", { name: /UX-1 Smoke Servico/i })
        .or(page.getByText(/Nenhum serviço disponível/i)),
    ).toBeVisible({ timeout: 15_000 });

    await expectSemTermosVetadosCidadao(page);
  });

  test("/cidadao/servicos/[slug] — detalhe mostra prazo + CTA", async ({
    page,
    context,
  }) => {
    await injectCidadaoCookie(context, cidadaoToken);
    await bridgeApiToNginx(page, context);
    await page.goto(`/cidadao/servicos/${smokeSlug}`);

    await expect(page.getByText(/UX-1 Smoke Servico/i)).toBeVisible({
      timeout: 10_000,
    });
    // Prazo estimado (microcopy de previsão, sem promessa).
    await expect(page.getByText(/Prazo estimado/i)).toBeVisible();
    // CTA "Solicitar serviço" (botão ou link asChild).
    await expect(page.getByRole("button", { name: /Solicitar serviço/i })).toBeVisible();

    await expectSemTermosVetadosCidadao(page);
  });

  test("/cidadao/servicos/[slug]/solicitar — formulário renderiza", async ({
    page,
    context,
  }) => {
    await injectCidadaoCookie(context, cidadaoToken);
    await bridgeApiToNginx(page, context);
    await page.goto(`/cidadao/servicos/${smokeSlug}/solicitar`);

    // Título do card "Solicitar: ..."
    await expect(page.getByText(/Solicitar:/i)).toBeVisible({ timeout: 10_000 });
    // Campo principal: textarea de descrição.
    await expect(page.getByLabel(/Descreva sua solicitação/i)).toBeVisible();
    // Orientação ao cidadão sobre o envio (placeholder + label).
    await expect(
      page.getByPlaceholder(/Conte com seus detalhes/i),
    ).toBeVisible();

    await expectSemTermosVetadosCidadao(page);
  });

  test("/cidadao/processos/[id] — Próximos passos visível", async ({
    page,
    context,
  }) => {
    await injectCidadaoCookie(context, cidadaoToken);
    await bridgeApiToNginx(page, context);
    await page.goto(`/cidadao/processos/${cidadaoProcessoId}`);

    // Card Próximos passos.
    await expect(page.getByText(/Próximos passos/i)).toBeVisible({
      timeout: 10_000,
    });

    await expectSemTermosVetadosCidadao(page);
  });

  test("/processos/[id] (servidor) — ActionsMenu Imprimir + Visão geral", async ({
    page,
    context,
  }) => {
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);
    await page.goto(`/processos/${cidadaoProcessoId}`);

    // Botão Imprimir do ActionsMenu (D-PRINT-MENU).
    await expect(
      page.getByRole("button", { name: /Imprimir/i }).first(),
    ).toBeVisible({ timeout: 10_000 });

    // Aba/heading Visão geral.
    await expect(
      page.getByRole("heading", { name: /Visão geral/i }).first(),
    ).toBeVisible();
  });

  test("/dashboard — FilterBar + 3 seções + exports", async ({
    page,
    context,
  }) => {
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);
    await page.goto("/dashboard");

    // FilterBar (Fase E): filtro de serviço + toggle legado são elementos
    // únicos do bloco. Se ambos estão visíveis, a FilterBar renderizou.
    await expect(
      page.getByTestId("dashboard-filtro-servico"),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByTestId("dashboard-toggle-legado"),
    ).toBeVisible();

    // 3 SectionCard de KPIs (Fase E).
    await expect(
      page.getByRole("heading", { name: /^Visão geral$/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Documentação e complementações/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Prazos por serviço/i }),
    ).toBeVisible();

    // Exports CSV/PDF (links dentro da FilterBar.Actions).
    await expect(page.getByRole("link", { name: /^PDF$/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /^CSV$/i })).toBeVisible();
  });

  test("/servicos (admin) — dialog com 3 seções (Identificação / Configuração / Orientações)", async ({
    page,
    context,
  }) => {
    await loginAdminInContext(context);
    await bridgeApiToNginx(page, context);
    await page.goto("/servicos");

    await expect(
      page.getByRole("heading", { name: /Catálogo de Serviços/i, level: 1 }),
    ).toBeVisible({ timeout: 10_000 });

    // Espera a lista renderizar (ou o EmptyState) — assim a página fica
    // estável e o botão "Novo serviço" não é re-renderizado durante o click.
    await expect(
      page
        .getByText("UX-1 Smoke Servico", { exact: false })
        .or(page.getByText(/Nenhum serviço cadastrado/i)),
    ).toBeVisible({ timeout: 15_000 });

    // Botão Novo serviço abre o dialog.
    const btnNovo = page.getByRole("button", { name: /Novo serviço/i }).first();
    await expect(btnNovo).toBeVisible();
    await btnNovo.click();

    // Dialog com 3 SectionCard.
    await expect(
      page.getByRole("heading", { name: /Identificação do serviço/i }),
    ).toBeVisible({ timeout: 5_000 });
    await expect(
      page.getByRole("heading", { name: /Configuração operacional/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /Orientações ao cidadão/i }),
    ).toBeVisible();
  });
});

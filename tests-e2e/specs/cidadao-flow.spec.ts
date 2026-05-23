import { expect, test } from "@playwright/test";

/**
 * Fluxo completo do cidadão (Fase 8 + Fase 9 paths):
 *   cadastrar → login → listar assuntos → abrir processo → listar meus →
 *   detalhe → isolamento (não vê processo alheio).
 *
 * Usa CPF dinâmico (timestamp-based) para evitar colisão com cadastros prévios
 * e permitir rodar a suite múltiplas vezes contra o mesmo banco dev.
 */

function cpfUnico(): string {
  // 11 dígitos baseados em timestamp ms. Não é CPF válido — só formato.
  return String(Date.now()).padStart(11, "0").slice(-11);
}

test.describe("Cidadão E2E", () => {
  test("ciclo completo", async ({ request }) => {
    const cpf = cpfUnico();
    const senha = "playw1234";

    // 1. Cadastrar
    const cad = await request.post("/api/v2/cidadao/cadastrar", {
      data: {
        cpf_cnpj: cpf,
        nome: "Playwright Bot",
        email: `${cpf}@e2e.test`,
        senha,
      },
    });
    expect(cad.status()).toBe(201);
    const cadBody = await cad.json();
    expect(cadBody.cpf_cnpj).toBe(cpf);

    // 2. Login
    const login = await request.post("/api/v2/cidadao/login", {
      data: { cpf_cnpj: cpf, senha },
    });
    expect(login.ok()).toBeTruthy();
    const { access_token: tok } = await login.json();
    const auth = { Authorization: `Bearer ${tok}` };

    // 3. Listar assuntos (catálogo público)
    const as = await request.get("/api/v2/cidadao/assuntos", { headers: auth });
    expect(as.ok()).toBeTruthy();
    const assuntos = await as.json();
    expect(assuntos.length).toBeGreaterThan(0);

    // 4. Abrir processo
    const abrir = await request.post("/api/v2/cidadao/processos", {
      headers: auth,
      data: {
        id_assunto: assuntos[0].id,
        corpo: "Solicitacao via Playwright E2E — teste de fluxo completo.",
        observacao: `cpf=${cpf}`,
      },
    });
    expect(abrir.status()).toBe(201);
    const novo = await abrir.json();
    expect(novo.numero_processo).toMatch(/^P\d{6}\/\d{4}$/);

    // 5. Listar meus
    const lista = await request.get("/api/v2/cidadao/processos", { headers: auth });
    expect(lista.ok()).toBeTruthy();
    const meus = await lista.json();
    expect(meus.find((p: { id: number }) => p.id === novo.id)).toBeTruthy();

    // 6. Detalhe próprio
    const det = await request.get(`/api/v2/cidadao/processos/${novo.id}`, {
      headers: auth,
    });
    expect(det.ok()).toBeTruthy();
    const dBody = await det.json();
    expect(dBody.movimentacoes.length).toBeGreaterThan(0);

    // 7. Isolamento: tenta acessar processo id=1 que NÃO é deste cidadão (cadastro novo)
    const alheio = await request.get("/api/v2/cidadao/processos/1", { headers: auth });
    expect(alheio.status()).toBe(404);
  });

  test("token de admin NÃO acessa /cidadao/me", async ({ request }) => {
    const adminLogin = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "admin123" },
    });
    const { access_token } = await adminLogin.json();
    const r = await request.get("/api/v2/cidadao/me", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(r.status()).toBe(401);
  });
});

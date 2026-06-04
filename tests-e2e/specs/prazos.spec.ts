import { expect, test } from "@playwright/test";

/**
 * PR 5b — Prazos por serviço (smoke).
 *
 * Cobre via HTTP:
 *  1) Detalhe cidadão expõe `prazo` reduzido SEM dias_*, snapshot ou
 *     concluido_em (defesa em profundidade da regra D-CIDADAO).
 *  2) Detalhe cidadão NÃO contém linguagem vetada ("garantia", "SLA",
 *     "prazo legal", "vencimento contratual").
 *  3) Endpoint `/dashboard/kpis` expõe o bloco `prazos` com a forma
 *     esperada (smoke — sem semântica de status, validada nos pytest).
 *
 * Setup mínimo: cadastra cidadão, abre um processo (pode ser sem
 * serviço — o bloco `prazo` ainda existe em modo `sem_previsao`).
 */

function cpfUnico(): string {
  const ts = Date.now() % 10_000_000_000;
  const rnd = Math.floor(Math.random() * 10);
  return String(ts * 10 + rnd).padStart(11, "0").slice(-11);
}

async function cadastrarELogar(
  request: any,
): Promise<{ cpf: string; token: string }> {
  const cpf = cpfUnico();
  const senha = "playw1234";
  const cad = await request.post("/api/v2/cidadao/cadastrar", {
    data: {
      cpf_cnpj: cpf,
      nome: `Cidadao PR5b ${cpf}`,
      email: `${cpf}@pr5b.test`,
      senha,
    },
  });
  expect(cad.status(), `cadastro falhou: ${await cad.text()}`).toBe(201);
  const login = await request.post("/api/v2/cidadao/login", {
    data: { cpf_cnpj: cpf, senha },
  });
  expect(login.ok(), `login falhou: ${await login.text()}`).toBeTruthy();
  const { access_token } = await login.json();
  return { cpf, token: access_token };
}

test.describe("PR 5b — Prazos (cidadão)", () => {
  let sharedAuth: Record<string, string>;
  let processoId: number;

  test.beforeAll(async ({ request }) => {
    const { token } = await cadastrarELogar(request);
    sharedAuth = { Authorization: `Bearer ${token}` };

    const assuntos = await (
      await request.get("/api/v2/cidadao/assuntos", { headers: sharedAuth })
    ).json();
    expect(Array.isArray(assuntos) && assuntos.length > 0).toBeTruthy();

    const r = await request.post("/api/v2/cidadao/processos", {
      headers: sharedAuth,
      data: {
        id_assunto: assuntos[0].id,
        corpo: "Pedido para teste de prazos PR 5b com mais de dez chars",
      },
    });
    expect(r.status(), `body=${await r.text()}`).toBe(201);
    const processo = await r.json();
    processoId = processo.id;
  });

  test("detalhe expõe `prazo` reduzido SEM contagem de dias", async ({
    request,
  }) => {
    const r = await request.get(`/api/v2/cidadao/processos/${processoId}`, {
      headers: sharedAuth,
    });
    expect(r.ok(), `detail falhou: ${await r.text()}`).toBeTruthy();
    const body = await r.json();

    expect(body.prazo, "bloco prazo ausente").toBeTruthy();
    expect(body.prazo).toHaveProperty("prazo_estimado_em");
    expect(body.prazo).toHaveProperty("status");

    // Campos vetados — defesa em profundidade da regra D-CIDADAO.
    expect(body.prazo).not.toHaveProperty("dias_restantes");
    expect(body.prazo).not.toHaveProperty("dias_atraso");
    expect(body.prazo).not.toHaveProperty("prazo_servico_dias_snapshot");
    expect(body.prazo).not.toHaveProperty("concluido_em");

    // Status no enum reduzido.
    expect([
      "sem_previsao",
      "dentro_da_previsao",
      "proximo_do_prazo",
      "fora_da_previsao",
      "concluido",
    ]).toContain(body.prazo.status);
  });

  test("detalhe NÃO contém linguagem vetada (garantia/SLA/legal)", async ({
    request,
  }) => {
    const r = await request.get(`/api/v2/cidadao/processos/${processoId}`, {
      headers: sharedAuth,
    });
    expect(r.ok()).toBeTruthy();
    const raw = (await r.text()).toLowerCase();
    // Regra D-CIDADAO: linguagem cuidadosa, sem promessa jurídica.
    expect(raw).not.toContain("garantia");
    expect(raw).not.toContain("garantido");
    expect(raw).not.toContain("prazo legal");
    expect(raw).not.toContain("\"sla\"");
    expect(raw).not.toContain("vencimento contratual");
  });
});

test.describe("PR 5b — Dashboard prazos (smoke)", () => {
  test("dashboard expõe bloco `prazos` quando usuário tem permissão", async ({
    request,
  }) => {
    // Login admin via cookie (mesma estratégia dos outros e2e).
    const login = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "admin123" },
    });
    if (!login.ok()) {
      // Em ambientes sem o seed admin, pula em silêncio — smoke não-crítica.
      test.skip(true, "admin seed ausente neste ambiente");
      return;
    }
    const cookies = login.headers()["set-cookie"];

    const r = await request.get("/api/v2/dashboard/kpis?periodo=30", {
      headers: cookies ? { Cookie: cookies } : undefined,
    });
    if (r.status() === 403) {
      // Usuário não tem permissão `dashboard` — esperado em alguns ambientes.
      test.skip(true, "usuário sem permissão dashboard");
      return;
    }
    expect(r.ok(), `kpis falhou: ${await r.text()}`).toBeTruthy();
    const body = await r.json();

    expect(body.prazos, "bloco prazos ausente").toBeTruthy();
    const p = body.prazos;
    expect(p).toHaveProperty("sem_prazo");
    expect(p).toHaveProperty("dentro_do_prazo");
    expect(p).toHaveProperty("vencendo");
    expect(p).toHaveProperty("atrasado");
    expect(p).toHaveProperty("concluido_no_prazo_periodo");
    expect(p).toHaveProperty("concluido_atrasado_periodo");
    expect(p).toHaveProperty("percentual_no_prazo");
    expect(p).toHaveProperty("tempo_medio_atraso_dias");

    // PR 5b — `por_servico` ganha campo `atrasados`.
    for (const item of body.por_servico ?? []) {
      expect(item, JSON.stringify(item)).toHaveProperty("atrasados");
    }

    // LGPD smoke — payload não vaza identificadores pessoais óbvios.
    const raw = JSON.stringify(body);
    expect(raw).not.toMatch(/\d{11}/); // sem CPF de 11 dígitos puros
  });
});

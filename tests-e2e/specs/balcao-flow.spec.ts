import { expect, test } from "@playwright/test";

/**
 * Fluxo de balcão (Fase P1 do Protocolo) — end-to-end via HTTP:
 *   login admin → POST /protocolo/balcao com espécie → confirma
 *   carimbos (canal_entrada=balcao, data_recepcao, espécie, NUP) →
 *   baixa etiqueta.pdf e comprovante.pdf, valida que são PDFs reais.
 *
 * Catálogos de Sobral (tenant=1): id_assunto=1, id_manifestante=1,
 * id_unidade=3, id_especie=2 (REQUERIMENTO). NUP federal está habilitado
 * com código 99001.
 *
 * Token reusado entre tests para não estourar o rate-limit do nginx
 * (5r/m burst 10 em /auth/login).
 */

test.describe("Balcão de Protocolo (P1)", () => {
  let token: string;
  let auth: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    const r = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "admin123" },
    });
    expect(r.ok(), `login falhou: ${await r.text()}`).toBeTruthy();
    const body = await r.json();
    token = body.access_token;
    auth = { Authorization: `Bearer ${token}` };
  });

  test("protocolar carimba canal/data_recepcao/espécie e gera NUP", async ({
    request,
  }) => {

    const r = await request.post("/api/v2/protocolo/balcao", {
      headers: auth,
      data: {
        id_manifestante: 1,
        id_assunto: 1,
        id_especie_documental: 2, // REQUERIMENTO
        id_unidade_proprietaria: 3,
        observacao: "E2E balcão smoke",
        publico: true,
      },
    });
    expect(r.status(), `body=${await r.text()}`).toBe(201);
    const body = await r.json();

    expect(body.id).toBeGreaterThan(0);
    expect(body.numero_processo).toMatch(/^P\d{6}\/\d{4}$/);
    expect(body.canal_entrada).toBe("balcao");
    expect(body.data_recepcao).toBeTruthy();
    expect(body.id_especie_documental).toBe(2);
    expect(body.especie_documental).toBe("Requerimento");
    // Tenant Sobral tem usar_nup_federal=true, NUP deve estar presente.
    expect(body.nup, "NUP esperado quando tenant tem flag").toMatch(
      /^\d{5}\.\d{6}\/\d{4}-\d{2}$/,
    );
  });

  test("etiqueta.pdf retorna PDF válido", async ({ request }) => {
    // Cria processo para gerar etiqueta
    const create = await request.post("/api/v2/protocolo/balcao", {
      headers: auth,
      data: {
        id_manifestante: 1,
        id_assunto: 1,
        id_especie_documental: 2,
        id_unidade_proprietaria: 3,
        publico: true,
      },
    });
    expect(create.ok()).toBeTruthy();
    const { id } = await create.json();

    const pdf = await request.get(`/api/v2/protocolo/${id}/etiqueta.pdf`, {
      headers: auth,
    });
    expect(pdf.ok()).toBeTruthy();
    expect(pdf.headers()["content-type"]).toContain("application/pdf");
    const buf = await pdf.body();
    expect(buf.byteLength).toBeGreaterThan(500);
    // Magic bytes do PDF
    expect(buf.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  });

  test("comprovante.pdf (2 vias) retorna PDF válido", async ({ request }) => {
    const create = await request.post("/api/v2/protocolo/balcao", {
      headers: auth,
      data: {
        id_manifestante: 1,
        id_assunto: 1,
        id_especie_documental: 2,
        id_unidade_proprietaria: 3,
        publico: true,
      },
    });
    const { id } = await create.json();

    const pdf = await request.get(`/api/v2/protocolo/${id}/comprovante.pdf`, {
      headers: auth,
    });
    expect(pdf.ok()).toBeTruthy();
    expect(pdf.headers()["content-type"]).toContain("application/pdf");
    const buf = await pdf.body();
    // Comprovante 2 vias é maior que etiqueta (~3.5KB vs ~2.5KB).
    expect(buf.byteLength).toBeGreaterThan(1500);
    expect(buf.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  });

  test("rejeita espécie inexistente", async ({ request }) => {
    const r = await request.post("/api/v2/protocolo/balcao", {
      headers: auth,
      data: {
        id_manifestante: 1,
        id_assunto: 1,
        id_especie_documental: 999_999, // inválida
        id_unidade_proprietaria: 3,
      },
    });
    // Validação no service → 400 ou 422 dependendo de onde catch
    expect(r.status()).toBeGreaterThanOrEqual(400);
    expect(r.status()).toBeLessThan(500);
  });
});

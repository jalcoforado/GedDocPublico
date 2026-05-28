import { APIRequestContext, expect, test } from "@playwright/test";

/**
 * Assinatura v2 (PR2b) — camada HTTP via nginx (cobre router + auth + schemas
 * que o pytest de serviço não exercita). Tenant Sobral (seed):
 * id_manifestante=1, id_assunto=1, id_unidade=3, id_especie=2.
 *
 * Cobre: assinar (hash + status), validar (íntegro), evidências, comprovante
 * PDF, recusar (status), throttle 429 após 5 tentativas malsucedidas.
 *
 * NÃO coberto aqui (justificativa no relatório do PR2b):
 *  - 409 MD5-only: não há como criar usuário só-MD5 via API; coberto no pytest
 *    (test_md5_only_bloqueado).
 *  - Renderização de UI (status/nível na tela, texto das mensagens): o harness
 *    e2e é API-level (sem browser/DOM); coberto por verificação manual +
 *    proposta de teste de componente (vitest+RTL) no PR2c.
 */

async function setup(
  request: APIRequestContext,
  auth: Record<string, string>,
  usuarioId: number,
): Promise<{ processoId: number; anexoId: number; aaId: number; solicId: number }> {
  const create = await request.post("/api/v2/protocolo/balcao", {
    headers: auth,
    data: {
      id_manifestante: 1,
      id_assunto: 1,
      id_especie_documental: 2,
      id_unidade_proprietaria: 3,
      observacao: "E2E assinatura v2",
      publico: true,
    },
  });
  expect(create.status(), `balcao: ${await create.text()}`).toBe(201);
  const processoId = (await create.json()).id as number;

  const up = await request.post(`/api/v2/processos/${processoId}/anexos`, {
    headers: auth,
    multipart: {
      file: {
        name: `e2e-${Date.now()}.txt`,
        mimeType: "text/plain",
        buffer: Buffer.from("conteudo do documento e2e v2"),
      },
      descricao: "Documento E2E",
      publico: "true",
    },
  });
  expect(up.status(), `upload: ${await up.text()}`).toBe(201);
  const anexoId = (await up.json()).id as number;

  const sol = await request.post(
    `/api/v2/processos/${processoId}/solicitacoes-assinatura`,
    { headers: auth, data: { id_assinantes: [usuarioId], id_anexos: [anexoId] } },
  );
  expect(sol.status(), `solicitar: ${await sol.text()}`).toBe(201);
  const solicId = (await sol.json()).id as number;

  const lista = await request.get(
    `/api/v2/processos/${processoId}/solicitacoes-assinatura`,
    { headers: auth },
  );
  const arr = await lista.json();
  const aaId = arr.find((s: any) => s.id === solicId).assinantes[0].anexos[0].id as number;

  return { processoId, anexoId, aaId, solicId };
}

test.describe("Assinatura v2 (PR2b)", () => {
  let auth: Record<string, string>;
  let usuarioId: number;

  test.beforeAll(async ({ request }) => {
    const r = await request.post("/api/v2/auth/login", {
      data: { email: "admin@local.test", senha: "admin123" },
    });
    expect(r.ok(), `login falhou: ${await r.text()}`).toBeTruthy();
    const body = await r.json();
    auth = { Authorization: `Bearer ${body.access_token}` };
    usuarioId = body.usuario_id;
  });

  test("assinar grava hash/status; validar íntegro; evidências; comprovante", async ({
    request,
  }) => {
    const { aaId } = await setup(request, auth, usuarioId);

    const sign = await request.post(`/api/v2/assinaturas/${aaId}/assinar`, {
      headers: auth,
      data: { senha: "admin123" },
    });
    expect(sign.status(), `assinar: ${await sign.text()}`).toBe(200);

    const val = await request.get(`/api/v2/assinaturas/${aaId}/validar`, { headers: auth });
    expect(val.ok()).toBeTruthy();
    const v = await val.json();
    expect(v.integro).toBe(true);
    expect(v.legado).toBe(false);

    const ev = await request.get(`/api/v2/assinaturas/${aaId}/evidencias`, { headers: auth });
    expect(ev.ok()).toBeTruthy();
    const e = await ev.json();
    expect(e.documento_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(e.metodo_autenticacao).toBe("senha_bcrypt");
    expect(e.nivel).toBe("simples");

    const comp = await request.get(`/api/v2/assinaturas/${aaId}/comprovante.pdf`, {
      headers: auth,
    });
    expect(comp.ok()).toBeTruthy();
    expect(comp.headers()["content-type"]).toContain("application/pdf");
    const buf = await comp.body();
    expect(buf.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  });

  test("recusar marca a solicitação como recusada", async ({ request }) => {
    const { solicId } = await setup(request, auth, usuarioId);
    const r = await request.post(
      `/api/v2/solicitacoes-assinatura/${solicId}/recusar`,
      { headers: auth, data: { motivo: "documento incorreto" } },
    );
    expect(r.status(), `recusar: ${await r.text()}`).toBe(200);
    const body = await r.json();
    const assinante = body.assinantes[0];
    expect(assinante.status).toBe("recusada");
  });

  test("throttle: 5 senhas erradas e a 6ª retorna 429", async ({ request }) => {
    const { aaId } = await setup(request, auth, usuarioId);
    for (let i = 0; i < 5; i++) {
      const bad = await request.post(`/api/v2/assinaturas/${aaId}/assinar`, {
        headers: auth,
        data: { senha: "senha-errada" },
      });
      expect(bad.status(), `tentativa ${i + 1}`).toBe(400);
    }
    const blocked = await request.post(`/api/v2/assinaturas/${aaId}/assinar`, {
      headers: auth,
      data: { senha: "senha-errada" },
    });
    expect(blocked.status()).toBe(429);
  });
});

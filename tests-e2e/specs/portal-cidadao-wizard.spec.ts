import { expect, test } from "@playwright/test";

/**
 * Portal Cidadão (Fase P3) — fluxo do wizard novo:
 *   cadastrar → login → GET /especies (3 do subset) → abrir processo
 *   com espécie → POST anexo (multipart) → detail mostra NUP +
 *   espécie + anexo → rate-limit bloqueia a 6ª abertura/24h.
 */

function cpfUnico(): string {
  // 11 dígitos com entropy adicional (timestamp + random) — evita colisão
  // entre tests consecutivos que rodam no mesmo ms.
  const ts = Date.now() % 10_000_000_000; // 10 dígitos
  const rnd = Math.floor(Math.random() * 10); // 1 dígito
  return String(ts * 10 + rnd).padStart(11, "0").slice(-11);
}

/** PDF mínimo válido (341 bytes, 1 página vazia). */
const PDF_MINIMO = Buffer.from(
  "%PDF-1.4\n" +
    "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" +
    "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n" +
    "3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 200 200] >>\nendobj\n" +
    "xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000060 00000 n\n0000000110 00000 n\n" +
    "trailer << /Root 1 0 R /Size 4 >>\nstartxref\n180\n%%EOF\n",
);

async function cadastrarELogar(
  request: any,
): Promise<{ cpf: string; token: string }> {
  const cpf = cpfUnico();
  const senha = "playw1234";
  const cad = await request.post("/api/v2/cidadao/cadastrar", {
    data: {
      cpf_cnpj: cpf,
      nome: `Cidadao P3 ${cpf}`,
      email: `${cpf}@p3.test`,
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

test.describe("Portal Cidadão wizard (P3)", () => {
  // Cidadão reusado entre os 4 tests "leves" — reduz 4 logins pra 1 e
  // evita estourar o rate-limit do nginx em /cidadao/login.
  let sharedToken: string;
  let sharedAuth: Record<string, string>;

  test.beforeAll(async ({ request }) => {
    const r = await cadastrarELogar(request);
    sharedToken = r.token;
    sharedAuth = { Authorization: `Bearer ${sharedToken}` };
  });

  test("GET /especies retorna subset (Requerimento/Petição/Declaração)", async ({
    request,
  }) => {
    const r = await request.get("/api/v2/cidadao/especies", {
      headers: sharedAuth,
    });
    expect(r.ok()).toBeTruthy();
    const lista = await r.json();
    const codigos = lista.map((e: { codigo: string }) => e.codigo).sort();
    expect(codigos).toEqual(["DECLARACAO", "PETICAO", "REQUERIMENTO"]);
  });

  test("abrir processo carimba canal=portal + espécie + NUP", async ({
    request,
  }) => {
    const assuntos = await (
      await request.get("/api/v2/cidadao/assuntos", { headers: sharedAuth })
    ).json();
    const especies = await (
      await request.get("/api/v2/cidadao/especies", { headers: sharedAuth })
    ).json();
    const requerimento = especies.find(
      (e: { codigo: string }) => e.codigo === "REQUERIMENTO",
    );
    expect(requerimento).toBeTruthy();

    const r = await request.post("/api/v2/cidadao/processos", {
      headers: sharedAuth,
      data: {
        id_assunto: assuntos[0].id,
        corpo: "Solicitacao via wizard P3 com mais de dez caracteres",
        id_especie_documental: requerimento.id,
      },
    });
    expect(r.status(), `body=${await r.text()}`).toBe(201);
    const processo = await r.json();

    expect(processo.especie_nome).toBe("Requerimento");
    expect(processo.nup, "NUP esperado em tenant configurado").toMatch(
      /^\d{5}\.\d{6}\/\d{4}-\d{2}$/,
    );
    expect(processo.numero_processo).toMatch(/^P\d{6}\/\d{4}$/);
  });

  test("upload anexo aparece no detalhe", async ({ request }) => {
    const auth = sharedAuth;
    const assuntos = await (
      await request.get("/api/v2/cidadao/assuntos", { headers: auth })
    ).json();

    const created = await (
      await request.post("/api/v2/cidadao/processos", {
        headers: auth,
        data: {
          id_assunto: assuntos[0].id,
          corpo: "Processo para receber anexo via wizard E2E",
        },
      })
    ).json();

    const up = await request.post(
      `/api/v2/cidadao/processos/${created.id}/anexos`,
      {
        headers: auth,
        multipart: {
          file: {
            name: "smoke.pdf",
            mimeType: "application/pdf",
            buffer: PDF_MINIMO,
          },
          descricao: "Documento E2E",
        },
      },
    );
    expect(up.status(), `body=${await up.text()}`).toBe(201);
    const anexo = await up.json();
    expect(anexo.publico).toBe(true);
    expect(anexo.descricao).toBe("Documento E2E");

    // Detail mostra
    const detail = await (
      await request.get(`/api/v2/cidadao/processos/${created.id}`, {
        headers: auth,
      })
    ).json();
    expect(detail.anexos.length).toBe(1);
    expect(detail.anexos[0].id).toBe(anexo.id);
  });

  test("rate-limit bloqueia 6ª abertura em 24h", async ({ request }) => {
    // Cidadão fresh é obrigatório aqui — outros tests deste describe
    // criaram processos no shared, conta aberturas das últimas 24h.
    const { token } = await cadastrarELogar(request);
    const auth = { Authorization: `Bearer ${token}` };
    const assuntos = await (
      await request.get("/api/v2/cidadao/assuntos", { headers: auth })
    ).json();

    // Aberturas 1..5 OK
    for (let i = 1; i <= 5; i++) {
      const r = await request.post("/api/v2/cidadao/processos", {
        headers: auth,
        data: {
          id_assunto: assuntos[0].id,
          corpo: `Abertura sequencial ${i} via E2E rate-limit test`,
        },
      });
      expect(r.status(), `abertura #${i}`).toBe(201);
    }

    // 6ª bloqueada
    const sexta = await request.post("/api/v2/cidadao/processos", {
      headers: auth,
      data: {
        id_assunto: assuntos[0].id,
        corpo: "Esta deveria ser bloqueada pelo rate-limit de 5/24h",
      },
    });
    expect(sexta.status()).toBe(400);
    const body = await sexta.json();
    expect(body.detail).toContain("Limite");
  });

  test("rejeita espécie fora do subset do portal", async ({ request }) => {
    const auth = sharedAuth;
    const assuntos = await (
      await request.get("/api/v2/cidadao/assuntos", { headers: auth })
    ).json();

    // Ofício (id=1) está no seed mas NÃO é uma das 3 expostas ao portal.
    const r = await request.post("/api/v2/cidadao/processos", {
      headers: auth,
      data: {
        id_assunto: assuntos[0].id,
        corpo: "Tentativa de protocolar com espécie restrita ao balcão",
        id_especie_documental: 1, // OFICIO
      },
    });
    expect(r.status()).toBe(400);
    const body = await r.json();
    expect(body.detail).toMatch(/[Ee]sp[eé]cie/);
  });
});

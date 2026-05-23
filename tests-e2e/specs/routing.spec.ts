import { expect, test } from "@playwright/test";

/**
 * Strangler Fig — confirma que cada rota volta com o header X-Aprimora-Backend
 * apontando para o upstream correto. Sintoma de problema: header ausente ou
 * apontando pro backend errado (ex: /processos indo pra php-legacy).
 */

const PY_ROUTES = [
  "/",
  "/login",
  "/cidadao",
  "/cidadao/login",
  "/cidadao/processos",
  "/processos",
  "/processos/1",
  "/home",
  "/jobs",
  "/relatorios",
  "/relatorios/tramitacao",
  "/relatorios/assinaturas",
  "/para-assinar",
];

const PHP_ROUTES = [
  "/cidadao_externo/login",   // não confundir com /cidadao do Python
  "/algumarotaaleatoria",     // fallback genérico
  "/css/site.css",
];

const API_ROUTES = ["/api/v2/health"];

test.describe("Strangler Fig routing", () => {
  for (const path of PY_ROUTES) {
    test(`${path} → python-frontend`, async ({ request }) => {
      const res = await request.get(path, { maxRedirects: 0 });
      expect(
        res.headers()["x-aprimora-backend"],
        `${path} deveria ser servido pelo frontend Python`,
      ).toBe("python-frontend");
    });
  }

  for (const path of PHP_ROUTES) {
    test(`${path} → php-legacy`, async ({ request }) => {
      const res = await request.get(path, { maxRedirects: 0 });
      expect(
        res.headers()["x-aprimora-backend"],
        `${path} deveria cair no fallback PHP`,
      ).toBe("php-legacy");
    });
  }

  for (const path of API_ROUTES) {
    test(`${path} → python-backend`, async ({ request }) => {
      const res = await request.get(path);
      expect(res.headers()["x-aprimora-backend"]).toBe("python-backend");
      expect(res.status()).toBe(200);
    });
  }
});

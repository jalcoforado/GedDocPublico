/**
 * Guard de rotas do frontend (`middleware.ts`): o que abre sem login.
 *
 * Existe porque `/validar/<codigo>` — o link impresso no documento assinado —
 * passou meses redirecionando para o login sem que nenhum teste percebesse: a
 * página, a API pública e o E2E (que valida já autenticado) estavam todos
 * verdes. O defeito morava só aqui.
 *
 * É guard de UX, não de segurança: a barreira real é o backend.
 */
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { middleware } from "../middleware";

function pedir(caminho: string, cookie?: string) {
  const req = new NextRequest(`http://sobral.aprimora.local${caminho}`, {
    headers: cookie ? { cookie } : undefined,
  });
  return middleware(req);
}

/** `NextResponse.redirect` carrega `location`; `NextResponse.next` não. */
function destino(res: Response): string | null {
  const loc = res.headers.get("location");
  return loc ? new URL(loc).pathname + new URL(loc).search : null;
}

describe("middleware — rotas públicas", () => {
  it.each([
    "/login",
    "/cidadao/login",
    "/cidadao/servicos",
    "/validar",
    "/validar/ABC123",
    "/brand/itaitinga-logo.png",
  ])("%s abre sem login", (caminho) => {
    expect(destino(pedir(caminho))).toBeNull();
  });

  it.each(["/home", "/m/protocolo/processos", "/admin/tenants"])(
    "%s sem login vai para o login, guardando o destino",
    (caminho) => {
      expect(destino(pedir(caminho))).toBe(`/login?next=${encodeURIComponent(caminho)}`);
    },
  );

  it("/modulos sem login vai para o login sem `next` (já é o destino padrão)", () => {
    expect(destino(pedir("/modulos"))).toBe("/login");
  });

  it("rota protegida com cookie de sessão segue adiante", () => {
    expect(destino(pedir("/home", "aprimora_token=qualquer"))).toBeNull();
  });
});

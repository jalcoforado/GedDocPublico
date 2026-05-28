import { describe, expect, it } from "vitest";

import {
  statusAssinante,
  statusSolicitacao,
  validacaoMensagem,
} from "@/lib/assinatura";

describe("statusSolicitacao", () => {
  it("cancelada → danger", () => {
    expect(statusSolicitacao({ cancelada: true, realizada: false })).toEqual({
      label: "Cancelada",
      intent: "danger",
    });
  });
  it("realizada → success", () => {
    expect(statusSolicitacao({ cancelada: false, realizada: true })).toEqual({
      label: "Concluída",
      intent: "success",
    });
  });
  it("em andamento → warning", () => {
    expect(statusSolicitacao({ cancelada: false, realizada: false })).toEqual({
      label: "Em andamento",
      intent: "warning",
    });
  });
});

describe("statusAssinante", () => {
  it("recusada → danger", () => {
    expect(statusAssinante({ status: "recusada", realizada: false })).toEqual({
      label: "Recusou",
      intent: "danger",
    });
  });
  it("realizada → success", () => {
    expect(statusAssinante({ status: "realizada", realizada: true }).label).toBe(
      "Assinou tudo",
    );
  });
  it("pendente → warning", () => {
    expect(statusAssinante({ status: "pendente", realizada: false }).label).toBe(
      "Pendente",
    );
  });
});

describe("validacaoMensagem", () => {
  it("legado → ok null", () => {
    expect(validacaoMensagem({ legado: true, integro: null }).ok).toBeNull();
  });
  it("íntegro → ok true", () => {
    const m = validacaoMensagem({ legado: false, integro: true });
    expect(m.ok).toBe(true);
    expect(m.texto).toMatch(/íntegra/i);
  });
  it("divergente → ok false", () => {
    const m = validacaoMensagem({ legado: false, integro: false });
    expect(m.ok).toBe(false);
    expect(m.texto).toMatch(/alterado/i);
  });
});

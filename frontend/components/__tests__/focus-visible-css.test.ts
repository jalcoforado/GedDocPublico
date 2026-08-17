import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Contrato do foco global (fatia UX-01A): o bloco `:focus-visible` de
// globals.css deve indicar foco via outline tokenizado, sem box-shadow
// (que empilha com o ring-* dos componentes) e sem border-radius forçado
// (que deforma controles que não são arredondados).

const css = readFileSync(
  resolve(__dirname, "../../app/globals.css"),
  "utf-8",
);

function blocoFocusVisibleGlobal(): string {
  // Seletor global exato `:focus-visible` (não compostos como `.x:focus-visible`)
  const match = css.match(/(?:^|\n)\s*:focus-visible\s*\{([^}]*)\}/);
  return match ? match[1] : "";
}

describe("foco global (:focus-visible) em globals.css", () => {
  const bloco = blocoFocusVisibleGlobal();

  it("existe uma regra global de :focus-visible", () => {
    expect(bloco).not.toBe("");
  });

  it("torna o foco visível via outline com offset", () => {
    expect(bloco).toMatch(/outline\s*:\s*(?!none)/);
    expect(bloco).toMatch(/outline-offset\s*:/);
  });

  it("não força border-radius no foco global", () => {
    expect(bloco).not.toMatch(/border-radius\s*:/);
  });

  it("não usa box-shadow no foco global (empilharia com ring-* dos componentes)", () => {
    expect(bloco).not.toMatch(/box-shadow\s*:/);
  });
});

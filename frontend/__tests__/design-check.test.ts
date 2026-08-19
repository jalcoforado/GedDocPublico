import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

import { describe, expect, it } from "vitest";

import { ALLOWLIST, comparar, varrer } from "../scripts/design-check.mjs";
import baseline from "../design-check-baseline.json";

/**
 * A guarda que faltava: nada impedia o próximo `bg-gray-100` (§4.10 da spec
 * master). O débito herdado fica congelado na baseline e só pode CAIR.
 *
 * Rodar aqui — e não só como script — põe a guarda no CI que já existe
 * (`frontend-tests`), sem depender de alguém lembrar de chamá-la.
 */
describe("design:check (ratchet do Design System)", () => {
  it("o código atual não piorou em relação à baseline", () => {
    const { contagem } = varrer();
    const { piorou } = comparar(contagem, baseline.arquivos);
    expect(piorou).toEqual([]);
  });

  it("a baseline reflete o código — quem queima débito aperta o ratchet", () => {
    const { contagem } = varrer();
    const { melhorou } = comparar(contagem, baseline.arquivos);
    // Falha com a instrução na mensagem: regrave com `--update`.
    expect({ regrave_a_baseline_com_update: melhorou }).toEqual({
      regrave_a_baseline_com_update: [],
    });
  });

  it("reprova cor literal em arquivo NOVO (inversão da guarda)", () => {
    const raiz = mkdtempSync(join(tmpdir(), "dc-"));
    try {
      mkdirSync(join(raiz, "components"), { recursive: true });
      writeFileSync(
        join(raiz, "components", "Novo.tsx"),
        'export const N = () => <p className="text-gray-500">x</p>;\n',
        "utf-8",
      );
      const { contagem, ocorrencias } = varrer(raiz);
      expect(ocorrencias.map((o) => o.texto)).toContain("text-gray-500");
      // sem entrada na baseline, o permitido é zero
      expect(comparar(contagem, {}).piorou).toHaveLength(1);
    } finally {
      rmSync(raiz, { recursive: true, force: true });
    }
  });

  it("reprova hex cru e aceita token do DS", () => {
    const raiz = mkdtempSync(join(tmpdir(), "dc-"));
    try {
      mkdirSync(join(raiz, "lib"), { recursive: true });
      writeFileSync(join(raiz, "lib", "a.ts"), 'export const c = "#1f2937";\n', "utf-8");
      writeFileSync(
        join(raiz, "lib", "b.ts"),
        'export const c = "hsl(var(--primary))";\nexport const k = "text-muted-foreground";\n',
        "utf-8",
      );
      const { ocorrencias } = varrer(raiz);
      expect(ocorrencias.map((o) => `${o.arquivo}:${o.tipo}`)).toEqual(["lib/a.ts:hex-cru"]);
    } finally {
      rmSync(raiz, { recursive: true, force: true });
    }
  });

  it("cada arquivo da allowlist declara a razão de estar isento", () => {
    for (const [arquivo, razao] of Object.entries(ALLOWLIST)) {
      expect(razao.length, `${arquivo} sem razão registrada`).toBeGreaterThan(30);
    }
  });
});

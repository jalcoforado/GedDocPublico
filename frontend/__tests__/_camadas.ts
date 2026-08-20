import { readFileSync } from "fs";
import { join } from "path";

/**
 * Helper compartilhado das guardas de camada (não é suíte: sem `.test.`).
 *
 * Lê a escala `--z-*` direto do `globals.css` — a fonte única. Se alguém
 * reordenar os tokens lá, as guardas passam a medir a escala nova em vez de
 * uma cópia desatualizada.
 */
const GLOBALS = join(__dirname, "..", "app", "globals.css");

export function tokensZ(): Record<string, number> {
  const css = readFileSync(GLOBALS, "utf-8");
  const tokens: Record<string, number> = {};
  for (const m of css.matchAll(/--z-([a-z-]+):\s*(\d+)\s*;/g)) {
    tokens[m[1]] = Number(m[2]);
  }
  return tokens;
}

/** Resolve o utilitário de camada de um elemento: `z-modal` → 1400. */
export function resolveZ(classe: string): number {
  const tokens = tokensZ();
  for (const t of classe.split(/\s+/)) {
    if (!t.startsWith("z-")) continue;
    const nome = t.slice(2);
    if (nome in tokens) return tokens[nome];
    if (/^\d+$/.test(nome)) return Number(nome); // legado `z-30`
    const cru = nome.match(/^\[(\d+)\]$/); // legado `z-[100]`
    if (cru) return Number(cru[1]);
  }
  throw new Error(`elemento sem utilitário de camada: "${classe}"`);
}

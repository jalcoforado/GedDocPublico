/**
 * UX-01 fatia 1.1 — guarda de tokens mortos/duplicados no globals.css.
 *
 * "Morto" = token `--x` definido no globals.css que nenhum arquivo consome
 * via `var(--x)` (nem o próprio globals, nem tailwind.config, nem código).
 * "Duplicado" = mesmo token definido duas vezes DENTRO do mesmo bloco
 * (redefinição no dark/density é override legítimo, não duplicata).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const RAIZ = join(__dirname, "..");
const globals = readFileSync(join(RAIZ, "app", "globals.css"), "utf8");
const tailwindConfig = readFileSync(join(RAIZ, "tailwind.config.ts"), "utf8");

function arquivosFonte(dir: string, out: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) {
      if (nome === "node_modules" || nome === ".next") continue;
      arquivosFonte(caminho, out);
    } else if (/\.(tsx?|css|mjs)$/.test(nome)) {
      out.push(caminho);
    }
  }
  return out;
}

function tokensDefinidos(css: string): string[] {
  return [...css.matchAll(/^\s*(--[a-z0-9-]+)\s*:/gim)].map((m) => m[1]);
}

// Única isenção deliberada: degraus das rampas primitivas de cor. A rampa
// completa é a API primitiva do DS — degrau vizinho existe para as fases
// UX-02+ (soft states, chart-theme) escolherem SEM inventar cor literal,
// que a guarda design:check (fatia 1.5) proíbe. Todo o resto: definiu, consome.
const RAMPAS_PRIMITIVAS =
  /^--(green|amber|neutral|red|emerald|yellow|blue)-\d+$/;

describe("tokens do design system (UX-01 fatia 1.1)", () => {
  it("nenhum token definido no globals.css fica sem consumidor (token morto)", () => {
    const definidos = new Set(
      tokensDefinidos(globals).filter((t) => !RAMPAS_PRIMITIVAS.test(t)),
    );
    const usos = new Set<string>();
    const dirs = ["app", "components", "lib", "scripts"].map((d) => join(RAIZ, d));
    const fontes = dirs.flatMap((d) => arquivosFonte(d));
    for (const conteudo of [tailwindConfig, ...fontes.map((f) => readFileSync(f, "utf8"))]) {
      for (const m of conteudo.matchAll(/var\((--[a-z0-9-]+)[),\s]/g)) usos.add(m[1]);
    }
    const mortos = [...definidos].filter((t) => !usos.has(t));
    expect(mortos, `tokens sem nenhum var(${"--"}...) consumidor`).toEqual([]);
  });

  it("nenhum token é definido duas vezes dentro do mesmo bloco", () => {
    // separa por bloco de chaves de topo (:root, :root.dark, etc.)
    const blocos = globals.match(/[^{}]+\{[^{}]*\}/g) ?? [];
    const duplicados: string[] = [];
    for (const bloco of blocos) {
      const vistos = new Set<string>();
      for (const t of tokensDefinidos(bloco)) {
        if (vistos.has(t)) duplicados.push(t);
        vistos.add(t);
      }
    }
    expect(duplicados).toEqual([]);
  });

  it(".bg-surface-* vem só do tailwind.config (sem utility duplicada no globals)", () => {
    expect(tailwindConfig).toMatch(/surface:\s*\{/);
    expect(globals).not.toMatch(/\.bg-surface-\d/);
  });

  it(".workflow-editor mora em @layer components", () => {
    const layer = globals.match(/@layer components\s*\{[\s\S]*?\n\}/);
    expect(layer, "@layer components existe").not.toBeNull();
    expect(layer![0]).toContain(".workflow-editor");
    // nenhuma regra .workflow-editor fora do layer
    const fora = globals.replace(layer![0], "");
    expect(fora).not.toContain(".workflow-editor");
  });
});

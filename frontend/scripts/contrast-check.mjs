#!/usr/bin/env node
/**
 * contrast:check — validador de contraste dos pares de token (UX-01, fatia 1.4).
 *
 * Descobre os pares SOZINHO: para todo `--X-foreground` existente procura o
 * `--X` correspondente e mede a razão WCAG nos dois temas. Par novo entra
 * coberto sem ninguém precisar lembrar de adicioná-lo a uma lista — que é
 * exatamente o tipo de lista que envelhece em silêncio.
 *
 * Uso: node scripts/contrast-check.mjs [--all]
 */
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CSS = join(RAIZ, "app", "globals.css");

/** Mínimo WCAG: 4.5 para texto normal; 3.0 onde o par é usado só como
 *  superfície/borda de UI ou texto grande — cada exceção com a razão. */
export const MINIMO_PADRAO = 4.5;
export const EXCECOES = {
  "primary/background": { min: 3, razao: "cor de marca usada como superfície e borda, não como texto sobre o fundo" },
};

function blocos(css) {
  const pega = (seletor) => {
    const i = css.indexOf(seletor);
    if (i < 0) return {};
    const ini = css.indexOf("{", i);
    let nivel = 0, fim = ini;
    for (let k = ini; k < css.length; k++) {
      if (css[k] === "{") nivel++;
      else if (css[k] === "}" && --nivel === 0) { fim = k; break; }
    }
    const corpo = css.slice(ini, fim);
    const vars = {};
    for (const m of corpo.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/gi)) vars[m[1]] = m[2].trim();
    return vars;
  };
  const light = pega(":root");
  return { light, dark: { ...light, ...pega(".dark") } };
}

/** Resolve `var(--x)` até chegar num valor HSL literal. */
function resolver(valor, vars, prof = 0) {
  if (prof > 10 || !valor) return null;
  const m = valor.match(/^var\((--[a-z0-9-]+)\)$/i);
  if (m) return resolver(vars[m[1]], vars, prof + 1);
  return valor;
}

export function hslParaRgb(valor) {
  const m = String(valor).trim().match(/^([\d.]+)\s+([\d.]+)%\s+([\d.]+)%$/);
  if (!m) return null;
  const h = Number(m[1]) / 360, s = Number(m[2]) / 100, l = Number(m[3]) / 100;
  if (s === 0) return [l, l, l].map((v) => v * 255);
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const canal = (t) => {
    if (t < 0) t += 1;
    if (t > 1) t -= 1;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [canal(h + 1 / 3), canal(h), canal(h - 1 / 3)].map((v) => v * 255);
}

export function luminancia([r, g, b]) {
  const c = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

export function contraste(a, b) {
  const [l1, l2] = [luminancia(a), luminancia(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

/** @returns {Array<{tema:string,par:string,razao:number,min:number,ok:boolean}>} */
export function medir(caminho = CSS) {
  const { light, dark } = blocos(readFileSync(caminho, "utf-8"));
  const linhas = [];
  for (const [tema, vars] of [["light", light], ["dark", dark]]) {
    for (const nome of Object.keys(vars)) {
      if (!nome.endsWith("-foreground")) continue;
      const fundoNome = nome.replace(/-foreground$/, "");
      if (!(fundoNome in vars)) continue;
      const fg = hslParaRgb(resolver(vars[nome], vars));
      const bg = hslParaRgb(resolver(vars[fundoNome], vars));
      if (!fg || !bg) continue;
      const par = `${fundoNome.replace(/^--/, "")}/${nome.replace(/^--/, "")}`;
      const chave = `${fundoNome.replace(/^--/, "")}/background`;
      const min = EXCECOES[chave]?.min ?? MINIMO_PADRAO;
      const razao = contraste(fg, bg);
      linhas.push({ tema, par, razao: Math.round(razao * 100) / 100, min, ok: razao >= min });
    }
  }
  return linhas;
}

function main() {
  const linhas = medir();
  const ruins = linhas.filter((l) => !l.ok);
  if (process.argv.includes("--all")) {
    for (const l of linhas.sort((a, b) => a.razao - b.razao)) {
      console.log(`${l.ok ? "✓" : "✗"} [${l.tema}] ${l.par}: ${l.razao}:1 (min ${l.min})`);
    }
  }
  if (ruins.length) {
    console.error("\nPares abaixo do mínimo WCAG:");
    for (const l of ruins) console.error(`  ✗ [${l.tema}] ${l.par}: ${l.razao}:1 — exige ${l.min}:1`);
    process.exit(1);
  }
  console.log(`✓ contrast:check — ${linhas.length} pares dentro do mínimo`);
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  main();
}

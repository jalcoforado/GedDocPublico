#!/usr/bin/env node
/**
 * design:check — guarda ratchet do Design System (UX-01, fatia 1.5).
 *
 * Reprova cor LITERAL nova no código: classe da paleta padrão do Tailwind
 * (`text-gray-500`, `bg-blue-600`…) e hex cru (`#1f2937`). O que já existe
 * entra congelado em `design-check-baseline.json`: o número por arquivo pode
 * cair, nunca subir, e arquivo fora da baseline começa em zero.
 *
 * Por que ratchet e não proibição total: são 125 ocorrências herdadas. Bloquear
 * tudo de uma vez pararia o trabalho; deixar sem guarda faz o débito voltar a
 * crescer — foi assim que ele chegou aqui, sem ninguém decidir.
 *
 * Uso:
 *   node scripts/design-check.mjs           verifica (exit 1 se piorou)
 *   node scripts/design-check.mjs --update  regrava a baseline
 */
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BASELINE = join(RAIZ, "design-check-baseline.json");

const DIRS = ["app", "components", "lib"];
const IGNORAR_DIR = new Set(["node_modules", ".next", "coverage", "__tests__"]);

// Arquivos autorizados a conter cor literal, com a razão registrada.
export const ALLOWLIST = {
  "lib/chart-theme.ts":
    "ponte única entre tokens CSS e bibliotecas de gráfico (recharts/xyflow), que não leem CSS custom properties",
};

const PALETA =
  "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|" +
  "teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose";
const PREFIXO =
  "text|bg|border|ring|fill|stroke|from|via|to|divide|outline|shadow|" +
  "decoration|accent|caret|placeholder";

const PADROES = [
  { nome: "classe-tailwind", re: new RegExp(`\\b(?:${PREFIXO})-(?:${PALETA})-\\d{2,3}\\b`, "g") },
  { nome: "hex-cru", re: /#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3}(?:[0-9a-fA-F]{2})?)?\b/g },
];

function fontes(dir, acc = []) {
  let entradas;
  try {
    entradas = readdirSync(dir);
  } catch {
    return acc;
  }
  for (const nome of entradas) {
    if (IGNORAR_DIR.has(nome)) continue;
    const full = join(dir, nome);
    if (statSync(full).isDirectory()) fontes(full, acc);
    else if (/\.tsx?$/.test(nome)) acc.push(full);
  }
  return acc;
}

/** @returns {{ contagem: Record<string, number>, ocorrencias: Array<{arquivo:string,linha:number,texto:string,tipo:string}> }} */
export function varrer(raiz = RAIZ) {
  const contagem = {};
  const ocorrencias = [];
  for (const d of DIRS) {
    for (const arquivo of fontes(join(raiz, d))) {
      const rel = relative(raiz, arquivo).replace(/\\/g, "/");
      if (rel in ALLOWLIST) continue;
      const linhas = readFileSync(arquivo, "utf-8").split("\n");
      linhas.forEach((linha, i) => {
        for (const { nome, re } of PADROES) {
          re.lastIndex = 0;
          for (const m of linha.matchAll(re)) {
            ocorrencias.push({ arquivo: rel, linha: i + 1, texto: m[0], tipo: nome });
            contagem[rel] = (contagem[rel] ?? 0) + 1;
          }
        }
      });
    }
  }
  return { contagem, ocorrencias };
}

export function lerBaseline(caminho = BASELINE) {
  try {
    return JSON.parse(readFileSync(caminho, "utf-8")).arquivos ?? {};
  } catch {
    return {};
  }
}

/** Compara a varredura com a baseline. Piorou = regressão a reprovar. */
export function comparar(contagem, baseline) {
  const piorou = [];
  const melhorou = [];
  for (const [arquivo, n] of Object.entries(contagem)) {
    const permitido = baseline[arquivo] ?? 0;
    if (n > permitido) piorou.push({ arquivo, permitido, atual: n });
  }
  for (const [arquivo, permitido] of Object.entries(baseline)) {
    const atual = contagem[arquivo] ?? 0;
    if (atual < permitido) melhorou.push({ arquivo, permitido, atual });
  }
  return { piorou, melhorou };
}

function main() {
  const { contagem, ocorrencias } = varrer();
  if (process.argv.includes("--update")) {
    const total = Object.values(contagem).reduce((a, b) => a + b, 0);
    writeFileSync(
      BASELINE,
      JSON.stringify(
        {
          _comentario:
            "Ratchet do design:check. Números só podem CAIR. Regrave com `npm run design:check -- --update` ao queimar débito — nunca para acomodar código novo.",
          total,
          arquivos: Object.fromEntries(Object.entries(contagem).sort()),
        },
        null,
        2,
      ) + "\n",
      "utf-8",
    );
    console.log(`baseline regravada: ${total} ocorrências em ${Object.keys(contagem).length} arquivos`);
    return;
  }
  const { piorou, melhorou } = comparar(contagem, lerBaseline());
  for (const p of piorou) {
    console.error(`\n✗ ${p.arquivo}: ${p.atual} cores literais (baseline permite ${p.permitido})`);
    for (const o of ocorrencias.filter((o) => o.arquivo === p.arquivo)) {
      console.error(`    ${p.arquivo}:${o.linha}  ${o.texto}  [${o.tipo}]`);
    }
  }
  if (piorou.length) {
    console.error(
      "\nUse token do Design System (text-muted-foreground, bg-surface, hsl(var(--…))).\n" +
        "A baseline existe para o débito ANTIGO — não a regrave para caber código novo.\n",
    );
    process.exit(1);
  }
  if (melhorou.length) {
    console.log(`✓ sem regressão. ${melhorou.length} arquivo(s) melhoraram — rode com --update para apertar o ratchet:`);
    for (const m of melhorou) console.log(`    ${m.arquivo}: ${m.permitido} → ${m.atual}`);
  } else {
    console.log("✓ design:check sem regressão");
  }
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
  main();
}

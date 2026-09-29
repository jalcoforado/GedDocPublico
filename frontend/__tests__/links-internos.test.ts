/**
 * Todo link interno escrito como literal tem de levar a uma página que existe.
 *
 * Nasceu de um defeito visto em homologação (2026-09-28): o "+ Cadastrar novo
 * manifestante" da tela de novo processo apontava para
 * `/cadastros/manifestantes/novo`, caminho de antes da F3 que não existe no
 * Next nem como redirect. No `:8090` ele cai no fallback legado do nginx e
 * responde 502. Nada quebrava: nem build, nem `tsc`, nem teste — a guarda de
 * `rotas-modulo.test.ts` só olha os menus.
 *
 * Alcance: literais em `href="…"`, `href={"…"}` e `router.push/replace("…")`
 * em `app/`, `components/` e `lib/`. Template strings ficam de fora (o trecho
 * dinâmico não é resolvível estaticamente) — é a mesma fronteira da guarda de
 * página órfã. Comentários são ignorados.
 *
 * Estrita de propósito: um redirect 308 do `next.config.js` NÃO conta como
 * destino válido. Os 308 existem para URL já gravada (link_url, favorito,
 * histórico); link novo nasce com `/m/<slug>/…` (CLAUDE.md, F3), senão é um
 * salto extra e a URL velha aparece na barra.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const RAIZ = join(__dirname, "..");
const APP = join(RAIZ, "app");

/** Rotas de página do App Router, com grupos `(x)` removidos. */
function paginas(dir = APP, prefixo = ""): string[] {
  const achadas: string[] = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.isFile() && /^page\.(tsx|ts|jsx|js)$/.test(e.name)) achadas.push(prefixo || "/");
    if (!e.isDirectory() || e.name === "__tests__" || e.name.startsWith("_")) continue;
    const seg = /^\(.*\)$/.test(e.name) ? "" : `/${e.name}`;
    achadas.push(...paginas(join(dir, e.name), prefixo + seg));
  }
  return achadas;
}

function padrao(rota: string): RegExp {
  const corpo = rota
    .split("/")
    .filter(Boolean)
    .map((s) => (s.startsWith("[[...") ? "?.*" : s.startsWith("[...") ? ".+" : s.startsWith("[") ? "[^/]+" : s))
    .join("/");
  return new RegExp(`^/${corpo}/?$`);
}

function fontes(): { caminho: string; texto: string }[] {
  const saida: { caminho: string; texto: string }[] = [];
  const anda = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const c = join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name !== "__tests__" && e.name !== "node_modules") anda(c);
      } else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) {
        const bruto = readFileSync(c, "utf-8");
        // Sem comentários: link comentado não é link. Só comentário JSX e
        // bloco que abre a linha — um `/*` solto casaria dentro de string
        // (`accept="image/*"`) e apagaria código de verdade, escondendo links.
        const texto = bruto
          .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "")
          .replace(/^\s*\/\*[\s\S]*?\*\//gm, "")
          .replace(/^\s*\/\/.*$/gm, "");
        saida.push({ caminho: c, texto });
      }
    }
  };
  for (const d of ["app", "components", "lib"]) anda(join(RAIZ, d));
  return saida;
}

const LINK = /(?:href=\{?\s*|\.(?:push|replace)\(\s*)["']((?:\/)[^"'?#]*)/g;

describe("links internos literais levam a uma página que existe", () => {
  it("a varredura achou páginas e links (controle contra regex quebrada)", () => {
    expect(paginas().length).toBeGreaterThan(30);
    const n = fontes().reduce((acc, f) => acc + [...f.texto.matchAll(LINK)].length, 0);
    expect(n).toBeGreaterThan(30);
  });

  it("nenhum href/push literal aponta para rota inexistente", () => {
    const rotas = paginas().map(padrao);
    const mortos: string[] = [];
    for (const { caminho, texto } of fontes()) {
      for (const m of texto.matchAll(LINK)) {
        const alvo = m[1];
        if (alvo.startsWith("/api/")) continue; // endpoint, não página
        if (rotas.some((r) => r.test(alvo))) continue;
        mortos.push(`${caminho.slice(RAIZ.length + 1)} -> ${alvo}`);
      }
    }
    expect(mortos, "links para páginas que não existem").toEqual([]);
  });
});

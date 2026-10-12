import { readFileSync, readdirSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * O `next build` recusa `page.tsx` que exporte qualquer coisa além do default
 * e dos campos de configuração de rota. `tsc --noEmit` e o vitest aceitam, e o
 * CI não roda o build: o defeito só aparece no deploy, que para na imagem do
 * frontend. Aconteceu com a trilha de auditoria de pagamentos, que exportava
 * uma constante de apoio. Constante compartilhada mora em `components/` ou
 * `lib/`, não na página.
 */
const EXPORTS_PERMITIDOS = new Set([
  "dynamic",
  "dynamicParams",
  "revalidate",
  "fetchCache",
  "runtime",
  "preferredRegion",
  "maxDuration",
  "metadata",
  "generateMetadata",
  "viewport",
  "generateViewport",
  "generateStaticParams",
]);

const APP = join(__dirname, "..", "app");

function paginas(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const caminho = join(dir, e.name);
    if (e.isDirectory()) return paginas(caminho);
    return e.name === "page.tsx" ? [caminho] : [];
  });
}

/** Nomes exportados no nível do módulo, fora o `export default`. */
export function exportsNomeados(fonte: string): string[] {
  const nomes: string[] = [];
  const declaracao =
    /^export\s+(?:declare\s+)?(?:async\s+)?(?:const|let|var|function\*?|class|enum)\s+([A-Za-z_$][\w$]*)/gm;
  for (const m of fonte.matchAll(declaracao)) nomes.push(m[1]);
  const lista = /^export\s*\{([^}]*)\}/gm;
  for (const m of fonte.matchAll(lista)) {
    for (const parte of m[1].split(",")) {
      const nome = parte.trim().split(/\s+as\s+/).pop()?.trim();
      if (nome && nome !== "default") nomes.push(nome);
    }
  }
  return nomes;
}

describe("guarda: export de página", () => {
  it("reconhece os formatos de export que o build recusa", () => {
    expect(
      exportsNomeados(
        [
          "export const ATOS = [];",
          "export async function carregar() {}",
          "export { a, b as c };",
          "export default function Pagina() {}",
          "export type Filtro = string;",
        ].join("\n"),
      ),
    ).toEqual(["ATOS", "carregar", "a", "c"]);
  });

  it("nenhuma page.tsx exporta além do default e da configuração de rota", () => {
    const arquivos = paginas(APP);
    expect(arquivos.length).toBeGreaterThan(50);
    const invalidos = arquivos.flatMap((arquivo) =>
      exportsNomeados(readFileSync(arquivo, "utf8"))
        .filter((nome) => !EXPORTS_PERMITIDOS.has(nome))
        .map((nome) => `${relative(APP, arquivo).split(sep).join("/")}: ${nome}`),
    );
    expect(invalidos).toEqual([]);
  });
});

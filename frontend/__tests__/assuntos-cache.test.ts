import { readFileSync, readdirSync, statSync } from "fs";
import { join } from "path";

import { describe, expect, it } from "vitest";

/**
 * Guarda do incidente `s.map is not a function` em /m/protocolo/servicos.
 *
 * A chave ["assuntos-all"] era montada à mão em cinco telas com `queryFn`
 * divergentes: quatro guardavam o `Paginated` inteiro e uma guardava
 * `.items`. O cache do React Query é indexado pela CHAVE, então quem
 * chegasse depois lia o formato de quem escreveu antes — e a tela que
 * esperava array quebrava ao ser aberta em segundo lugar.
 *
 * Tipo não pega isto: cada `useQuery` está correto isoladamente; o conflito
 * só existe entre arquivos, no cache em runtime.
 */
const RAIZ = join(__dirname, "..");
const IGNORAR = new Set(["node_modules", ".next", "coverage", ".git"]);
const FONTE_UNICA = join("lib", "assuntos.ts");

function fontes(dir: string, acc: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    if (IGNORAR.has(nome)) continue;
    const full = join(dir, nome);
    if (statSync(full).isDirectory()) fontes(full, acc);
    else if (/\.tsx?$/.test(nome)) acc.push(full);
  }
  return acc;
}

describe("cache de assuntos", () => {
  const arquivos = fontes(RAIZ);

  it("a chave assuntos-all só existe no módulo que a define", () => {
    const infratores = arquivos
      .filter((f) => readFileSync(f, "utf-8").includes("assuntos-all"))
      .map((f) => f.slice(RAIZ.length + 1).replace(/\\/g, "/"))
      .filter((f) => f !== FONTE_UNICA.replace(/\\/g, "/"))
      .filter((f) => !f.startsWith("__tests__/"));
    expect(infratores).toEqual([]);
  });

  it("nenhuma tela chama api.assuntos.list com page_size acima do teto do backend", () => {
    // routers/assuntos.py declara Query(20, ge=1, le=200): pedir 500 devolvia
    // 422 e deixava o combo vazio no Balcão e no Novo processo.
    const excessos: string[] = [];
    for (const f of arquivos) {
      for (const m of readFileSync(f, "utf-8").matchAll(
        /api\.assuntos\.list\(\s*\{[^}]*page_size:\s*(\d+)/g,
      )) {
        if (Number(m[1]) > 200) excessos.push(`${f}: page_size ${m[1]}`);
      }
    }
    expect(excessos).toEqual([]);
  });
});

/**
 * Nenhuma tela pede `page_size` acima do teto que o backend aceita.
 *
 * O backend declara `page_size: int = Query(..., le=N)`; pedir mais devolve
 * 422 e o combo/lista fica vazio. Isto já aconteceu DUAS vezes:
 * - agosto (7242ffe): assuntos com 500 contra teto 200 (Balcão e Novo processo);
 * - 2026-09-28: manifestantes com 500 contra 200 (as mesmas telas), usuários
 *   com 200 contra 100 (relatório de assinaturas), processos com 200 contra 100
 *   (apensar) e bairros com 500 contra 200 (endereços).
 * A guarda de agosto só olhava assuntos; o resto passou sem sintoma em teste.
 *
 * O teto de cada recurso NÃO é uma tabela solta aqui: o teste lê o `le=` na
 * função de listagem do próprio router do backend, então a tabela abaixo só
 * diz ONDE procurar. Recurso novo chamado com `page_size` literal e ausente da
 * tabela reprova — para ninguém escapar da guarda por omissão.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const RAIZ = join(__dirname, "..");
const ROUTERS = join(RAIZ, "..", "backend", "app", "routers");

/** recurso de `api.<recurso>.list(...)` → função de listagem no backend. */
const ONDE: Record<string, { arquivo: string; funcao: string }> = {
  manifestantes: { arquivo: "manifestantes.py", funcao: "list_manifestantes" },
  cidades: { arquivo: "localizacao.py", funcao: "list_cidades" },
  bairros: { arquivo: "localizacao.py", funcao: "list_bairros" },
  enderecos: { arquivo: "localizacao.py", funcao: "list_enderecos" },
  assuntos: { arquivo: "assuntos.py", funcao: "list_assuntos" },
  unidades: { arquivo: "unidades.py", funcao: "list_unidades" },
  usuarios: { arquivo: "usuarios.py", funcao: "list_usuarios" },
  processos: { arquivo: "processos.py", funcao: "list_endpoint" },
  contratos: { arquivo: "contratos.py", funcao: "list_contratos" },
};

function tetoNoBackend(recurso: string): number {
  const { arquivo, funcao } = ONDE[recurso];
  const src = readFileSync(join(ROUTERS, arquivo), "utf-8");
  const ini = src.search(new RegExp(`def ${funcao}\\(`));
  expect(ini, `${arquivo}: função ${funcao} não encontrada`).toBeGreaterThan(-1);
  const assinatura = src.slice(ini, src.indexOf("):", ini) + 2);
  const m = assinatura.match(/page_size:\s*int\s*=\s*Query\([^\n]*le=(\d+)/);
  expect(m, `${arquivo}::${funcao} sem page_size com le=`).not.toBeNull();
  return Number(m![1]);
}

const CHAMADA = /api\.(\w+)\.list\(\s*\{[^}]*?\bpage_size:\s*(\d+)/g;

function chamadas(): { onde: string; recurso: string; pedido: number }[] {
  const saida: { onde: string; recurso: string; pedido: number }[] = [];
  const anda = (dir: string) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const c = join(dir, e.name);
      if (e.isDirectory()) {
        if (e.name !== "__tests__" && e.name !== "node_modules") anda(c);
      } else if (/\.tsx?$/.test(e.name) && !/\.test\.tsx?$/.test(e.name)) {
        for (const m of readFileSync(c, "utf-8").matchAll(CHAMADA)) {
          saida.push({ onde: c.slice(RAIZ.length + 1), recurso: m[1], pedido: Number(m[2]) });
        }
      }
    }
  };
  for (const d of ["app", "components", "lib"]) anda(join(RAIZ, d));
  return saida;
}

describe("page_size pedido pelo frontend ≤ teto do backend", () => {
  it("a varredura achou chamadas (controle contra regex quebrada)", () => {
    expect(chamadas().length).toBeGreaterThan(10);
  });

  it("todo recurso chamado com page_size literal está mapeado", () => {
    const fora = [...new Set(chamadas().map((c) => c.recurso))].filter((r) => !(r in ONDE));
    expect(fora, "acrescente em ONDE (arquivo + função de listagem do backend)").toEqual([]);
  });

  it("nenhuma chamada pede acima do teto", () => {
    const acima = chamadas()
      .filter((c) => c.pedido > tetoNoBackend(c.recurso))
      .map((c) => `${c.onde}: ${c.recurso} page_size=${c.pedido} > ${tetoNoBackend(c.recurso)}`);
    expect(acima).toEqual([]);
  });
});

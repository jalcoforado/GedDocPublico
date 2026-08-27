/**
 * Guarda das abas: `role="tablist"` à mão não cresce mais.
 *
 * O primitivo `components/ui/tabs.tsx` existe desde a UX-02 (fatia 2.5) com
 * ARIA completo — `aria-controls`/`aria-labelledby` de mão dupla, `role=
 * "tabpanel"`, roving tabindex, setas/Home/End — e cinco testes cobrindo isso.
 *
 * Ele tinha **zero consumidores em produção**. Enquanto isso, seis telas
 * reimplementaram abas à mão, e as seis pararam no mesmo lugar: `role="tablist"`
 * + `role="tab"` e nada mais. Medição de 2026-08-27:
 *
 *   tela                                  aria-controls  tabpanel  setas
 *   admin/tenants/[id] (TenantEditTabs)         0            0        0
 *   m/administracao/jobs                        0            0        0
 *   m/pagamentos/autorizacao                    0            0        0
 *   m/pagamentos/tesouraria                     0            0        0
 *   m/protocolo/processos/[id]                  0            0        0
 *   components/RelatoriosNav                    0            0        0
 *
 * O que isso custa a quem usa leitor de tela: o widget anuncia "aba" e o leitor
 * não encontra painel associado. Não dá para saber o que a aba controla, nem
 * pular para o conteúdo dela, nem trocar de aba pelo teclado da forma que o
 * padrão manda. Nada disso quebra tela, nenhum teste fica vermelho, nenhum erro
 * aparece no console — foi por isso que atravessou sete meses.
 *
 * O backlog registrava isto como resíduo de UMA tela (item 1.0.9 da F2). Eram
 * seis, incluindo o detalhe do processo. Um item que subestima o próprio
 * tamanho é pior que nenhum item: quem o lê acha que é conserto de quinze
 * minutos e adia.
 *
 * **Esta guarda não conserta as cinco restantes.** Ela impede a sétima. A lista
 * `PENDENTES` abaixo só pode ENCOLHER: migrar uma tela para o primitivo remove
 * a linha correspondente; acrescentar linha aqui exige decisão escrita, do
 * mesmo jeito que `TRANSVERSAIS` em `rotas-modulo.test.ts`.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import { describe, expect, it } from "vitest";

const RAIZ = join(__dirname, "..");
const VARRER = ["app", "components"];
const IGNORAR = new Set(["node_modules", ".next", "__tests__"]);

/** O primitivo é o único lugar onde `role="tablist"` é escrito de propósito. */
const PRIMITIVO = join("components", "ui", "tabs.tsx");

/**
 * Telas que ainda reimplementam abas à mão, medidas em 2026-08-27.
 *
 * Cada linha é uma tela onde quem usa leitor de tela não consegue navegar as
 * abas. Migrar para `components/ui/tabs` remove a linha. **Só encolhe.**
 */
const PENDENTES = new Set(
  [
    "app/(app)/m/administracao/jobs/page.tsx",
    "app/(app)/m/pagamentos/autorizacao/page.tsx",
    "app/(app)/m/pagamentos/tesouraria/page.tsx",
    "app/(app)/m/protocolo/processos/[id]/page.tsx",
    "components/RelatoriosNav.tsx",
  ].map((p) => p.split("/").join("/")),
);

function arquivos(dir: string): string[] {
  const achados: string[] = [];
  for (const nome of readdirSync(dir)) {
    if (IGNORAR.has(nome)) continue;
    const caminho = join(dir, nome);
    if (statSync(caminho).isDirectory()) achados.push(...arquivos(caminho));
    else if (/\.tsx?$/.test(nome)) achados.push(caminho);
  }
  return achados;
}

/**
 * Tira comentários antes de procurar. Sem isto, o primeiro vermelho desta
 * guarda foi o `TenantEditTabs` — que **menciona** `role="tablist"` no
 * docstring, justamente para explicar que deixou de usá-lo. Menção em prosa
 * não é implementação, e ficar verde de outro jeito exigiria apagar a
 * explicação. (A guarda de links da documentação tropeçou no mesmo espelho
 * no mesmo dia: `backend/tests/test_guarda_links_docs.py`.)
 *
 * A remoção é textual, não um parser: string contendo `//` ou `/*` viraria
 * ruído. Nenhuma das telas varridas tem isso, e o controle de vacuidade no
 * fim do arquivo pega o dia em que a heurística começar a comer código.
 */
function semComentarios(fonte: string): string {
  return fonte
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "");
}

function comTablistNaMao(): string[] {
  const achados: string[] = [];
  for (const base of VARRER) {
    for (const caminho of arquivos(join(RAIZ, base))) {
      const rel = relative(RAIZ, caminho);
      if (rel === PRIMITIVO) continue;
      if (semComentarios(readFileSync(caminho, "utf8")).includes('role="tablist"')) {
        achados.push(rel.split("\\").join("/"));
      }
    }
  }
  return achados.sort();
}

describe("abas — ARIA", () => {
  it("nenhuma tela NOVA reimplementa `role=\"tablist\"` à mão", () => {
    const achados = comTablistNaMao();
    const novas = achados.filter((a) => !PENDENTES.has(a));

    expect(
      novas,
      'tela com `role="tablist"` escrito à mão. Use `components/ui/tabs` — ele já ' +
        "traz aria-controls/aria-labelledby, role=tabpanel, roving tabindex e " +
        "navegação por setas. Se o painel precisar preservar estado local ao " +
        "trocar de aba, passe `keepMounted` ao `<TabPanel>`.",
    ).toEqual([]);
  });

  it("a lista de pendentes só encolhe — nenhuma entrada dela já foi migrada", () => {
    const achados = new Set(comTablistNaMao());
    const jaMigradas = [...PENDENTES].filter((p) => !achados.has(p));

    expect(
      jaMigradas,
      "estas telas não têm mais `role=\"tablist\"` à mão — apague a linha " +
        "correspondente de `PENDENTES` neste arquivo. Isenção que sobrevive à " +
        "própria causa vira permissão silenciosa.",
    ).toEqual([]);
  });

  it("a varredura enxerga alguma coisa (controle de vacuidade)", () => {
    // Sem isto, um erro no caminho ou no glob deixaria as duas asserções acima
    // verdes para sempre, comparando lista vazia com lista vazia.
    expect(comTablistNaMao().length).toBeGreaterThanOrEqual(PENDENTES.size);
  });
});

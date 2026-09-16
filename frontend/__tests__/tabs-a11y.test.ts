/**
 * Guarda das abas: `role="tablist"` só existe no primitivo.
 *
 * O primitivo `components/ui/tabs.tsx` existe desde a UX-02 (fatia 2.5) com
 * ARIA completo — `aria-controls`/`aria-labelledby` de mão dupla, `role=
 * "tabpanel"`, roving tabindex, setas/Home/End.
 *
 * Ele passou meses com **zero consumidores em produção**. Enquanto isso, seis
 * telas reimplementaram abas à mão, e as seis pararam no mesmo lugar:
 * `role="tablist"` + `role="tab"` e nada mais. Medição de 2026-08-27:
 *
 *   tela                                  aria-controls  tabpanel  setas
 *   admin/tenants/[id] (TenantEditTabs)         0            0        0
 *   m/administracao/jobs                        0            0        0
 *   m/pagamentos/autorizacao                    0            0        0
 *   m/pagamentos/tesouraria                     0            0        0
 *   m/protocolo/processos/[id]                  0            0        0
 *   components/RelatoriosNav                    0            0        0
 *
 * O que custava a quem usa leitor de tela: o widget anunciava "aba" e o leitor
 * não encontrava painel associado. Não dava para saber o que a aba controla,
 * nem pular para o conteúdo, nem trocar de aba pelo teclado. Nada quebrava
 * tela, nenhum teste ficava vermelho, nenhum erro no console — foi por isso que
 * atravessou sete meses.
 *
 * As seis foram resolvidas, mas **não da mesma forma**, e a diferença é o que
 * vale registrar:
 *
 *   - Cinco eram abas de verdade (painéis na mesma página) e migraram para o
 *     primitivo.
 *   - `RelatoriosNav` **não era aba nenhuma**: três `<Link>` para três rotas
 *     distintas. Não havia painel porque não havia painel. Ali o conserto foi o
 *     OPOSTO — tirar `role="tab"`, que o APG não admite em link que navega, e
 *     ficar com `<nav>` + `aria-current="page"`. Migrar teria piorado.
 *
 * Esta guarda não distingue os dois casos: ela só vê `role="tablist"` escrito
 * fora do primitivo. Quem for adicionar abas precisa decidir qual dos dois tem
 * em mãos — a pergunta é "o conteúdo troca NESTA página?".
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
 * Telas que ainda reimplementam abas à mão. **Vazia desde 2026-08-27.**
 *
 * Mantida (em vez de apagada junto com a última entrada) porque o dia em que
 * alguém precisar de uma exceção legítima, o lugar de registrá-la — com a
 * razão ao lado — já existe. Lista vazia é a afirmação mais forte que este
 * arquivo pode fazer, e o teste abaixo garante que ela não volte a crescer em
 * silêncio.
 */
const PENDENTES = new Set<string>([]);

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
 * explicação. (A guarda de links da documentação tropeçou no mesmo espelho no
 * mesmo dia: `backend/tests/test_guarda_links_docs.py`.)
 *
 * A remoção é textual, não um parser: string contendo `//` viraria ruído.
 * Nenhuma das telas varridas tem isso, e os controles de vacuidade no fim do
 * arquivo pegam o dia em que a heurística começar a comer código.
 */
function semComentarios(fonte: string): string {
  return fonte.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
}

function varredura(): { arquivosLidos: number; comTablist: string[] } {
  const comTablist: string[] = [];
  let arquivosLidos = 0;
  for (const base of VARRER) {
    for (const caminho of arquivos(join(RAIZ, base))) {
      arquivosLidos += 1;
      const rel = relative(RAIZ, caminho).split("\\").join("/");
      if (rel === PRIMITIVO.split("\\").join("/")) continue;
      if (semComentarios(readFileSync(caminho, "utf8")).includes('role="tablist"')) {
        comTablist.push(rel);
      }
    }
  }
  return { arquivosLidos, comTablist: comTablist.sort() };
}

describe("abas — ARIA", () => {
  it('nenhuma tela reimplementa `role="tablist"` à mão', () => {
    const { comTablist } = varredura();
    const novas = comTablist.filter((a) => !PENDENTES.has(a));

    expect(
      novas,
      'tela com `role="tablist"` escrito à mão. Duas saídas, e a escolha depende ' +
        'de uma pergunta: "o conteúdo troca NESTA página?".\n' +
        "  SIM  -> use `components/ui/tabs` (aria-controls, role=tabpanel, roving " +
        "tabindex, setas). Se o painel precisar preservar estado local ao trocar " +
        "de aba, passe `keepMounted`. Se o visual for de botão arredondado, " +
        '`variant="pill"`.\n' +
        '  NÃO  -> não são abas, são links. Use `<nav>` + `aria-current="page"`, ' +
        "como `components/RelatoriosNav.tsx`.",
    ).toEqual([]);
  });

  it("a lista de pendentes só encolhe — nenhuma entrada dela já foi resolvida", () => {
    const { comTablist } = varredura();
    const achados = new Set(comTablist);
    const jaResolvidas = [...PENDENTES].filter((p) => !achados.has(p));

    expect(
      jaResolvidas,
      "estas telas não têm mais `role=\"tablist\"` à mão — apague a linha " +
        "correspondente de `PENDENTES` neste arquivo. Isenção que sobrevive à " +
        "própria causa vira permissão silenciosa.",
    ).toEqual([]);
  });

  // --- Controles de vacuidade -------------------------------------------
  //
  // Com `PENDENTES` vazia, as duas asserções acima comparam lista vazia com
  // lista vazia. Elas passariam para sempre se a varredura parasse de varrer —
  // caminho errado, glob quebrado, `semComentarios` engolindo código. Estes
  // dois testes existem só para que isso não aconteça em silêncio.

  it("a varredura realmente percorre a árvore", () => {
    const { arquivosLidos } = varredura();
    expect(arquivosLidos).toBeGreaterThan(150);
  });

  it("a varredura enxergaria o primitivo, se ele não fosse isento", () => {
    // Prova positiva: existe pelo menos UM arquivo onde a busca casa. Sem isto,
    // um `semComentarios` guloso demais (ou um regex quebrado) zeraria todos os
    // achados e a guarda ficaria verde por não enxergar nada.
    const fonte = readFileSync(join(RAIZ, PRIMITIVO), "utf8");
    expect(semComentarios(fonte)).toContain('role="tablist"');
  });
});

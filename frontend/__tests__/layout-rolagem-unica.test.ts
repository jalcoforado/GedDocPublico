/**
 * SI-50 — barra de rolagem dupla no Painel e no montar relatório.
 *
 * O <main> do layout autenticado é a área que rola. Sem `relative` nele,
 * qualquer elemento `absolute` sem ancestral posicionado (o `sr-only` dos
 * avisos para leitor de tela é o caso real) passa a ser medido contra a
 * página inteira, vaza para baixo do fim da tela e cria uma segunda barra.
 * Não dá para ver isso no jsdom (não há layout), então a guarda é sobre o
 * código-fonte: tirar o `relative` reprova aqui.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

describe("layout autenticado — uma barra de rolagem só", () => {
  it("o <main id=conteudo> é posicionado (relative)", () => {
    const fonte = readFileSync(join(__dirname, "..", "app", "(app)", "layout.tsx"), "utf-8");
    const main = fonte.match(/<main\s+id="conteudo"\s+className="([^"]+)"/);
    expect(main, "não achei o <main id=\"conteudo\"> no layout").not.toBeNull();
    const classes = main![1].split(/\s+/);
    expect(classes).toContain("relative");
    expect(classes).toContain("overflow-y-auto");
  });
});

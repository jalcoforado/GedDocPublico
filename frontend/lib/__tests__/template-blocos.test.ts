import { describe, expect, it } from "vitest";

import {
  blocosParaHtml,
  htmlDoBloco,
  htmlParaBlocos,
  moverPara,
  novoBloco,
  type Bloco,
} from "@/lib/template-blocos";

/** Compara sem o id (gerado a cada leitura). */
function semId(bs: Bloco[]) {
  return bs.map(({ id: _id, ...resto }) => resto);
}

describe("htmlDoBloco — só o que o editor de texto entende", () => {
  it("título centralizado, com texto escapado", () => {
    expect(htmlDoBloco({ id: "a", tipo: "titulo", texto: "Ofício <nº> & cia", alinhamento: "center" })).toBe(
      '<h2 style="text-align: center">Ofício &lt;nº&gt; &amp; cia</h2>',
    );
  });

  it("campo com e sem rótulo (dois-pontos do rótulo não duplica)", () => {
    expect(htmlDoBloco({ id: "a", tipo: "campo", rotulo: "Processo:", chave: "processo.numero" })).toBe(
      "<p><strong>Processo:</strong> {{processo.numero}}</p>",
    );
    expect(htmlDoBloco({ id: "a", tipo: "campo", rotulo: "", chave: "requerente.nome" })).toBe(
      "<p>{{requerente.nome}}</p>",
    );
  });

  it("data e local à direita, com a data do dia", () => {
    expect(htmlDoBloco({ id: "a", tipo: "data_local", local: "Itaitinga" })).toBe(
      '<p style="text-align: right">Itaitinga, {{data_hoje}}.</p>',
    );
    expect(htmlDoBloco({ id: "a", tipo: "data_local", local: "" })).toBe(
      '<p style="text-align: right">{{data_hoje}}.</p>',
    );
  });

  it("assinatura: linha, nome em negrito e cargo, centralizados; sem cargo, sem a linha dele", () => {
    const html = htmlDoBloco({ id: "a", tipo: "assinatura", nome: "{{usuario.nome}}", cargo: "Secretário" });
    expect(html).toContain('<p style="text-align: center"><strong>{{usuario.nome}}</strong></p>');
    expect(html).toContain('<p style="text-align: center">Secretário</p>');
    const semCargo = htmlDoBloco({ id: "a", tipo: "assinatura", nome: "Ana", cargo: "" });
    expect(semCargo.match(/<p/g)).toHaveLength(2);
  });

  it("bloco vazio não gera nada (título sem texto não vira <h2> vazio)", () => {
    expect(blocosParaHtml([novoBloco("titulo"), novoBloco("texto")])).toBe("");
  });
});

describe("blocos ↔ HTML", () => {
  const blocos: Bloco[] = [
    { id: "1", tipo: "titulo", texto: "Despacho & encaminhamento", alinhamento: "center" },
    { id: "2", tipo: "texto", html: "<p>Encaminho o processo <strong>{{processo.numero}}</strong>.</p><ul><li>item</li></ul>" },
    { id: "3", tipo: "campo", rotulo: "Requerente", chave: "requerente.nome" },
    { id: "4", tipo: "separador" },
    { id: "5", tipo: "data_local", local: "Itaitinga" },
    { id: "6", tipo: "assinatura", nome: "{{usuario.nome}}", cargo: "Chefe de Gabinete" },
    { id: "7", tipo: "titulo", texto: "Anexo", alinhamento: "left" },
  ];

  it("cada bloco sai num embrulho que o sanitizador do backend aceita (div com class)", () => {
    const html = blocosParaHtml(blocos);
    expect(html.match(/<div class="bloco bloco-[a-z_]+">/g)).toHaveLength(blocos.length);
    expect(html).not.toMatch(/data-/);
  });

  it("ida e volta devolve os mesmos blocos", () => {
    expect(semId(htmlParaBlocos(blocosParaHtml(blocos)))).toEqual(semId(blocos));
  });

  it("modelo antigo, sem marca de bloco, vira UM bloco de Texto com o HTML intacto", () => {
    const antigo = "<h2>Ofício</h2><p>Prezado {{destinatario.nome}},</p><p>texto</p>";
    expect(semId(htmlParaBlocos(antigo))).toEqual([{ tipo: "texto", html: antigo }]);
  });

  it("trechos soltos entre blocos viram Texto no lugar onde estavam", () => {
    const html = `<p>antes</p>${blocosParaHtml([blocos[3]])}<p>depois</p>`;
    expect(semId(htmlParaBlocos(html))).toEqual([
      { tipo: "texto", html: "<p>antes</p>" },
      { tipo: "separador" },
      { tipo: "texto", html: "<p>depois</p>" },
    ]);
  });

  it("embrulho que não dá para ler (alguém mexeu no HTML) vira Texto — nada se perde", () => {
    const html = '<div class="bloco bloco-assinatura"><p>só uma linha</p></div>';
    expect(semId(htmlParaBlocos(html))).toEqual([{ tipo: "texto", html: "<p>só uma linha</p>" }]);
  });

  it("vazio é lista vazia", () => {
    expect(htmlParaBlocos("  ")).toEqual([]);
  });
});

describe("moverPara", () => {
  const l = ["a", "b", "c", "d"];
  it("para cima, para baixo, para o fim", () => {
    expect(moverPara(l, 2, 0)).toEqual(["c", "a", "b", "d"]);
    expect(moverPara(l, 0, 2)).toEqual(["b", "a", "c", "d"]);
    expect(moverPara(l, 1, 4)).toEqual(["a", "c", "d", "b"]);
  });
  it("soltar no mesmo lugar não muda nada (mesma referência)", () => {
    expect(moverPara(l, 1, 1)).toBe(l);
    expect(moverPara(l, 1, 2)).toBe(l);
  });
});

import { describe, expect, it } from "vitest";

import { estadoDaColuna, proximaOrdenacao } from "@/lib/ordenacao";

describe("ordenação por coluna (SI-19)", () => {
  it("coluna nova começa crescente; a mesma coluna alterna", () => {
    const a = proximaOrdenacao(undefined, "assunto");
    expect(a).toEqual({ campo: "assunto", direcao: "asc" });
    const b = proximaOrdenacao(a, "assunto");
    expect(b).toEqual({ campo: "assunto", direcao: "desc" });
    expect(proximaOrdenacao(b, "assunto")).toEqual({ campo: "assunto", direcao: "asc" });
    expect(proximaOrdenacao(b, "numero")).toEqual({ campo: "numero", direcao: "asc" });
  });

  it("só a coluna ordenada mostra a seta", () => {
    const atual = { campo: "numero", direcao: "desc" } as const;
    expect(estadoDaColuna(atual, "numero")).toBe("desc");
    expect(estadoDaColuna(atual, "assunto")).toBeNull();
    expect(estadoDaColuna(undefined, "assunto")).toBeNull();
  });
});

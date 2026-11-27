import { describe, expect, it } from "vitest";

import {
  fracaoDoSelo,
  limitarPosicao,
  moverComTeclado,
  posicaoDoPonteiro,
  posicaoInicial,
  SELO_ALTURA_PT,
  SELO_LARGURA_PT,
} from "@/lib/selo-assinatura";

const A4 = { larguraPt: 595, alturaPt: 842 };
const PAISAGEM = { larguraPt: 842, alturaPt: 595 };

describe("geometria do selo (SI-68)", () => {
  it("o quadrado ocupa a fração certa da página", () => {
    const f = fracaoDoSelo(A4);
    expect(f.largura).toBeCloseTo(SELO_LARGURA_PT / 595);
    expect(f.altura).toBeCloseTo(SELO_ALTURA_PT / 842);
  });

  it("nunca deixa o quadrado sair da página", () => {
    const f = fracaoDoSelo(A4);
    expect(limitarPosicao(2, 2, A4)).toEqual({ x: 1 - f.largura, y: 1 - f.altura });
    expect(limitarPosicao(-1, -1, A4)).toEqual({ x: 0, y: 0 });
  });

  it("começa no canto inferior direito, dentro da página, nos dois formatos", () => {
    for (const p of [A4, PAISAGEM]) {
      const { x, y } = posicaoInicial(p);
      const f = fracaoDoSelo(p);
      expect(x).toBeGreaterThan(0.5);
      expect(y).toBeGreaterThan(0.5);
      expect(x + f.largura).toBeLessThanOrEqual(1);
      expect(y + f.altura).toBeLessThanOrEqual(1);
    }
  });

  it("arrastar segura o quadrado no ponto em que foi pego", () => {
    const area = { left: 100, top: 50, width: 595, height: 842 }; // escala 1
    // Pegou no canto superior esquerdo do quadrado e soltou em (400, 300):
    // o canto vai exatamente para lá.
    const p = posicaoDoPonteiro(400, 300, area, A4, { x: 0, y: 0 });
    expect(p.x).toBeCloseTo(300 / 595);
    expect(p.y).toBeCloseTo(250 / 842);
    // Pegou pelo meio: o canto fica meio quadrado antes.
    const meio = posicaoDoPonteiro(400, 300, area, A4);
    expect(meio.x).toBeCloseTo((300 - SELO_LARGURA_PT / 2) / 595);
    expect(meio.y).toBeCloseTo((250 - SELO_ALTURA_PT / 2) / 842);
  });

  it("setas movem 1% (5% com Shift) e ignoram outras teclas", () => {
    const direita = moverComTeclado("ArrowRight", false, { x: 0.2, y: 0.2 }, A4);
    expect(direita?.x).toBeCloseTo(0.21);
    expect(direita?.y).toBe(0.2);
    expect(moverComTeclado("ArrowUp", true, { x: 0.2, y: 0.2 }, A4)?.y).toBeCloseTo(0.15);
    expect(moverComTeclado("Enter", false, { x: 0.2, y: 0.2 }, A4)).toBeNull();
  });
});

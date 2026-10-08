/**
 * Tema por município. O que se trava aqui é a promessa do módulo: a cor que o
 * município escolhe NÃO pode tornar o sistema ilegível, e valor malformado não
 * pode virar CSS.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  STORAGE_TEMA,
  TEMA_CORES_INIT_SCRIPT,
  TOKENS_DE_TEMA,
  aplicarTema,
  contraste,
  derivarTema,
  guardarTema,
  hexParaHsl,
  hslParaHex,
  tokenParaHex,
  type Hsl,
} from "@/lib/tema-cores";

const BRANCO: Hsl = { h: 0, s: 0, l: 100 };

function tokenComoHsl(valor: string): Hsl {
  const [h, s, l] = valor.replace(/%/g, "").split(" ").map(Number);
  return { h, s, l };
}

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("style");
  document.documentElement.classList.remove("dark");
});

describe("conversão de cor", () => {
  it("hex → hsl → hex devolve a mesma cor", () => {
    for (const hex of ["#1b4f8f", "#e5451f", "#12305a", "#000000", "#ffffff", "#7f7f7f"]) {
      expect(hslParaHex(hexParaHsl(hex))).toBe(hex);
    }
  });

  it("lê token HSL do CSS e recusa o que não for um", () => {
    expect(tokenParaHex(" 0 0% 100% ")).toBe("#ffffff");
    expect(tokenParaHex("var(--green-700)")).toBeNull();
    expect(tokenParaHex("")).toBeNull();
  });
});

describe("derivarTema", () => {
  it("escurece a primária até texto branco ler sobre ela (AA)", () => {
    // Amarelo, ciano e rosa claros: os piores casos para botão com texto branco.
    for (const cor of ["#ffd400", "#00e5ff", "#ff9ecb", "#ffffff"]) {
      const marca = tokenComoHsl(derivarTema({ cor_primaria: cor }, "light")["--brand"]);
      expect(contraste(marca, BRANCO), cor).toBeGreaterThanOrEqual(4.4);
    }
  });

  it("preserva o matiz da cor escolhida", () => {
    const original = hexParaHsl("#1b4f8f");
    const marca = tokenComoHsl(derivarTema({ cor_primaria: "#1b4f8f" }, "light")["--brand"]);
    expect(Math.abs(marca.h - original.h)).toBeLessThanOrEqual(1);
  });

  it("a barra lateral é sempre escura — os itens do menu são claros", () => {
    for (const cor of ["#ffffff", "#ffd400", "#12305a"]) {
      for (const modo of ["light", "dark"] as const) {
        const fundo = tokenComoHsl(derivarTema({ cor_lateral: cor }, modo)["--sidebar"]);
        expect(fundo.l, `${cor} ${modo}`).toBeLessThanOrEqual(20);
      }
    }
  });

  it("sem cor lateral, a barra acompanha o matiz da primária", () => {
    const tema = derivarTema({ cor_primaria: "#1b4f8f" }, "light");
    const lateral = tokenComoHsl(tema["--sidebar"]);
    expect(Math.abs(lateral.h - hexParaHsl("#1b4f8f").h)).toBeLessThanOrEqual(1);
  });

  it("cor não definida não gera token — vale o padrão do globals.css", () => {
    expect(derivarTema({}, "light")).toEqual({});
    expect(Object.keys(derivarTema({ cor_destaque: "#e5451f" }, "light"))).toEqual([
      "--accent",
      "--accent-light",
      "--accent-dark",
      "--accent-foreground",
    ]);
  });

  it("ignora valor que não seja #RRGGBB", () => {
    for (const ruim of ["red", "#123", "1b4f8f", "#1b4f8f;color:red", null, undefined]) {
      expect(derivarTema({ cor_primaria: ruim, cor_destaque: ruim, cor_lateral: ruim }, "light")).toEqual({});
    }
  });

  it("todo token que deriva está na lista usada para limpar", () => {
    const todos = derivarTema(
      { cor_primaria: "#1b4f8f", cor_destaque: "#e5451f", cor_lateral: "#12305a" },
      "dark",
    );
    expect(Object.keys(todos).sort()).toEqual([...TOKENS_DE_TEMA].sort());
  });
});

describe("aplicarTema", () => {
  it("remove o token que a paleta nova deixou de definir", () => {
    const el = document.documentElement;
    aplicarTema(el, derivarTema({ cor_primaria: "#1b4f8f", cor_destaque: "#e5451f" }, "light"));
    expect(el.style.getPropertyValue("--accent")).not.toBe("");
    // O município apagou a cor de destaque: o âmbar padrão tem de voltar.
    aplicarTema(el, derivarTema({ cor_primaria: "#1b4f8f" }, "light"));
    expect(el.style.getPropertyValue("--accent")).toBe("");
    expect(el.style.getPropertyValue("--brand")).not.toBe("");
  });
});

describe("script de <head>", () => {
  const rodar = () => new Function(TEMA_CORES_INIT_SCRIPT)();

  it("aplica o tema guardado, no modo em que a página está", () => {
    guardarTema({ cor_primaria: "#1b4f8f" });
    const temas = JSON.parse(window.localStorage.getItem(STORAGE_TEMA)!);
    rodar();
    expect(document.documentElement.style.getPropertyValue("--brand")).toBe(temas.light["--brand"]);

    document.documentElement.classList.add("dark");
    rodar();
    expect(document.documentElement.style.getPropertyValue("--brand")).toBe(temas.dark["--brand"]);
  });

  it("não transforma em CSS o que não tiver formato de token", () => {
    window.localStorage.setItem(
      STORAGE_TEMA,
      JSON.stringify({
        light: {
          "--brand": "red; background: url(https://exemplo.test/x)",
          "background": "10 10% 10%",
          "--accent": "30 90% 50%",
        },
      }),
    );
    rodar();
    const estilo = document.documentElement.style;
    expect(estilo.getPropertyValue("--brand")).toBe("");
    expect(estilo.getPropertyValue("background")).toBe("");
    expect(estilo.getPropertyValue("--accent")).toBe("30 90% 50%");
  });

  it("sem nada guardado, ou com lixo, não quebra a página", () => {
    expect(rodar).not.toThrow();
    window.localStorage.setItem(STORAGE_TEMA, "{nao-e-json");
    expect(rodar).not.toThrow();
  });
});

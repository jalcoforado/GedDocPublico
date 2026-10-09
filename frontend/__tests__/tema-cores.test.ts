/**
 * Tema por município. O que se trava aqui é a promessa do módulo: a cor que o
 * município escolhe NÃO pode tornar o sistema ilegível, e valor malformado não
 * pode virar CSS.
 */
import { afterEach, describe, expect, it } from "vitest";

import {
  FONTES,
  STORAGE_TEMA,
  TEMA_CORES_INIT_SCRIPT,
  TOKENS_DE_TEMA,
  aplicarFonte,
  aplicarTema,
  cssDaFonte,
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

  // Até 2026-10-09 a barra era forçada a escura, e quem escolhia branco ou um
  // azul vivo recebia um quase preto: a tela parecia ignorar a escolha.
  it("a cor lateral ESCOLHIDA é a que vai para a tela, clara ou escura", () => {
    for (const cor of ["#ffffff", "#f3f4f6", "#ffd400", "#1d6fe0", "#12305a", "#000000"]) {
      const tema = derivarTema({ cor_lateral: cor }, "light");
      const [esperado, obtido] = [hexParaHsl(cor), tokenComoHsl(tema["--sidebar"])];
      expect(Math.abs(obtido.l - esperado.l), `${cor} luminosidade`).toBeLessThanOrEqual(1);
      expect(Math.abs(obtido.s - esperado.s), `${cor} saturação`).toBeLessThanOrEqual(1);
    }
  });

  it("o texto do menu se adapta ao fundo e lê em AA — inclusive o apagado", () => {
    const cores = ["#ffffff", "#f3f4f6", "#ffd400", "#f05a28", "#808080", "#1d6fe0", "#12305a", "#000000"];
    for (const cor of cores) {
      const tema = derivarTema({ cor_lateral: cor }, "light");
      const fundo = tokenComoHsl(tema["--sidebar"]);
      for (const nome of ["--sidebar-foreground", "--sidebar-muted-foreground"]) {
        expect(contraste(tokenComoHsl(tema[nome]), fundo), `${cor} ${nome}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("fundo claro recebe texto escuro, e fundo escuro, texto claro", () => {
    const clara = derivarTema({ cor_lateral: "#ffffff" }, "light");
    expect(tokenComoHsl(clara["--sidebar-foreground"]).l).toBeLessThan(30);
    const escura = derivarTema({ cor_lateral: "#12305a" }, "light");
    expect(tokenComoHsl(escura["--sidebar-foreground"]).l).toBeGreaterThan(80);
  });

  it("hover e item ativo se afastam do fundo no sentido certo", () => {
    const clara = derivarTema({ cor_lateral: "#f3f4f6" }, "light");
    expect(tokenComoHsl(clara["--sidebar-active"]).l).toBeLessThan(tokenComoHsl(clara["--sidebar"]).l);
    const escura = derivarTema({ cor_lateral: "#12305a" }, "light");
    expect(tokenComoHsl(escura["--sidebar-active"]).l).toBeGreaterThan(tokenComoHsl(escura["--sidebar"]).l);
  });

  it("no tema escuro a barra continua escura, mesmo com cor clara escolhida", () => {
    for (const cor of ["#ffffff", "#ffd400", "#12305a"]) {
      const fundo = tokenComoHsl(derivarTema({ cor_lateral: cor }, "dark")["--sidebar"]);
      expect(fundo.l, cor).toBeLessThanOrEqual(14);
    }
  });

  it("sem cor lateral própria, a barra derivada da primária continua escura", () => {
    for (const cor of ["#f05a28", "#ffd400", "#1b4f8f"]) {
      const fundo = tokenComoHsl(derivarTema({ cor_primaria: cor }, "light")["--sidebar"]);
      expect(fundo.l, cor).toBeLessThanOrEqual(20);
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
      {
        cor_primaria: "#1b4f8f",
        cor_destaque: "#e5451f",
        cor_lateral: "#12305a",
        cor_titulos: "#7a1f1f",
      },
      "dark",
    );
    expect(Object.keys(todos).sort()).toEqual([...TOKENS_DE_TEMA].sort());
  });
});

describe("títulos", () => {
  const CANVAS: Record<"light" | "dark", Hsl> = {
    light: { h: 120, s: 6, l: 97 },
    dark: { h: 158, s: 20, l: 8 },
  };

  it("a cor dos títulos lê sobre o canvas nos dois temas, seja qual for", () => {
    // Do amarelo (ilegível no claro) ao azul-marinho (ilegível no escuro).
    for (const cor of ["#ffd400", "#ffffff", "#f05a28", "#7a1f1f", "#12305a", "#000000"]) {
      for (const modo of ["light", "dark"] as const) {
        const tema = derivarTema({ cor_titulos: cor }, modo);
        expect(
          contraste(tokenComoHsl(tema["--titulo"]), CANVAS[modo]),
          `${cor} ${modo}`,
        ).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it("os dois papéis de título recebem a mesma cor", () => {
    const tema = derivarTema({ cor_titulos: "#7a1f1f" }, "light");
    expect(tema["--titulo"]).toBe(tema["--titulo-destaque"]);
  });

  it("cor que já lê é mantida — o ajuste não mexe no que não precisa", () => {
    const tema = derivarTema({ cor_titulos: "#7a1f1f" }, "light");
    expect(hslParaHex(tokenComoHsl(tema["--titulo"]))).toBe(
      hslParaHex(tokenComoHsl(`${Math.round(hexParaHsl("#7a1f1f").h)} ${Math.round(hexParaHsl("#7a1f1f").s)}% ${Math.round(hexParaHsl("#7a1f1f").l)}%`)),
    );
  });

  it("sem cor de títulos não há token — cada título fica no seu padrão", () => {
    const tema = derivarTema({ cor_primaria: "#1b4f8f" }, "light");
    expect(tema["--titulo"]).toBeUndefined();
    expect(tema["--titulo-destaque"]).toBeUndefined();
  });
});

describe("fonte dos títulos", () => {
  it("a lista é fechada e todo valor de CSS é uma var() hospedada no layout", () => {
    for (const f of FONTES) {
      if (f.css !== null) expect(f.css, f.chave).toMatch(/^var\(--font-[a-z-]+\)$/);
    }
    // A padrão não sobrescreve nada: é a opção sem CSS.
    expect(FONTES.filter((f) => f.css === null).map((f) => f.chave)).toEqual(["montserrat"]);
  });

  it("chave fora da lista não vira font-family", () => {
    for (const ruim of ["Comic Sans MS", "roboto-slab", "arial; }", "constructor", "", null, undefined]) {
      expect(cssDaFonte(ruim), String(ruim)).toBeNull();
    }
    expect(cssDaFonte("roboto_slab")).toBe("var(--font-roboto-slab)");
  });

  it("aplica a fonte escolhida e a remove ao voltar para a padrão", () => {
    const el = document.documentElement;
    aplicarFonte(el, "nunito");
    expect(el.style.getPropertyValue("--font-display")).toBe("var(--font-nunito)");
    aplicarFonte(el, "montserrat");
    expect(el.style.getPropertyValue("--font-display")).toBe("");
    aplicarFonte(el, "nunito");
    aplicarFonte(el, null);
    expect(el.style.getPropertyValue("--font-display")).toBe("");
  });

  it("o cache guarda só a CHAVE, e o script de <head> a traduz pela própria tabela", () => {
    guardarTema({ cor_primaria: "#1b4f8f", fonte_titulos: "roboto_slab" });
    const guardado = JSON.parse(window.localStorage.getItem(STORAGE_TEMA) ?? "{}");
    expect(guardado.fonte).toBe("roboto_slab");
    new Function(TEMA_CORES_INIT_SCRIPT)();
    expect(document.documentElement.style.getPropertyValue("--font-display")).toBe(
      "var(--font-roboto-slab)",
    );
  });

  it("o script não transforma em CSS uma fonte que não esteja na tabela", () => {
    for (const ruim of ["constructor", "__proto__", "var(--x); background:url(x)", 42, { a: 1 }]) {
      document.documentElement.removeAttribute("style");
      window.localStorage.setItem(
        STORAGE_TEMA,
        JSON.stringify({ light: {}, dark: {}, fonte: ruim }),
      );
      new Function(TEMA_CORES_INIT_SCRIPT)();
      expect(
        document.documentElement.style.getPropertyValue("--font-display"),
        JSON.stringify(ruim),
      ).toBe("");
    }
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

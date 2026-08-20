import { mkdtempSync, rmSync, writeFileSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

import { describe, expect, it } from "vitest";

import { EXCECOES, contraste, hslParaRgb, medir } from "../scripts/contrast-check.mjs";

/**
 * Guarda de contraste (UX-01, fatia 1.4).
 *
 * O validador descobre os pares sozinho — todo `--X-foreground` é medido
 * contra o `--X` correspondente, nos dois temas. Par novo nasce coberto, sem
 * depender de alguém lembrar de inscrevê-lo numa lista.
 *
 * A spec apontava `--accent-foreground` e `--info` no dark. A medição achou
 * cinco pares reprovados e o `info` não era um deles: accent e success
 * falhavam nos DOIS temas, e danger só no dark. Vale como lembrete de que
 * inventário escrito à mão envelhece — o validador é que sabe.
 */
describe("contraste dos pares de token (WCAG AA)", () => {
  it("todo par foreground/fundo alcança o mínimo nos dois temas", () => {
    const ruins = medir()
      .filter((l) => !l.ok)
      .map((l) => `[${l.tema}] ${l.par}: ${l.razao}:1 (min ${l.min})`);
    expect(ruins).toEqual([]);
  });

  it("mede os dois temas e um número razoável de pares", () => {
    const linhas = medir();
    expect(linhas.filter((l) => l.tema === "light").length).toBeGreaterThan(8);
    expect(linhas.filter((l) => l.tema === "dark").length).toBeGreaterThan(8);
  });

  it("reprova par abaixo do mínimo (inversão da guarda)", () => {
    const dir = mkdtempSync(join(tmpdir(), "ct-"));
    try {
      const css = join(dir, "globals.css");
      writeFileSync(
        css,
        `:root {\n  --tudo-ok: 0 0% 0%;\n  --tudo-ok-foreground: 0 0% 100%;\n` +
          `  --ilegivel: 60 100% 80%;\n  --ilegivel-foreground: 0 0% 100%;\n}\n`,
        "utf-8",
      );
      const linhas = medir(css);
      const ruins = linhas.filter((l) => !l.ok).map((l) => l.par);
      expect(ruins).toContain("ilegivel/ilegivel-foreground");
      expect(ruins).not.toContain("tudo-ok/tudo-ok-foreground");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it("a matemática bate com valores conhecidos do WCAG", () => {
    const branco = hslParaRgb("0 0% 100%");
    const preto = hslParaRgb("0 0% 0%");
    expect(contraste(branco, preto)).toBeCloseTo(21, 1);
    expect(contraste(branco, branco)).toBeCloseTo(1, 5);
  });

  it("cada exceção ao mínimo declara a razão", () => {
    for (const [par, { min, razao }] of Object.entries(EXCECOES)) {
      expect(min, `${par}: exceção não pode ficar abaixo de 3:1`).toBeGreaterThanOrEqual(3);
      expect(razao.length, `${par} sem razão registrada`).toBeGreaterThan(30);
    }
  });
});

import { readFileSync, readdirSync, statSync } from "fs";
import { join, relative } from "path";

import { describe, expect, it } from "vitest";

import { tokensZ } from "./_camadas";

/**
 * Guarda da escala de camadas (UX-01, fatia 1.3).
 *
 * Os tokens `--z-*` existiam desde a DS v3 e nenhum componente os usava: cada
 * overlay escolhia um número solto (z-30/40/50/[100]/[200]), então a ordem
 * entre Header, drawer, modal, command palette e barra de progresso era
 * acidente de quem escreveu por último — o combobox vencia o modal sem
 * ninguém ter decidido isso.
 *
 * Regra: camada GLOBAL (fixed/sticky) usa classe semântica. `z-N` cru continua
 * válido para empilhamento LOCAL dentro de um container (a lista abaixo), onde
 * um valor da escala global seria errado, não certo.
 */
const RAIZ = join(__dirname, "..");
const IGNORAR = new Set(["node_modules", ".next", "coverage", "__tests__"]);

/** Empilhamento local legítimo — cada entrada com a razão. */
const LOCAIS_PERMITIDOS: Record<string, string> = {
  "app/login/page.tsx": "conteúdo sobre a arte de fundo, dentro do próprio hero",
  "app/(app)/m/pagamentos/autorizacao/page.tsx": "barra de ações sticky dentro da página",
  "app/(app)/m/pagamentos/tesouraria/page.tsx": "barra de ações sticky dentro da página",
  "app/cidadao/servicos/[slug]/page.tsx": "barra de ação sticky dentro da página",
  "components/workflow/WorkflowEditor.tsx": "painel flutuante dentro do canvas do editor",
};

function fontes(dir: string, acc: string[] = []): string[] {
  for (const nome of readdirSync(dir)) {
    if (IGNORAR.has(nome)) continue;
    const full = join(dir, nome);
    if (statSync(full).isDirectory()) fontes(full, acc);
    else if (/\.tsx?$/.test(nome)) acc.push(full);
  }
  return acc;
}

function usosCrus() {
  const achados: { arquivo: string; linha: number; texto: string; global: boolean }[] = [];
  for (const d of ["app", "components"]) {
    for (const arquivo of fontes(join(RAIZ, d))) {
      const rel = relative(RAIZ, arquivo).replace(/\\/g, "/");
      readFileSync(arquivo, "utf-8")
        .split("\n")
        .forEach((linha, i) => {
          for (const m of linha.matchAll(/\bz-(?:\[(\d+)\]|(\d+))\b/g)) {
            achados.push({
              arquivo: rel,
              linha: i + 1,
              texto: m[0],
              global: /\b(fixed|sticky)\b/.test(linha),
            });
          }
        });
    }
  }
  return achados;
}

describe("escala de camadas (--z-*)", () => {
  it("a escala está definida e estritamente crescente na ordem semântica", () => {
    const t = tokensZ();
    const ordem = [
      "dropdown", "sticky", "fixed", "modal-backdrop",
      "modal", "popover", "tooltip", "toast",
    ];
    for (const nome of ordem) expect(t[nome], `token --z-${nome} ausente`).toBeTypeOf("number");
    const valores = ordem.map((n) => t[n]);
    expect(valores).toEqual([...valores].sort((a, b) => a - b));
    expect(new Set(valores).size, "dois papéis com o mesmo valor: a ordem volta a ser acidente")
      .toBe(valores.length);
  });

  it("nenhuma camada global usa z-index cru — só classe semântica", () => {
    const infratores = usosCrus()
      .filter((u) => u.global)
      .filter((u) => !(u.arquivo in LOCAIS_PERMITIDOS))
      .map((u) => `${u.arquivo}:${u.linha} ${u.texto}`);
    expect(infratores).toEqual([]);
  });

  it("todo empilhamento local isento declara a razão", () => {
    const arquivosComCru = new Set(usosCrus().map((u) => u.arquivo));
    for (const [arquivo, razao] of Object.entries(LOCAIS_PERMITIDOS)) {
      expect(razao.length, `${arquivo} sem razão`).toBeGreaterThan(20);
      // isenção que não corresponde a nenhum uso real vira lixo que esconde
      // regressão futura — cai fora junto com o código que a motivou
      expect(arquivosComCru.has(arquivo), `isenção órfã: ${arquivo}`).toBe(true);
    }
  });

  it("o shell empilha na ordem pretendida: header < backdrop < modal < palette < progresso", () => {
    const t = tokensZ();
    const classe = (f: string) => readFileSync(join(RAIZ, f), "utf-8");
    expect(classe("components/Header.tsx")).toContain("z-sticky");
    expect(classe("components/Sidebar.tsx")).toContain("z-modal-backdrop");
    expect(classe("components/Sidebar.tsx")).toContain("z-modal");
    expect(classe("components/ui/dialog.tsx")).toContain("z-modal");
    expect(classe("components/CommandPalette.tsx")).toContain("z-popover");
    expect(classe("components/LoadingBar.tsx")).toContain("z-toast");
    // a ordem que os valores garantem (era a ordem de fato antes da migração:
    // 30 < 40 < 50 < 100 < 200 — preservada, agora por decisão e não por acaso)
    expect(t.sticky).toBeLessThan(t["modal-backdrop"]);
    expect(t["modal-backdrop"]).toBeLessThan(t.modal);
    expect(t.modal).toBeLessThan(t.popover);
    expect(t.popover).toBeLessThan(t.toast);
  });
});

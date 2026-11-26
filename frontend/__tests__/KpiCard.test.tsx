/**
 * O número do KPI usa a fonte do tema e não divide a linha com o ícone.
 *
 * Era `font-mono`: uma terceira família na tela, fora do alcance da tela
 * "Aparência", e larga o bastante para cortar "R$ 1.772.060,00" ao lado do
 * ícone. O jsdom não mede largura; o que dá para travar é a estrutura que
 * causava o corte e a família aplicada.
 */
import { render, screen } from "@testing-library/react";
import { Wallet } from "lucide-react";
import { describe, expect, it } from "vitest";

import { KpiCard } from "@/components/ui/kpi-card";
import { aplicarFonte } from "@/lib/tema-cores";

describe("KpiCard", () => {
  it("o valor usa a fonte dos títulos, com algarismos tabulares, e não a monoespaçada", () => {
    render(<KpiCard label="Saldo total" value="R$ 1.772.060,00" icon={Wallet} />);
    const valor = screen.getByTestId("kpi-valor");
    expect(valor).toHaveTextContent("R$ 1.772.060,00");
    expect(valor.className).toContain("font-display");
    expect(valor.className).toContain("tabular-nums");
    expect(valor.className).not.toContain("font-mono");
  });

  it("o ícone não está na mesma linha do valor", () => {
    const { container } = render(
      <KpiCard label="Saldo total" value="R$ 1.772.060,00" icon={Wallet} />,
    );
    const valor = screen.getByTestId("kpi-valor");
    const icone = container.querySelector("svg") as SVGElement;
    // Quem contém o ícone não contém o valor: são blocos empilhados.
    expect(valor.parentElement?.contains(icone)).toBe(true);
    expect(icone.closest(".flex.items-start")?.contains(valor)).toBe(false);
  });

  it("a fonte escolhida em Aparência é a variável que o valor consome", () => {
    // `font-display` resolve para `var(--font-display)` (tailwind.config), e é
    // essa variável que a tela Aparência troca.
    const raiz = document.createElement("div");
    aplicarFonte(raiz, "nunito");
    expect(raiz.style.getPropertyValue("--font-display")).toBe("var(--font-nunito)");
    aplicarFonte(raiz, "montserrat");
    expect(raiz.style.getPropertyValue("--font-display")).toBe("");
  });
});

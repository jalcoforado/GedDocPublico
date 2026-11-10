/**
 * Coluna "Ações" padrão: no máximo N à vista, o resto no ⋯, a destrutiva por
 * último e nunca em vermelho cheio. Antes cada tela desenhava a sua — até seis
 * botões quebrando a linha em duas, com "Excluir" vermelho em todas.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";

describe("AcoesDaLinha", () => {
  it("com poucas ações, mostra todas e a destrutiva fica por último", () => {
    render(
      <AcoesDaLinha
        acoes={[
          { label: "Excluir", perigo: true, onClick: vi.fn() },
          { label: "Editar", onClick: vi.fn() },
        ]}
      />,
    );
    const botoes = screen.getAllByRole("button").map((b) => b.textContent);
    expect(botoes).toEqual(["Editar", "Excluir"]);
    expect(screen.queryByRole("button", { name: "Mais ações" })).toBeNull();
  });

  it("a destrutiva usa danger-outline, não o vermelho cheio", () => {
    render(<AcoesDaLinha acoes={[{ label: "Excluir", perigo: true, onClick: vi.fn() }]} />);
    const excluir = screen.getByRole("button", { name: "Excluir" });
    expect(excluir.className).toContain("text-danger-soft-foreground");
    expect(excluir.className).not.toContain("bg-danger ");
  });

  it("com muitas ações, o excedente vai para o menu e continua clicável", () => {
    const suspender = vi.fn();
    const excluir = vi.fn();
    render(
      <AcoesDaLinha
        acoes={[
          { label: "Detalhes", onClick: vi.fn() },
          { label: "Editar", onClick: vi.fn() },
          { label: "Suspender", onClick: suspender },
          { label: "Excluir", perigo: true, onClick: excluir },
        ]}
      />,
    );
    expect(screen.getByRole("button", { name: "Detalhes" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Editar" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Suspender" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Mais ações" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Excluir" }));
    expect(excluir).toHaveBeenCalledTimes(1);
    expect(suspender).not.toHaveBeenCalled();
  });

  it("ação oculta some da linha", () => {
    render(
      <AcoesDaLinha
        acoes={[
          { label: "Editar", onClick: vi.fn() },
          { label: "Excluir", perigo: true, oculta: true, onClick: vi.fn() },
        ]}
      />,
    );
    expect(screen.queryByRole("button", { name: "Excluir" })).toBeNull();
  });
});

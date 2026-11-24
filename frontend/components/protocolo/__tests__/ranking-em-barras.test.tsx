/**
 * Ranking em barras dos relatórios ("onde o processo para", "com quem estão
 * as assinaturas"): o topo aparece, o resto fica atrás de um botão, e a maior
 * barra é a do maior valor.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankingEmBarras } from "@/components/protocolo/RankingEmBarras";

const itens = Array.from({ length: 10 }, (_, i) => ({
  chave: i,
  rotulo: `Unidade ${i + 1}`,
  valor: 100 - i * 10,
  valorTexto: `${100 - i * 10} min`,
}));

describe("RankingEmBarras", () => {
  it("mostra só o limite e abre o resto no botão", () => {
    render(<RankingEmBarras itens={itens} limite={3} rotuloDoValor="tempo" vazio="nada" />);
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: /ver todos os 10/i }));
    expect(screen.getAllByRole("listitem")).toHaveLength(10);
  });

  it("a barra do primeiro ocupa a largura toda; as outras, proporcionais", () => {
    const { container } = render(
      <RankingEmBarras itens={itens.slice(0, 2)} rotuloDoValor="tempo" vazio="nada" />,
    );
    const barras = container.querySelectorAll<HTMLElement>("[role=presentation] > div");
    expect(barras[0].style.width).toBe("100%");
    expect(barras[1].style.width).toBe("90%");
  });

  it("lista vazia mostra o estado vazio, não uma lista sem itens", () => {
    render(<RankingEmBarras itens={[]} rotuloDoValor="tempo" vazio="Ninguém pendente" />);
    expect(screen.getByText("Ninguém pendente")).toBeInTheDocument();
    expect(screen.queryByRole("list")).toBeNull();
  });
});

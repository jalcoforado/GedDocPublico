/**
 * Linha que abre: clicar em qualquer parte da linha faz o mesmo que o link
 * "Analisar" dela; o botão e os links internos seguem fazendo o próprio papel.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TBody, TD, TRLink, Table } from "@/components/ui/table";

const HREF = "/m/pagamentos/solicitacoes/4";

function linha() {
  const navegou = vi.fn((e: React.MouseEvent) => e.preventDefault());
  const outroBotao = vi.fn();
  render(
    <Table>
      <TBody>
        <TRLink href={HREF} data-testid="linha">
          <TD>Alimentos Bom Prato</TD>
          <TD>
            <button type="button" onClick={outroBotao}>
              Excluir
            </button>
            <a href={HREF} onClick={navegou}>
              Analisar
            </a>
          </TD>
        </TRLink>
      </TBody>
    </Table>,
  );
  return { tr: screen.getByTestId("linha"), navegou, outroBotao };
}

describe("TRLink", () => {
  it("clicar no texto da linha faz o mesmo que o link 'Analisar'", () => {
    const { navegou } = linha();
    fireEvent.click(screen.getByText("Alimentos Bom Prato"));
    expect(navegou).toHaveBeenCalledTimes(1);
  });

  it("clicar no próprio link não navega duas vezes", () => {
    const { navegou } = linha();
    fireEvent.click(screen.getByRole("link", { name: "Analisar" }));
    expect(navegou).toHaveBeenCalledTimes(1);
  });

  it("clicar em outro botão da linha não abre a linha", () => {
    const { navegou, outroBotao } = linha();
    fireEvent.click(screen.getByRole("button", { name: "Excluir" }));
    expect(outroBotao).toHaveBeenCalled();
    expect(navegou).not.toHaveBeenCalled();
  });

  it("Enter na linha focada abre (teclado)", () => {
    const { tr, navegou } = linha();
    fireEvent.keyDown(tr, { key: "Enter" });
    expect(navegou).toHaveBeenCalledTimes(1);
  });

  it("Ctrl+clique abre em outra aba, sem navegar nesta", () => {
    const abrir = vi.spyOn(window, "open").mockImplementation(() => null);
    const { navegou } = linha();
    fireEvent.click(screen.getByText("Alimentos Bom Prato"), { ctrlKey: true });
    expect(abrir).toHaveBeenCalledWith(HREF, "_blank", "noopener");
    expect(navegou).not.toHaveBeenCalled();
    abrir.mockRestore();
  });
});

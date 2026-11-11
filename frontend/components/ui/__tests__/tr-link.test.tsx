/**
 * Linha que abre: clicar em qualquer parte da linha leva ao mesmo endereço do
 * botão dela; o botão e os links internos seguem fazendo o próprio papel.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import { TBody, TD, TRLink, Table } from "@/components/ui/table";

function linha(onBotao = vi.fn()) {
  render(
    <Table>
      <TBody>
        <TRLink href="/m/pagamentos/solicitacoes/4" data-testid="linha">
          <TD>Alimentos Bom Prato</TD>
          <TD>
            <button type="button" onClick={onBotao}>
              Analisar
            </button>
          </TD>
        </TRLink>
      </TBody>
    </Table>,
  );
  return screen.getByTestId("linha");
}

beforeEach(() => push.mockReset());

describe("TRLink", () => {
  it("clicar no texto da linha abre o endereço", () => {
    linha();
    fireEvent.click(screen.getByText("Alimentos Bom Prato"));
    expect(push).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/4");
  });

  it("clicar no botão da linha não dispara a linha junto", () => {
    const onBotao = vi.fn();
    linha(onBotao);
    fireEvent.click(screen.getByRole("button", { name: "Analisar" }));
    expect(onBotao).toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("Enter na linha focada abre (teclado)", () => {
    const tr = linha();
    fireEvent.keyDown(tr, { key: "Enter" });
    expect(push).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/4");
  });

  it("Ctrl+clique abre em outra aba, sem navegar nesta", () => {
    const abrir = vi.spyOn(window, "open").mockImplementation(() => null);
    linha();
    fireEvent.click(screen.getByText("Alimentos Bom Prato"), { ctrlKey: true });
    expect(abrir).toHaveBeenCalledWith("/m/pagamentos/solicitacoes/4", "_blank", "noopener");
    expect(push).not.toHaveBeenCalled();
    abrir.mockRestore();
  });
});

/**
 * UX-02 fatia 2.7 — Table: aria-sort no <th> (estava no botão interno, onde
 * leitor de tela não o associa à coluna), linha clicável operável por teclado
 * e SkeletonRow respeitando a densidade.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SkeletonRow, Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";

describe("TH ordenável — aria-sort", () => {
  function renderTH(sortState: "asc" | "desc" | null) {
    render(
      <Table>
        <THead>
          <tr>
            <TH sortable sortState={sortState} onSortToggle={() => {}}>
              Data
            </TH>
          </tr>
        </THead>
      </Table>,
    );
    return screen.getByRole("columnheader", { name: /Data/ });
  }

  it("asc/desc/none aparecem no PRÓPRIO th, não no botão interno", () => {
    const th = renderTH("asc");
    expect(th.tagName).toBe("TH");
    expect(th).toHaveAttribute("aria-sort", "ascending");
    expect(th.querySelector("button")).not.toHaveAttribute("aria-sort");
  });

  it("sem ordenação ativa: aria-sort=none", () => {
    expect(renderTH(null)).toHaveAttribute("aria-sort", "none");
  });
});

describe("TR clicável — teclado", () => {
  function renderRow(onClickRow: () => void) {
    render(
      <Table>
        <TBody>
          <TR onClickRow={onClickRow}>
            <TD>Processo 123</TD>
          </TR>
        </TBody>
      </Table>,
    );
    return screen.getByText("Processo 123").closest("tr") as HTMLElement;
  }

  it("entra na ordem de tabulação e ativa com Enter e Espaço", async () => {
    const onClickRow = vi.fn();
    const tr = renderRow(onClickRow);
    expect(tr).toHaveAttribute("tabindex", "0");
    tr.focus();
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard(" ");
    expect(onClickRow).toHaveBeenCalledTimes(2);
  });

  it("linha sem onClickRow não entra na ordem de tabulação", () => {
    render(
      <Table>
        <TBody>
          <TR>
            <TD>estática</TD>
          </TR>
        </TBody>
      </Table>,
    );
    const tr = screen.getByText("estática").closest("tr") as HTMLElement;
    expect(tr).not.toHaveAttribute("tabindex");
  });
});

describe("SkeletonRow", () => {
  it("renderiza uma célula skeleton por coluna, com a altura de linha da densidade", () => {
    render(
      <Table>
        <TBody>
          <SkeletonRow cols={4} />
        </TBody>
      </Table>,
    );
    const linha = document.querySelector("tbody tr") as HTMLElement;
    expect(linha.querySelectorAll("td").length).toBe(4);
    // density-aware: a altura vem do token --density-row-h, não de valor fixo
    expect(linha.className).toContain("--density-row-h");
  });

  it("é aria-hidden — esqueleto não é conteúdo para leitor de tela", () => {
    render(
      <Table>
        <TBody>
          <SkeletonRow cols={2} />
        </TBody>
      </Table>,
    );
    const linha = document.querySelector("tbody tr") as HTMLElement;
    expect(linha).toHaveAttribute("aria-hidden", "true");
  });
});

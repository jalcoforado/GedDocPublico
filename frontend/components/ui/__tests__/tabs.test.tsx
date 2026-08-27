/**
 * UX-02 fatia 2.5 — Tabs com ARIA completo: tablist/tab/tabpanel ligados,
 * seleção controlada e navegação por teclado (setas, Home, End).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";

function Harness() {
  const [tab, setTab] = React.useState("dados");
  return (
    <Tabs value={tab} onChange={setTab}>
      <TabList
        aria-label="Seções do processo"
        tabs={[
          { value: "dados", label: "Dados" },
          { value: "anexos", label: "Anexos" },
          { value: "historico", label: "Histórico" },
        ]}
      />
      <TabPanel value="dados">Conteúdo de dados</TabPanel>
      <TabPanel value="anexos">Conteúdo de anexos</TabPanel>
      <TabPanel value="historico">Conteúdo de histórico</TabPanel>
    </Tabs>
  );
}

describe("Tabs — estrutura ARIA", () => {
  it("tablist com tabs; a ativa tem aria-selected e o painel correspondente aparece", () => {
    render(<Harness />);
    expect(screen.getByRole("tablist", { name: "Seções do processo" })).toBeTruthy();
    const ativa = screen.getByRole("tab", { name: "Dados" });
    expect(ativa).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel").textContent).toBe("Conteúdo de dados");
    // painéis inativos não aparecem
    expect(screen.queryByText("Conteúdo de anexos")).toBeNull();
  });

  it("tab e painel se referenciam (aria-controls / aria-labelledby)", () => {
    render(<Harness />);
    const tab = screen.getByRole("tab", { name: "Dados" });
    const painel = screen.getByRole("tabpanel");
    expect(tab.getAttribute("aria-controls")).toBe(painel.id);
    expect(painel.getAttribute("aria-labelledby")).toBe(tab.id);
  });

  it("clicar troca o painel", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("tab", { name: "Anexos" }));
    expect(screen.getByRole("tabpanel").textContent).toBe("Conteúdo de anexos");
  });
});

describe("Tabs — teclado", () => {
  it("setas movem foco e seleção; Home/End vão para as pontas; extremos dão a volta", async () => {
    render(<Harness />);
    const dados = screen.getByRole("tab", { name: "Dados" });
    dados.focus();

    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Anexos" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Anexos" })).toHaveAttribute("aria-selected", "true");

    await userEvent.keyboard("{End}");
    expect(screen.getByRole("tab", { name: "Histórico" })).toHaveFocus();

    await userEvent.keyboard("{ArrowRight}"); // dá a volta
    expect(screen.getByRole("tab", { name: "Dados" })).toHaveFocus();

    await userEvent.keyboard("{ArrowLeft}"); // volta pelo outro lado
    expect(screen.getByRole("tab", { name: "Histórico" })).toHaveFocus();

    await userEvent.keyboard("{Home}");
    expect(screen.getByRole("tab", { name: "Dados" })).toHaveFocus();
  });

  it("apenas a tab ativa está na ordem de tabulação (roving tabindex)", () => {
    render(<Harness />);
    expect(screen.getByRole("tab", { name: "Dados" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("tab", { name: "Anexos" })).toHaveAttribute("tabindex", "-1");
  });
});

/**
 * `keepMounted` — painel inativo continua no DOM, escondido.
 *
 * A opção existe porque desmontar apaga o estado local da aba sem nenhum aviso
 * ao usuário (o caso real: o admin marca módulos na edição de tenant, olha
 * "Dados" e volta com as marcações perdidas). Um teste que só confirmasse "o
 * painel some" não distinguiria as duas coisas, então aqui as duas
 * possibilidades são exercitadas lado a lado.
 */
function HarnessKeepMounted() {
  const [tab, setTab] = React.useState("a");
  return (
    <Tabs value={tab} onChange={setTab}>
      <TabList
        aria-label="Com estado"
        tabs={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />
      <TabPanel value="a" keepMounted>
        <input aria-label="campo" defaultValue="" />
      </TabPanel>
      <TabPanel value="b" keepMounted>
        Painel B
      </TabPanel>
    </Tabs>
  );
}

describe("Tabs — keepMounted", () => {
  it("sem keepMounted, o painel inativo NÃO está no DOM", () => {
    render(<Harness />);
    expect(screen.queryByText("Conteúdo de anexos")).toBeNull();
  });

  it("com keepMounted, o painel inativo fica no DOM porém hidden", async () => {
    render(<HarnessKeepMounted />);
    const painelB = screen.getByText("Painel B");
    expect(painelB).toBeTruthy();
    expect(painelB.hasAttribute("hidden")).toBe(true);

    await userEvent.click(screen.getByRole("tab", { name: "B" }));
    expect(painelB.hasAttribute("hidden")).toBe(false);
  });

  it("o painel oculto sai da ordem de tabulação", () => {
    render(<HarnessKeepMounted />);
    const [pa, pb] = screen.getAllByRole("tabpanel", { hidden: true });
    expect(pa.getAttribute("tabindex")).toBe("0");
    expect(pb.getAttribute("tabindex")).toBe("-1");
  });

  it("o estado digitado sobrevive à troca de aba e à volta", async () => {
    render(<HarnessKeepMounted />);
    await userEvent.type(screen.getByLabelText("campo"), "rascunho");
    await userEvent.click(screen.getByRole("tab", { name: "B" }));
    await userEvent.click(screen.getByRole("tab", { name: "A" }));
    expect((screen.getByLabelText("campo") as HTMLInputElement).value).toBe("rascunho");
  });
});

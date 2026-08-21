/**
 * UX-02 fatia 2.6 — combobox: painel via Popover (Floating UI) e "Limpar
 * seleção" focável de verdade. O limpar era um span tabIndex=-1 DENTRO do
 * botão do trigger (aninhamento interativo inválido) — teclado nunca chegava
 * nele.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Combobox } from "@/components/ui/combobox";

const OPCOES = [
  { value: 1, label: "Protocolo Geral" },
  { value: 2, label: "Ouvidoria" },
  { value: 3, label: "Tributos", hint: "Secretaria da Fazenda" },
];

describe("Combobox — regressão do fluxo básico", () => {
  it("abre, filtra e seleciona por clique", async () => {
    const onChange = vi.fn();
    render(<Combobox options={OPCOES} value={null} onChange={onChange} />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.type(screen.getByPlaceholderText("Buscar…"), "ouvi");
    await userEvent.click(screen.getByRole("option", { name: /Ouvidoria/ }));
    expect(onChange).toHaveBeenCalledWith(2, expect.objectContaining({ value: 2 }));
  });

  it("navega com setas e seleciona com Enter", async () => {
    const onChange = vi.fn();
    render(<Combobox options={OPCOES} value={null} onChange={onChange} />);
    await userEvent.click(screen.getByRole("combobox"));
    // o foco do input de busca chega via requestAnimationFrame — teclar antes
    // dele perde a seta (aconteceu no runner do CI, não localmente)
    await waitFor(() => expect(screen.getByPlaceholderText("Buscar…")).toHaveFocus());
    await userEvent.keyboard("{ArrowDown}{Enter}");
    expect(onChange).toHaveBeenCalledWith(2, expect.objectContaining({ value: 2 }));
  });
});

describe("Combobox — painel via Popover", () => {
  it("o painel renderiza pelo primitivo Popover (portal, fora do wrapper)", async () => {
    render(
      <div data-testid="recorte" style={{ overflow: "hidden" }}>
        <Combobox options={OPCOES} value={null} onChange={() => {}} />
      </div>,
    );
    await userEvent.click(screen.getByRole("combobox"));
    const lista = screen.getByRole("listbox");
    expect(screen.getByTestId("recorte").contains(lista)).toBe(false);
    expect(lista.closest("[data-popover]")).not.toBeNull();
  });

  it("Escape fecha e devolve o foco ao trigger", async () => {
    render(<Combobox options={OPCOES} value={null} onChange={() => {}} />);
    const trigger = screen.getByRole("combobox");
    await userEvent.click(trigger);
    expect(screen.getByRole("listbox")).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(trigger).toHaveFocus();
  });
});

describe("Combobox — limpar seleção acessível", () => {
  it("é um <button> alcançável por Tab, irmão do trigger (sem aninhamento interativo)", async () => {
    render(<Combobox options={OPCOES} value={1} onChange={() => {}} />);
    const limpar = screen.getByRole("button", { name: "Limpar seleção" });
    expect(limpar.tagName).toBe("BUTTON");
    expect(limpar).not.toHaveAttribute("tabindex", "-1");
    // não pode morar dentro do botão do combobox
    expect(screen.getByRole("combobox").contains(limpar)).toBe(false);
  });

  it("aciona por teclado e limpa o valor sem abrir o dropdown", async () => {
    const onChange = vi.fn();
    render(<Combobox options={OPCOES} value={1} onChange={onChange} />);
    const limpar = screen.getByRole("button", { name: "Limpar seleção" });
    limpar.focus();
    await userEvent.keyboard("{Enter}");
    expect(onChange).toHaveBeenCalledWith(null, null);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("sem seleção (ou disabled) o limpar não existe", () => {
    const { rerender } = render(
      <Combobox options={OPCOES} value={null} onChange={() => {}} />,
    );
    expect(screen.queryByRole("button", { name: "Limpar seleção" })).toBeNull();
    rerender(<Combobox options={OPCOES} value={1} onChange={() => {}} disabled />);
    expect(screen.queryByRole("button", { name: "Limpar seleção" })).toBeNull();
  });
});

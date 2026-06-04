import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Printer } from "lucide-react";
import { describe, expect, it, vi } from "vitest";

import { ActionsMenu } from "@/components/ui/actions-menu";

describe("ActionsMenu", () => {
  it("começa fechado e abre ao clicar no botão", async () => {
    const fn = vi.fn();
    render(
      <ActionsMenu
        label="Imprimir"
        icon={Printer}
        items={[{ label: "Capa", onClick: fn }]}
      />,
    );
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: /imprimir/i }),
    );
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: /capa/i })).toBeInTheDocument();
  });

  it("clicar em item dispara onClick e fecha o menu", async () => {
    const onCapa = vi.fn();
    const onEtiqueta = vi.fn();
    render(
      <ActionsMenu
        label="Imprimir"
        items={[
          { label: "Capa", onClick: onCapa },
          { label: "Etiqueta", onClick: onEtiqueta },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /imprimir/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /capa/i }));
    expect(onCapa).toHaveBeenCalledTimes(1);
    expect(onEtiqueta).not.toHaveBeenCalled();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("ESC fecha o menu", async () => {
    render(
      <ActionsMenu
        label="Imprimir"
        items={[{ label: "Capa", onClick: vi.fn() }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /imprimir/i }));
    expect(screen.getByRole("menu")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("item disabled não dispara onClick", async () => {
    const onCapa = vi.fn();
    render(
      <ActionsMenu
        label="Imprimir"
        items={[{ label: "Capa", onClick: onCapa, disabled: true }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /imprimir/i }));
    const item = screen.getByRole("menuitem", { name: /capa/i });
    expect(item).toBeDisabled();
    await userEvent.click(item);
    expect(onCapa).not.toHaveBeenCalled();
  });

  it("renderiza ícones dos itens quando fornecidos", async () => {
    render(
      <ActionsMenu
        label="Imprimir"
        items={[{ label: "Capa", icon: Printer, onClick: vi.fn() }]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /imprimir/i }));
    const menuitem = screen.getByRole("menuitem", { name: /capa/i });
    expect(menuitem.querySelector("svg")).toBeInTheDocument();
  });

  it("aria-expanded reflete estado", async () => {
    render(
      <ActionsMenu
        label="Imprimir"
        items={[{ label: "Capa", onClick: vi.fn() }]}
      />,
    );
    const trigger = screen.getByRole("button", { name: /imprimir/i });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });
});

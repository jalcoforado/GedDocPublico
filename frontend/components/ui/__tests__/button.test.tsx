import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { Button } from "@/components/ui/button";

describe("Button — modo nativo (regressão)", () => {
  it("renderiza um <button> com type=button por default", () => {
    render(<Button>Salvar</Button>);
    const btn = screen.getByRole("button", { name: "Salvar" });
    expect(btn.tagName).toBe("BUTTON");
    expect(btn).toHaveAttribute("type", "button");
  });

  it("dispara onClick em modo nativo", async () => {
    const fn = vi.fn();
    render(<Button onClick={fn}>X</Button>);
    await userEvent.click(screen.getByRole("button"));
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("aceita className extra preservando classes base", () => {
    render(<Button className="ring-2 ring-amber-500">Y</Button>);
    const btn = screen.getByRole("button", { name: "Y" });
    expect(btn.className).toContain("ring-amber-500");
    expect(btn.className).toContain("inline-flex");
  });
});

describe("Button — asChild", () => {
  it("renderiza o filho em vez de <button>", () => {
    render(
      <Button asChild>
        <a href="/x">Ir</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Ir" });
    expect(link.tagName).toBe("A");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("propaga className do Button para o filho mesclando com a do próprio filho", () => {
    render(
      <Button asChild className="extra-from-button">
        <a href="/x" className="extra-from-child">Ir</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Ir" });
    expect(link.className).toContain("extra-from-button");
    expect(link.className).toContain("extra-from-child");
    // Classes base também migram:
    expect(link.className).toContain("inline-flex");
  });

  it("aplica variant ao filho (cores da variante 'danger')", () => {
    render(
      <Button asChild variant="danger">
        <a href="/x">Apagar</a>
      </Button>,
    );
    const link = screen.getByRole("link");
    expect(link.className).toContain("bg-danger");
  });

  it("propaga onClick para o filho", async () => {
    const fn = vi.fn((e: React.MouseEvent) => e.preventDefault());
    render(
      <Button asChild onClick={fn}>
        <a href="/x">Ir</a>
      </Button>,
    );
    await userEvent.click(screen.getByRole("link"));
    expect(fn).toHaveBeenCalledTimes(1);
  });
});

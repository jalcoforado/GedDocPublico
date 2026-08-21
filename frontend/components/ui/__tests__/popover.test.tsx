/**
 * UX-02 fatia 2.6 — Popover base (Floating UI). O que importa provar aqui:
 * portal (escapa de overflow-hidden) e posição fixed calculada. Flip/colisão
 * são da Floating UI (não re-testamos a biblioteca).
 */
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { Popover } from "@/components/ui/popover";

function Harness({ open }: { open: boolean }) {
  const anchorRef = React.useRef<HTMLButtonElement>(null);
  return (
    <div data-testid="recorte" style={{ overflow: "hidden" }}>
      <button ref={anchorRef} type="button">
        âncora
      </button>
      <Popover open={open} anchorRef={anchorRef} onClose={() => {}}>
        <p>conteúdo flutuante</p>
      </Popover>
    </div>
  );
}

describe("Popover", () => {
  it("fechado não renderiza nada", () => {
    render(<Harness open={false} />);
    expect(screen.queryByText("conteúdo flutuante")).toBeNull();
  });

  it("aberto renderiza em portal (fora do container com overflow) com position fixed", () => {
    render(<Harness open />);
    const conteudo = screen.getByText("conteúdo flutuante");
    expect(screen.getByTestId("recorte").contains(conteudo)).toBe(false);
    const painel = conteudo.closest("[data-popover]") as HTMLElement;
    expect(painel.style.position).toBe("fixed");
  });
});

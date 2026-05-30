import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CancelarComplementacaoDialog } from "@/components/CancelarComplementacaoDialog";

describe("CancelarComplementacaoDialog (PR 4d)", () => {
  it("envia motivo null quando vazio", () => {
    const onSubmit = vi.fn();
    render(
      <CancelarComplementacaoDialog
        open
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Confirmar cancelamento/i }));
    expect(onSubmit).toHaveBeenCalledWith({ motivo: null });
  });

  it("envia motivo preenchido (trim)", () => {
    const onSubmit = vi.fn();
    render(
      <CancelarComplementacaoDialog
        open
        onClose={vi.fn()}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Motivo/i), {
      target: { value: "  enviado por outro canal  " },
    });
    fireEvent.click(screen.getByRole("button", { name: /Confirmar cancelamento/i }));
    expect(onSubmit).toHaveBeenCalledWith({ motivo: "enviado por outro canal" });
  });
});

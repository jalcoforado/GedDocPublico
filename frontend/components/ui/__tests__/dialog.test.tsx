import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { Dialog } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";

/**
 * Regressão: `onClose` costuma ser um arrow function inline no call-site
 * (`onClose={() => setOpen(false)}`), então toda vez que o componente pai
 * re-renderiza — inclusive por causa de um campo controlado dentro do
 * próprio dialog — `onClose` ganha uma referência nova. O efeito de foco
 * inicial do Dialog tinha `onClose` nas dependências, então rodava de novo
 * a cada letra digitada e devolvia o foco pro primeiro elemento focável
 * (o botão "Fechar"), tirando o foco do campo de texto no meio da digitação.
 */
function ParentComCampoControlado() {
  const [open] = React.useState(true);
  const [texto, setTexto] = React.useState("");
  return (
    <Dialog open={open} onClose={() => {}} title="Rejeitar solicitação">
      <Textarea
        aria-label="Justificativa"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
      />
    </Dialog>
  );
}

describe("Dialog — foco (regressão)", () => {
  it("não rouba o foco do campo ao digitar, mesmo com onClose inline no pai", async () => {
    render(<ParentComCampoControlado />);
    const campo = screen.getByLabelText("Justificativa");
    campo.focus();

    await userEvent.type(campo, "abc");

    expect(campo).toHaveValue("abc");
    expect(campo).toHaveFocus();
  });
});

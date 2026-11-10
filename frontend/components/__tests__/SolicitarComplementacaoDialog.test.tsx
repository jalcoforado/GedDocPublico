import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SolicitarComplementacaoDialog } from "@/components/SolicitarComplementacaoDialog";
import type { ChecklistDocumentosResponse } from "@/lib/api";

const CHECKLIST: ChecklistDocumentosResponse = {
  id_processo: 1,
  id_servico: 2,
  status_documental: "pendente",
  obrigatorios_total: 2,
  obrigatorios_enviados: 0,
  itens: [
    { key: "rg", nome: "RG", obrigatorio: true, descricao: null, enviado: false, anexos: [] },
    { key: "cpf", nome: "CPF", obrigatorio: true, descricao: null, enviado: true, anexos: [{ id_anexo: 1, descricao: "cpf" }] },
    { key: "comp", nome: "Comprovante", obrigatorio: false, descricao: null, enviado: false, anexos: [] },
  ],
  complementacao_aberta: null,
};

describe("SolicitarComplementacaoDialog (PR 4d)", () => {
  it("pré-marca os itens não enviados", () => {
    const onSubmit = vi.fn();
    render(
      <SolicitarComplementacaoDialog
        open
        onClose={vi.fn()}
        checklist={CHECKLIST}
        onSubmit={onSubmit}
      />,
    );
    const rg = screen.getByLabelText("RG") as HTMLInputElement;
    const cpf = screen.getByLabelText(/CPF/) as HTMLInputElement;
    const compc = screen.getByLabelText("Comprovante") as HTMLInputElement;
    expect(rg.checked).toBe(true);
    expect(cpf.checked).toBe(false); // já enviado
    expect(compc.checked).toBe(true);
  });

  it("valida mensagem obrigatória + pelo menos 1 doc; envia payload correto", () => {
    const onSubmit = vi.fn();
    render(
      <SolicitarComplementacaoDialog
        open
        onClose={vi.fn()}
        checklist={CHECKLIST}
        onSubmit={onSubmit}
      />,
    );
    const submit = screen.getByRole("button", { name: /Enviar solicitação/i });
    // Padrão de formulário: nunca desabilitado por validação. Sem mensagem,
    // clicar mostra o erro sob o campo e não envia.
    expect(screen.queryByText(/Escreva a mensagem/)).toBeNull();
    fireEvent.click(submit);
    expect(screen.getByText(/Escreva a mensagem/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Mensagem ao cidadão/i), {
      target: { value: "Por favor envie." },
    });

    fireEvent.click(submit);
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.mensagem).toBe("Por favor envie.");
    expect(new Set(payload.documentos_solicitados)).toEqual(new Set(["rg", "comp"]));
  });

  it("desmarcar todos os checkboxes impede o envio e diz o que falta", () => {
    const onSubmit = vi.fn();
    render(
      <SolicitarComplementacaoDialog
        open
        onClose={vi.fn()}
        checklist={CHECKLIST}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Mensagem ao cidadão/i), {
      target: { value: "x" },
    });
    fireEvent.click(screen.getByLabelText("RG"));
    fireEvent.click(screen.getByLabelText("Comprovante"));
    fireEvent.click(screen.getByRole("button", { name: /Enviar solicitação/i }));
    expect(screen.getByText("Marque pelo menos um documento.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

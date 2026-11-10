/**
 * Peças do padrão de formulário (2026-11-10): o que FormField ganhou
 * (opcional, ação ao lado do rótulo, erro no lugar da dica), a escolha
 * segmentada, o campo com unidade e o roteiro com o que falta.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { RoteiroFormulario, resumoDoQueFalta, type EtapaRoteiro } from "@/components/ui/roteiro-formulario";

describe("FormField", () => {
  it("marca 'opcional' só quando o campo não é obrigatório", () => {
    const { rerender } = render(
      <FormField label="Número de origem" opcional>
        <Input />
      </FormField>,
    );
    expect(screen.getByText("opcional")).toBeInTheDocument();
    rerender(
      <FormField label="Número de origem" opcional required>
        <Input />
      </FormField>,
    );
    expect(screen.queryByText("opcional")).toBeNull();
  });

  it("com erro, a dica sai de vista mas continua descrevendo o campo", () => {
    render(
      <FormField label="CPF" hint="Só números" error="CPF inválido: confira os dígitos.">
        <Input />
      </FormField>,
    );
    const campo = screen.getByLabelText("CPF");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription(/Só números.*CPF inválido/);
    expect(screen.getByText("Só números").className).toContain("sr-only");
  });

  it("a ação fica ao lado do rótulo", () => {
    render(
      <FormField label="Manifestante" acao={<a href="/novo">Cadastrar novo</a>}>
        <Input />
      </FormField>,
    );
    expect(screen.getByRole("link", { name: "Cadastrar novo" })).toBeInTheDocument();
    expect(screen.getByLabelText("Manifestante")).toBeInTheDocument();
  });
});

describe("EscolhaSegmentada", () => {
  it("todas as opções à vista; a descrição é a da marcada", () => {
    const onChange = vi.fn();
    render(
      <EscolhaSegmentada
        nome="vis"
        titulo="Visibilidade"
        valor="publico"
        onChange={onChange}
        opcoes={[
          { valor: "publico", rotulo: "Público", descricao: "Qualquer servidor vê." },
          { valor: "sigiloso", rotulo: "Sigiloso", descricao: "Só autorizados." },
        ]}
      />,
    );
    expect(screen.getByRole("radio", { name: "Público" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Público" })).toHaveAccessibleDescription("Qualquer servidor vê.");
    fireEvent.click(screen.getByRole("radio", { name: "Sigiloso" }));
    expect(onChange).toHaveBeenCalledWith("sigiloso");
  });
});

describe("CampoComUnidade", () => {
  it("mostra a unidade sem entrar no nome acessível", () => {
    render(
      <FormField label="Valor total">
        <CampoComUnidade prefixo="R$" />
      </FormField>,
    );
    expect(screen.getByText("R$")).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByRole("textbox", { name: "Valor total" })).toBeInTheDocument();
  });
});

describe("RoteiroFormulario", () => {
  const etapas: EtapaRoteiro[] = [
    { id: "e1", titulo: "Identificação", faltando: [{ rotulo: "Manifestante", campoId: "manif" }, { rotulo: "Assunto", campoId: "assunto" }] },
    { id: "e2", titulo: "Conteúdo", faltando: [], opcional: true },
    { id: "e3", titulo: "Configurações", faltando: [] },
  ];

  it("conta só as etapas obrigatórias e lista o que falta", () => {
    render(<RoteiroFormulario etapas={etapas} />);
    expect(screen.getByText("1 de 2")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByRole("button", { name: "Manifestante" })).toBeInTheDocument();
  });

  it("clicar no que falta leva ao campo", () => {
    render(
      <>
        <input id="manif" aria-label="campo" />
        <RoteiroFormulario etapas={etapas} />
      </>,
    );
    Element.prototype.scrollIntoView = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Manifestante" }));
    expect(screen.getByLabelText("campo")).toHaveFocus();
  });

  it("resumo de bolso para a barra de ações", () => {
    expect(resumoDoQueFalta(etapas)).toBe("Falta: Manifestante e Assunto.");
    expect(resumoDoQueFalta([{ id: "x", titulo: "x", faltando: [] }])).toBeNull();
  });
});

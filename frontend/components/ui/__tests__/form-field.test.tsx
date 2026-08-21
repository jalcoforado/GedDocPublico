/**
 * UX-02 fatia 2.4 — FormField e estado de erro dos controles.
 *
 * O que a fatia fecha: erro de validação hoje é um texto solto que leitor de
 * tela não associa ao campo (sem aria-describedby/aria-invalid), e cada tela
 * refaz Label+hint+erro à mão de um jeito.
 */
import { render, screen } from "@testing-library/react";
import * as React from "react";
import { describe, expect, it } from "vitest";

import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

describe("FormField — ligação label/controle", () => {
  it("o controle é encontrável pelo label (htmlFor/id gerados)", () => {
    render(
      <FormField label="Nome">
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText("Nome")).toBeTruthy();
  });

  it("required marca o label e o controle", () => {
    render(
      <FormField label="Nome" required>
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText(/Nome/)).toHaveAttribute("required");
  });
});

describe("FormField — hint e erro", () => {
  it("hint entra no aria-describedby do controle", () => {
    render(
      <FormField label="CPF" hint="Somente números.">
        <Input />
      </FormField>,
    );
    const campo = screen.getByLabelText("CPF");
    const ids = campo.getAttribute("aria-describedby") ?? "";
    const textos = ids
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent)
      .join(" ");
    expect(textos).toContain("Somente números.");
  });

  it("com error: aria-invalid no controle, erro visível e no aria-describedby", () => {
    render(
      <FormField label="CPF" hint="Somente números." error="CPF inválido.">
        <Input />
      </FormField>,
    );
    const campo = screen.getByLabelText("CPF");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    const ids = campo.getAttribute("aria-describedby") ?? "";
    const textos = ids
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent)
      .join(" ");
    expect(textos).toContain("CPF inválido.");
    expect(screen.getByText("CPF inválido.")).toBeTruthy();
  });

  it("sem error: sem aria-invalid", () => {
    render(
      <FormField label="CPF">
        <Input />
      </FormField>,
    );
    expect(screen.getByLabelText("CPF")).not.toHaveAttribute("aria-invalid");
  });

  it("funciona com Select e Textarea, não só Input", () => {
    render(
      <>
        <FormField label="Tipo" error="Escolha um tipo.">
          <Select>
            <option value="">—</option>
          </Select>
        </FormField>
        <FormField label="Observações" error="Obrigatório.">
          <Textarea />
        </FormField>
      </>,
    );
    expect(screen.getByLabelText("Tipo")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Observações")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("controles — borda de erro", () => {
  it("Input/Select/Textarea carregam a variante de borda danger para aria-invalid", () => {
    const { container } = render(
      <>
        <Input aria-invalid="true" />
        <Select aria-invalid="true" />
        <Textarea aria-invalid="true" />
      </>,
    );
    for (const el of Array.from(container.querySelectorAll("input,select,textarea"))) {
      expect(el.className).toContain("aria-[invalid=true]:border-danger");
    }
  });
});

describe("focarPrimeiroInvalido", () => {
  it("foca o primeiro controle com aria-invalid no documento", () => {
    render(
      <form data-testid="form">
        <FormField label="A">
          <Input />
        </FormField>
        <FormField label="B" error="erro em B">
          <Input />
        </FormField>
        <FormField label="C" error="erro em C">
          <Input />
        </FormField>
      </form>,
    );
    focarPrimeiroInvalido(screen.getByTestId("form"));
    expect(screen.getByLabelText("B")).toHaveFocus();
  });

  it("sem inválidos, não move o foco", () => {
    render(
      <form data-testid="form">
        <FormField label="A">
          <Input />
        </FormField>
      </form>,
    );
    const antes = document.activeElement;
    focarPrimeiroInvalido(screen.getByTestId("form"));
    expect(document.activeElement).toBe(antes);
  });
});

/**
 * UX-02 fatia 2.5 — Alert (4 intents, substitui as variantes manuais das
 * telas) e Spinner (o "Carregando…" textual padronizado em um só lugar).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Alert } from "@/components/ui/alert";
import { Spinner } from "@/components/ui/spinner";

describe("Alert", () => {
  it("renderiza título e corpo com o estilo do intent", () => {
    render(
      <Alert intent="warning" title="Atenção">
        O prazo vence amanhã.
      </Alert>,
    );
    const alerta = screen.getByText("O prazo vence amanhã.").closest("div[data-intent]");
    expect(alerta).toHaveAttribute("data-intent", "warning");
    expect(screen.getByText("Atenção")).toBeTruthy();
  });

  it("danger é anunciado como role=alert; info não é live region", () => {
    render(
      <>
        <Alert intent="danger">Falhou.</Alert>
        <Alert intent="info">Só um aviso.</Alert>
      </>,
    );
    expect(screen.getByRole("alert").textContent).toContain("Falhou.");
    expect(screen.getByText("Só um aviso.").closest("[role]")).toBeNull();
  });

  it("aceita os quatro intents", () => {
    render(
      <>
        <Alert intent="info">i</Alert>
        <Alert intent="success">s</Alert>
        <Alert intent="warning">w</Alert>
        <Alert intent="danger">d</Alert>
      </>,
    );
    for (const texto of ["i", "s", "w", "d"]) {
      expect(screen.getByText(texto)).toBeTruthy();
    }
  });
});

describe("Spinner", () => {
  it("tem role=status e rótulo acessível (default 'Carregando')", () => {
    render(<Spinner />);
    const s = screen.getByRole("status");
    expect(s).toHaveAccessibleName(/carregando/i);
  });

  it("aceita rótulo customizado", () => {
    render(<Spinner label="Enviando anexo" />);
    expect(screen.getByRole("status")).toHaveAccessibleName("Enviando anexo");
  });
});

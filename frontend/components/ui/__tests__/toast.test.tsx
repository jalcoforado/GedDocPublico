/**
 * UX-02 fatia 2.2 — Toast: erro audível (role=alert), pausa no hover/foco e
 * limite de fila. O modo de falha que motivou a fatia: erro anunciado como
 * "status" educado some antes de leitor de tela chegar nele, e uma rajada de
 * toasts empilhava sem limite cobrindo a tela.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider, useToast } from "@/components/ui/toast";

function Harness() {
  const t = useToast();
  return (
    <div>
      <button type="button" onClick={() => t.error("Falhou ao salvar")}>
        erro
      </button>
      <button type="button" onClick={() => t.success("Salvo")}>
        sucesso
      </button>
      <button type="button" onClick={() => t.info(`Aviso ${Math.random()}`)}>
        info
      </button>
    </div>
  );
}

function renderComToasts() {
  return render(
    <ToastProvider>
      <Harness />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("Toast — papel por intent", () => {
  it("erro usa role=alert (assertive); sucesso usa role=status (polite)", () => {
    renderComToasts();
    fireEvent.click(screen.getByText("erro"));
    fireEvent.click(screen.getByText("sucesso"));
    expect(screen.getByRole("alert").textContent).toContain("Falhou ao salvar");
    expect(screen.getByRole("status").textContent).toContain("Salvo");
  });
});

describe("Toast — pausa no hover e no foco", () => {
  it("com o mouse em cima o toast não expira; ao sair, volta a contar", () => {
    renderComToasts();
    fireEvent.click(screen.getByText("sucesso"));
    const toast = screen.getByRole("status");

    fireEvent.mouseEnter(toast);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toBeTruthy(); // pausado, não expirou

    fireEvent.mouseLeave(toast);
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("com foco dentro (ex.: no botão de ação) o toast não expira", () => {
    renderComToasts();
    fireEvent.click(screen.getByText("sucesso"));
    const fechar = screen.getByLabelText("Fechar notificação");

    fireEvent.focusIn(fechar);
    act(() => {
      vi.advanceTimersByTime(60_000);
    });
    expect(screen.getByRole("status")).toBeTruthy();

    fireEvent.focusOut(fechar);
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("Toast — limite de fila", () => {
  it("mais que o limite: os mais antigos saem, os recentes ficam", () => {
    renderComToasts();
    for (let i = 0; i < 5; i++) fireEvent.click(screen.getByText("info"));
    const visiveis = screen.getAllByRole("status");
    expect(visiveis.length).toBeLessThanOrEqual(3);
  });
});

describe("Toast — expiração normal (regressão)", () => {
  it("sem interação, some após a duração", () => {
    renderComToasts();
    fireEvent.click(screen.getByText("sucesso"));
    expect(screen.getByRole("status")).toBeTruthy();
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(screen.queryByRole("status")).toBeNull();
  });
});

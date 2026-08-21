/**
 * UX-02 fatia 2.3 — confirm com estado async: quando a confirmação carrega um
 * `onConfirm` assíncrono, o botão Confirmar entra em loading e o dialog NÃO
 * fecha antes de a ação terminar. Sem isso, o call site fecha o modal e a
 * falha da ação aparece "do nada", sem contexto.
 */
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmProvider, useConfirm } from "@/components/ui/confirm";

function Harness({ onConfirm, resultado }: {
  onConfirm?: () => Promise<void>;
  resultado: (v: boolean) => void;
}) {
  const confirm = useConfirm();
  return (
    <button
      type="button"
      onClick={async () => {
        const ok = await confirm({
          message: "Excluir o anexo?",
          confirmLabel: "Excluir",
          intent: "danger",
          onConfirm,
        });
        resultado(ok);
      }}
    >
      abrir
    </button>
  );
}

function renderHarness(props: Omit<React.ComponentProps<typeof Harness>, never>) {
  return render(
    <ConfirmProvider>
      <Harness {...props} />
    </ConfirmProvider>,
  );
}

describe("confirm — regressão do fluxo síncrono", () => {
  it("confirmar resolve true e fecha; cancelar resolve false", async () => {
    const resultado = vi.fn();
    renderHarness({ resultado });
    await userEvent.click(screen.getByText("abrir"));
    await userEvent.click(screen.getByRole("button", { name: "Excluir" }));
    await waitFor(() => expect(resultado).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).toBeNull();

    await userEvent.click(screen.getByText("abrir"));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(resultado).toHaveBeenCalledWith(false));
  });
});

describe("confirm — onConfirm async (UX-02 fatia 2.3)", () => {
  it("enquanto onConfirm roda, o botão fica em loading e o dialog aberto; ao resolver, fecha e resolve true", async () => {
    let libera!: () => void;
    const pendura = new Promise<void>((r) => { libera = r; });
    const onConfirm = vi.fn(() => pendura);
    const resultado = vi.fn();
    renderHarness({ onConfirm, resultado });

    await userEvent.click(screen.getByText("abrir"));
    await userEvent.click(screen.getByRole("button", { name: /Excluir/ }));

    // ação em voo: dialog aberto, botão ocupado, promise do confirm pendente
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Excluir/ })).toHaveAttribute("aria-busy", "true");
    expect(resultado).not.toHaveBeenCalled();

    await act(async () => libera());
    await waitFor(() => expect(resultado).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("clicar Excluir de novo durante o voo não dispara onConfirm duas vezes", async () => {
    let libera!: () => void;
    const onConfirm = vi.fn(() => new Promise<void>((r) => { libera = r; }));
    const resultado = vi.fn();
    renderHarness({ onConfirm, resultado });

    await userEvent.click(screen.getByText("abrir"));
    const botao = screen.getByRole("button", { name: /Excluir/ });
    await userEvent.click(botao);
    await userEvent.click(botao).catch(() => {});
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await act(async () => libera());
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("onConfirm que rejeita: o dialog fecha e a promise do confirm rejeita (caller trata o erro)", async () => {
    const erro = new Error("500 do backend");
    const onConfirm = vi.fn(() => Promise.reject(erro));
    const capturado = vi.fn();

    function HarnessComCatch() {
      const confirm = useConfirm();
      return (
        <button
          type="button"
          onClick={() =>
            confirm({ message: "Excluir?", confirmLabel: "Excluir", onConfirm }).catch(capturado)
          }
        >
          abrir
        </button>
      );
    }
    render(
      <ConfirmProvider>
        <HarnessComCatch />
      </ConfirmProvider>,
    );

    await userEvent.click(screen.getByText("abrir"));
    await userEvent.click(screen.getByRole("button", { name: /Excluir/ }));
    await waitFor(() => expect(capturado).toHaveBeenCalledWith(erro));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

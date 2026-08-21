import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as React from "react";
import { describe, expect, it, vi } from "vitest";

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

describe("Dialog — foco inicial", () => {
  it("com input no conteúdo, o foco inicial vai para o input, não para Fechar", () => {
    render(
      <Dialog open onClose={() => {}} title="Novo registro">
        <input aria-label="Nome" />
      </Dialog>,
    );
    expect(screen.getByLabelText("Nome")).toHaveFocus();
    expect(screen.getByLabelText("Fechar")).not.toHaveFocus();
  });

  it("elemento com autoFocus mantém o foco (o efeito do Dialog não sobrescreve)", () => {
    render(
      <Dialog open onClose={() => {}} title="Editar">
        <input aria-label="Primeiro" />
        {/* o autoFocus do React foca durante o commit, antes do efeito do Dialog */}
        <input aria-label="Segundo" autoFocus />
      </Dialog>,
    );
    expect(screen.getByLabelText("Segundo")).toHaveFocus();
  });

  it("sem campo no conteúdo, a primeira ação do footer recebe o foco, não Fechar", () => {
    render(
      <Dialog
        open
        onClose={() => {}}
        title="Confirmar"
        footer={
          <>
            <button type="button">Cancelar</button>
            <button type="button">Excluir</button>
          </>
        }
      >
        <div>Esta ação não pode ser desfeita.</div>
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
    expect(screen.getByLabelText("Fechar")).not.toHaveFocus();
  });

  it("dialog contendo somente Fechar foca Fechar como fallback", () => {
    render(
      <Dialog open onClose={() => {}} title="Aviso">
        <div>Conteúdo sem nada focável.</div>
      </Dialog>,
    );
    expect(screen.getByLabelText("Fechar")).toHaveFocus();
  });
});

describe("Dialog — teclado e trap", () => {
  it("Escape chama onClose", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Qualquer">
        <input aria-label="Campo" />
      </Dialog>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Tab no último volta ao primeiro; Shift+Tab no primeiro volta ao último", async () => {
    render(
      <Dialog
        open
        onClose={() => {}}
        title="Form"
        footer={<button type="button">Salvar</button>}
      >
        <input aria-label="Campo" />
      </Dialog>,
    );
    // Ordem no DOM: Fechar (header) → Campo (conteúdo) → Salvar (footer)
    const fechar = screen.getByLabelText("Fechar");
    const salvar = screen.getByRole("button", { name: "Salvar" });

    salvar.focus();
    await userEvent.tab();
    expect(fechar).toHaveFocus();

    await userEvent.tab({ shift: true });
    expect(salvar).toHaveFocus();
  });
});

describe("Dialog — restauração de foco", () => {
  function ParentComTrigger() {
    const [open, setOpen] = React.useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Abrir
        </button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Janela">
          <input aria-label="Dentro" />
        </Dialog>
      </>
    );
  }

  it("ao fechar, o foco volta para o elemento que abriu o dialog", async () => {
    render(<ParentComTrigger />);
    const abrir = screen.getByRole("button", { name: "Abrir" });

    await userEvent.click(abrir);
    expect(screen.getByLabelText("Dentro")).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(abrir).toHaveFocus();
  });

  function ParentComTriggerEAutoFocus() {
    const [open, setOpen] = React.useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Abrir
        </button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Prompt">
          {/* autoFocus foca durante o commit, ANTES do efeito do Dialog —
              se a captura do "elemento anterior" acontecer no efeito, ela
              guarda este input em vez do trigger, e o foco se perde no
              fechamento. É o caso real do prompt do ConfirmProvider. */}
          <input aria-label="Valor" autoFocus />
        </Dialog>
      </>
    );
  }

  it("restaura o trigger mesmo quando um filho tem autoFocus", async () => {
    render(<ParentComTriggerEAutoFocus />);
    const abrir = screen.getByRole("button", { name: "Abrir" });

    await userEvent.click(abrir);
    expect(screen.getByLabelText("Valor")).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(abrir).toHaveFocus();
  });

  it("restaura o trigger com filho autoFocus também sob StrictMode", async () => {
    render(
      <React.StrictMode>
        <ParentComTriggerEAutoFocus />
      </React.StrictMode>,
    );
    const abrir = screen.getByRole("button", { name: "Abrir" });

    await userEvent.click(abrir);
    // Sob StrictMode o efeito monta/desmonta/remonta; o que importa é o
    // comportamento observável: foco dentro do dialog e, ao fechar, de
    // volta ao trigger.
    const dentro = screen.getByLabelText("Valor");
    expect(dentro.ownerDocument.activeElement).toBe(dentro);

    await userEvent.keyboard("{Escape}");
    expect(abrir).toHaveFocus();
  });

  function DoisTriggers() {
    const [open, setOpen] = React.useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Abrir A
        </button>
        <button type="button" onClick={() => setOpen(true)}>
          Abrir B
        </button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Janela">
          <input aria-label="Campo1" />
          <input aria-label="Campo2" />
        </Dialog>
      </>
    );
  }

  it("reabrir por outro trigger captura o NOVO trigger (não reutiliza o anterior)", async () => {
    render(<DoisTriggers />);
    const a = screen.getByRole("button", { name: "Abrir A" });
    const b = screen.getByRole("button", { name: "Abrir B" });

    await userEvent.click(a);
    expect(screen.getByLabelText("Campo1")).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(a).toHaveFocus();

    await userEvent.click(b);
    expect(screen.getByLabelText("Campo1")).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(b).toHaveFocus();
  });

  it("mover o foco entre elementos internos não sobrescreve o destino de retorno", async () => {
    render(<DoisTriggers />);
    const a = screen.getByRole("button", { name: "Abrir A" });

    await userEvent.click(a);
    expect(screen.getByLabelText("Campo1")).toHaveFocus();

    // usuário navega dentro do modal
    await userEvent.click(screen.getByLabelText("Campo2"));
    expect(screen.getByLabelText("Campo2")).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(a).toHaveFocus();
  });

  function TriggerRemovivel() {
    const [open, setOpen] = React.useState(false);
    const [temTrigger, setTemTrigger] = React.useState(true);
    return (
      <>
        {temTrigger && (
          <button type="button" onClick={() => setOpen(true)}>
            Abrir
          </button>
        )}
        <button type="button" onClick={() => setTemTrigger(false)}>
          Remover trigger
        </button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Janela">
          <input aria-label="Campo" />
        </Dialog>
      </>
    );
  }

  it("trigger desmontado enquanto o dialog está aberto: fechar não lança erro", async () => {
    render(<TriggerRemovivel />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(screen.getByLabelText("Campo")).toHaveFocus();

    // o elemento que originou a abertura sai do DOM
    await userEvent.click(screen.getByRole("button", { name: "Remover trigger" }));
    expect(screen.queryByRole("button", { name: "Abrir" })).toBeNull();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull(); // fechou sem exceção
  });
});

describe("Dialog — clique fora vs drag (UX-02 fatia 2.1)", () => {
  function renderComOverlay(onClose: () => void) {
    render(
      <Dialog open onClose={onClose} title="Título">
        <p>conteúdo selecionável</p>
      </Dialog>,
    );
    // o overlay é o ancestral do painel — o elemento que recebe o clique de fora
    return screen.getByRole("dialog").parentElement as HTMLElement;
  }

  it("clique iniciado E terminado no overlay fecha", () => {
    const onClose = vi.fn();
    const overlay = renderComOverlay(onClose);
    fireEvent.mouseDown(overlay);
    fireEvent.mouseUp(overlay);
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("drag que começa DENTRO (selecionar texto) e solta fora NÃO fecha", () => {
    const onClose = vi.fn();
    const overlay = renderComOverlay(onClose);
    const conteudo = screen.getByText("conteúdo selecionável");
    fireEvent.mouseDown(conteudo);
    fireEvent.mouseUp(overlay);
    // navegadores disparam o click no ancestral comum — aqui, o overlay
    fireEvent.click(overlay);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("depois de um drag abortado, um clique normal no overlay volta a fechar", () => {
    const onClose = vi.fn();
    const overlay = renderComOverlay(onClose);
    fireEvent.mouseDown(screen.getByText("conteúdo selecionável"));
    fireEvent.mouseUp(overlay);
    fireEvent.click(overlay);
    fireEvent.mouseDown(overlay);
    fireEvent.mouseUp(overlay);
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Dialog — aria-describedby (UX-02 fatia 2.1)", () => {
  it("com description, o dialog aponta aria-describedby para o texto", () => {
    render(
      <Dialog open onClose={() => {}} title="Excluir anexo" description="Esta ação não pode ser desfeita.">
        <p>corpo</p>
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog");
    const id = dialog.getAttribute("aria-describedby");
    expect(id).toBeTruthy();
    const alvo = document.getElementById(id as string);
    expect(alvo?.textContent).toBe("Esta ação não pode ser desfeita.");
  });

  it("sem description não inventa aria-describedby", () => {
    render(
      <Dialog open onClose={() => {}} title="Título">
        <p>corpo</p>
      </Dialog>,
    );
    expect(screen.getByRole("dialog")).not.toHaveAttribute("aria-describedby");
  });
});

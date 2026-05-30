import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ComplementacaoAbertaCard } from "@/components/ComplementacaoAbertaCard";
import type { ComplementacaoOut } from "@/lib/api";

function comp(overrides: Partial<ComplementacaoOut> = {}): ComplementacaoOut {
  return {
    id: 7,
    status: "aberta",
    mensagem: "Envie o RG e o CPF, por favor.",
    documentos_solicitados: [
      { key: "rg", nome: "RG", descricao: null, enviado: false },
      { key: "cpf", nome: "CPF", descricao: null, enviado: true },
    ],
    id_usuario_solicitante: 1,
    nome_solicitante: "Servidor X",
    criado_em: "2026-05-29T10:00:00",
    atualizado_em: null,
    respondido_em: null,
    cancelado_em: null,
    motivo_cancelamento: null,
    ...overrides,
  };
}

describe("ComplementacaoAbertaCard (PR 4d)", () => {
  it("modo cidadão: mostra mensagem, docs e botão Responder", () => {
    const onResponder = vi.fn();
    const onAnexar = vi.fn();
    render(
      <ComplementacaoAbertaCard
        data={comp()}
        modo="cidadao"
        onResponder={onResponder}
        onAnexar={onAnexar}
      />,
    );
    expect(screen.getByText(/Envie o RG/)).toBeInTheDocument();
    expect(screen.getByText("RG")).toBeInTheDocument();
    expect(screen.getByText("CPF")).toBeInTheDocument();
    // CPF enviado → badge "Enviado"; RG pendente
    expect(screen.getAllByText(/Enviado/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Pendente/).length).toBeGreaterThan(0);
    // Botão de anexar só aparece no item pendente (RG)
    const anexarButtons = screen.getAllByRole("button", { name: /Anexar/i });
    expect(anexarButtons).toHaveLength(1);
    fireEvent.click(anexarButtons[0]);
    expect(onAnexar).toHaveBeenCalledWith("rg", "RG");
    // Responder
    fireEvent.click(screen.getByRole("button", { name: /Responder complementação/i }));
    expect(onResponder).toHaveBeenCalledTimes(1);
  });

  it("modo cidadão: D-RESPOSTA — botão Responder aparece mesmo com nenhum doc enviado", () => {
    const onResponder = vi.fn();
    render(
      <ComplementacaoAbertaCard
        data={comp({
          documentos_solicitados: [
            { key: "rg", nome: "RG", descricao: null, enviado: false },
            { key: "cpf", nome: "CPF", descricao: null, enviado: false },
          ],
        })}
        modo="cidadao"
        onResponder={onResponder}
        onAnexar={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Responder complementação/i }));
    expect(onResponder).toHaveBeenCalled();
  });

  it("modo servidor: mostra botão Cancelar, sem Responder/Anexar", () => {
    const onCancelar = vi.fn();
    render(
      <ComplementacaoAbertaCard
        data={comp()}
        modo="servidor"
        onCancelar={onCancelar}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /Responder/i }),
    ).toBeNull();
    expect(screen.queryByRole("button", { name: /^Anexar$/i })).toBeNull();
    const cancelar = screen.getByRole("button", { name: /Cancelar complementação/i });
    fireEvent.click(cancelar);
    expect(onCancelar).toHaveBeenCalledTimes(1);
  });

  it("status respondida: não mostra ações", () => {
    render(
      <ComplementacaoAbertaCard
        data={comp({ status: "respondida", respondido_em: "2026-05-29T11:00" })}
        modo="cidadao"
        onResponder={vi.fn()}
      />,
    );
    expect(
      screen.queryByRole("button", { name: /Responder/i }),
    ).toBeNull();
    expect(screen.getByText("Respondida")).toBeInTheDocument();
  });

  it("status cancelada: mostra motivo de cancelamento", () => {
    render(
      <ComplementacaoAbertaCard
        data={comp({
          status: "cancelada",
          cancelado_em: "2026-05-29T12:00",
          motivo_cancelamento: "Recebido por outro canal",
        })}
        modo="servidor"
        onCancelar={vi.fn()}
      />,
    );
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
    expect(screen.getByText(/Recebido por outro canal/)).toBeInTheDocument();
    // Cancelar não mais disponível pra cancelada
    expect(
      screen.queryByRole("button", { name: /Cancelar complementação/i }),
    ).toBeNull();
  });
});

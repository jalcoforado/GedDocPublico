import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ComplementacoesHistoricoLista } from "@/components/ComplementacoesHistoricoLista";
import type { ComplementacaoOut } from "@/lib/api";

function mk(id: number, status: "respondida" | "cancelada"): ComplementacaoOut {
  return {
    id,
    status,
    mensagem: `msg ${id}`,
    documentos_solicitados: [],
    id_usuario_solicitante: 1,
    nome_solicitante: `Serv ${id}`,
    criado_em: "2026-05-29T10:00:00",
    atualizado_em: null,
    respondido_em: status === "respondida" ? "2026-05-29T11:00:00" : null,
    cancelado_em: status === "cancelada" ? "2026-05-29T11:00:00" : null,
    motivo_cancelamento: null,
  };
}

describe("ComplementacoesHistoricoLista (PR 4d)", () => {
  it("nada renderiza quando a lista está vazia", () => {
    const { container } = render(<ComplementacoesHistoricoLista data={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("renderiza linhas com badge por status", () => {
    render(
      <ComplementacoesHistoricoLista data={[mk(1, "respondida"), mk(2, "cancelada")]} />,
    );
    expect(screen.getByText("Respondida")).toBeInTheDocument();
    expect(screen.getByText("Cancelada")).toBeInTheDocument();
    expect(screen.getByText(/Serv 1/)).toBeInTheDocument();
    expect(screen.getByText(/Serv 2/)).toBeInTheDocument();
  });
});

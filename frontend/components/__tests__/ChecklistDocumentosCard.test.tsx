import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ChecklistDocumentosCard } from "@/components/ChecklistDocumentosCard";
import type { ChecklistDocumentosResponse } from "@/lib/api";

const ITENS = [
  {
    key: "rg",
    nome: "Documento de identificação",
    obrigatorio: true,
    descricao: "RG ou CNH",
    enviado: false,
    anexos: [],
  },
  {
    key: "cpf",
    nome: "CPF",
    obrigatorio: true,
    descricao: null,
    enviado: true,
    anexos: [{ id_anexo: 10, descricao: "cpf.pdf" }],
  },
  {
    key: "opc",
    nome: "Doc opcional",
    obrigatorio: false,
    descricao: null,
    enviado: false,
    anexos: [],
  },
];

function payload(overrides: Partial<ChecklistDocumentosResponse> = {}): ChecklistDocumentosResponse {
  return {
    id_processo: 1,
    id_servico: 2,
    status_documental: "parcial",
    obrigatorios_total: 2,
    obrigatorios_enviados: 1,
    itens: ITENS,
    complementacao_aberta: null,
    ...overrides,
  };
}

describe("ChecklistDocumentosCard (PR 4c)", () => {
  it("mostra status, contagem e itens (cidadão com onAnexar)", () => {
    const onAnexar = vi.fn();
    render(<ChecklistDocumentosCard data={payload()} onAnexar={onAnexar} />);
    expect(screen.getByText("Parcial")).toBeInTheDocument();
    expect(screen.getByText(/1\/2 obrigatórios enviados/i)).toBeInTheDocument();
    expect(screen.getByText("Documento de identificação")).toBeInTheDocument();
    expect(screen.getByText("CPF")).toBeInTheDocument();
    // CPF está enviado → badge "Enviado"
    expect(screen.getAllByText(/Enviado/i).length).toBeGreaterThan(0);
    // rótulo "opcional" (minúsculas) aparece para itens não-obrigatórios
    expect(screen.getByText(/^opcional$/i)).toBeInTheDocument();
  });

  it("modo cidadão: clicar em Anexar chama onAnexar(key, nome)", () => {
    const onAnexar = vi.fn();
    render(<ChecklistDocumentosCard data={payload()} onAnexar={onAnexar} />);
    // há 3 botões "Anexar" (um por item)
    const buttons = screen.getAllByRole("button", { name: /Anexar/i });
    expect(buttons.length).toBe(3);
    fireEvent.click(buttons[0]);
    expect(onAnexar).toHaveBeenCalledWith("rg", "Documento de identificação");
  });

  it("modo servidor (sem onAnexar): nenhum botão Anexar", () => {
    render(<ChecklistDocumentosCard data={payload()} />);
    expect(screen.queryByRole("button", { name: /Anexar/i })).toBeNull();
  });

  it("sem_documentos_exigidos: mensagem amigável", () => {
    render(
      <ChecklistDocumentosCard
        data={payload({ status_documental: "sem_documentos_exigidos", itens: [], obrigatorios_total: 0, obrigatorios_enviados: 0 })}
      />,
    );
    expect(screen.getByText(/Sem documentos exigidos/i)).toBeInTheDocument();
    expect(screen.getByText(/não tem documentos exigidos/i)).toBeInTheDocument();
  });

  it("loading: spinner sem itens", () => {
    render(<ChecklistDocumentosCard data={undefined} loading />);
    expect(screen.getByText(/Carregando/i)).toBeInTheDocument();
  });
});

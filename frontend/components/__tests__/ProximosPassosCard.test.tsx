import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ProximosPassosCard,
  calcularProximoPasso,
} from "@/components/ProximosPassosCard";
import type {
  ChecklistDocumentosResponse,
  ComplementacaoOut,
} from "@/lib/api";

function checklist(
  overrides: Partial<ChecklistDocumentosResponse> = {},
): ChecklistDocumentosResponse {
  return {
    id_processo: 1,
    id_servico: 2,
    status_documental: "completo",
    obrigatorios_total: 0,
    obrigatorios_enviados: 0,
    itens: [],
    complementacao_aberta: null,
    ...overrides,
  };
}

function complementacao(
  status: ComplementacaoOut["status"] = "aberta",
): ComplementacaoOut {
  return {
    id: 7,
    status,
    mensagem: "Por favor, envie o comprovante de residência.",
    documentos_solicitados: [],
    motivo_cancelamento: null,
    id_usuario_solicitante: 100,
    criado_em: "2026-05-01T10:00:00",
    atualizado_em: null,
    nome_solicitante: "Servidor X",
    respondido_em: null,
    cancelado_em: null,
  };
}

// =============================================================================
// calcularProximoPasso (puro)
// =============================================================================

describe("calcularProximoPasso", () => {
  it("processo encerrado → 'Sua solicitação foi concluída.' (success)", () => {
    const m = calcularProximoPasso({ ativo: false });
    expect(m.intent).toBe("success");
    expect(m.title).toMatch(/concluída/i);
  });

  it("complementação aberta tem prioridade sobre checklist", () => {
    const m = calcularProximoPasso(
      { ativo: true },
      checklist({ status_documental: "pendente" }),
      complementacao("aberta"),
    );
    expect(m.intent).toBe("warning");
    expect(m.title).toMatch(/complementação documental/i);
  });

  it("checklist pendente sem complementação → 'Envie os documentos pendentes…'", () => {
    const m = calcularProximoPasso(
      { ativo: true },
      checklist({
        status_documental: "pendente",
        obrigatorios_total: 3,
        obrigatorios_enviados: 0,
      }),
    );
    expect(m.intent).toBe("info");
    expect(m.title).toMatch(/Envie os documentos pendentes/i);
    expect(m.description).toMatch(/0 de 3/);
  });

  it("checklist parcial → também é 'Envie os documentos pendentes'", () => {
    const m = calcularProximoPasso(
      { ativo: true },
      checklist({ status_documental: "parcial" }),
    );
    expect(m.intent).toBe("info");
    expect(m.title).toMatch(/Envie os documentos pendentes/i);
  });

  it("checklist completo + ativo → fallback 'Acompanhe o andamento'", () => {
    const m = calcularProximoPasso(
      { ativo: true },
      checklist({ status_documental: "completo" }),
    );
    expect(m.intent).toBe("default");
    expect(m.title).toMatch(/Acompanhe o andamento/i);
  });

  it("sem checklist ainda → fallback 'Acompanhe o andamento'", () => {
    const m = calcularProximoPasso({ ativo: true }, undefined, undefined);
    expect(m.intent).toBe("default");
    expect(m.title).toMatch(/Acompanhe o andamento/i);
  });

  it("complementação respondida (não aberta) NÃO entra como ação", () => {
    const m = calcularProximoPasso(
      { ativo: true },
      checklist({ status_documental: "completo" }),
      complementacao("respondida"),
    );
    expect(m.intent).toBe("default");
    expect(m.title).toMatch(/Acompanhe o andamento/i);
  });
});

// =============================================================================
// Linguagem cidadã — termos vetados
// =============================================================================

describe("calcularProximoPasso — linguagem cidadã", () => {
  const todasMensagens = [
    calcularProximoPasso({ ativo: false }),
    calcularProximoPasso({ ativo: true }, undefined, complementacao("aberta")),
    calcularProximoPasso({ ativo: true }, checklist({ status_documental: "pendente" })),
    calcularProximoPasso({ ativo: true }),
  ];

  it("nenhuma mensagem contém 'SLA'", () => {
    for (const m of todasMensagens) {
      expect(`${m.title} ${m.description}`).not.toMatch(/\bSLA\b/i);
    }
  });

  it("nenhuma mensagem contém 'garantia' ou 'garantido'", () => {
    for (const m of todasMensagens) {
      expect(`${m.title} ${m.description}`).not.toMatch(/garantia|garantido/i);
    }
  });

  it("nenhuma mensagem contém 'prazo legal'", () => {
    for (const m of todasMensagens) {
      expect(`${m.title} ${m.description}`).not.toMatch(/prazo legal/i);
    }
  });

  it("nenhuma mensagem contém 'deferido' ou 'indeferido'", () => {
    for (const m of todasMensagens) {
      expect(`${m.title} ${m.description}`).not.toMatch(/deferid[oa]|indeferid[oa]/i);
    }
  });
});

// =============================================================================
// ProximosPassosCard (renderização)
// =============================================================================

describe("ProximosPassosCard (render)", () => {
  it("renderiza title, description e data-testid='proximos-passos'", () => {
    render(<ProximosPassosCard processo={{ ativo: true }} />);
    const region = screen.getByTestId("proximos-passos");
    expect(region).toBeInTheDocument();
    expect(screen.getByText(/Acompanhe o andamento/i)).toBeInTheDocument();
  });

  it("complementação aberta destaca o pedido", () => {
    render(
      <ProximosPassosCard
        processo={{ ativo: true }}
        complementacaoAberta={complementacao("aberta")}
      />,
    );
    expect(
      screen.getByText(/Responda à solicitação de complementação documental/i),
    ).toBeInTheDocument();
  });

  it("processo concluído mostra conclusão", () => {
    render(<ProximosPassosCard processo={{ ativo: false }} />);
    expect(screen.getByText(/foi concluída/i)).toBeInTheDocument();
  });

  it("checklist incompleto pede documentos", () => {
    render(
      <ProximosPassosCard
        processo={{ ativo: true }}
        checklist={checklist({
          status_documental: "parcial",
          obrigatorios_total: 2,
          obrigatorios_enviados: 1,
        })}
      />,
    );
    expect(screen.getByText(/Envie os documentos pendentes/i)).toBeInTheDocument();
    expect(screen.getByText(/1 de 2 documentos obrigatórios/i)).toBeInTheDocument();
  });
});

import { describe, expect, it } from "vitest";

import {
  documentoBadge,
  prazoBadge,
  statusProcessoBadge,
} from "@/lib/badges";
import type {
  ChecklistItem,
  PrazoCidadao,
  PrazoInfo,
} from "@/lib/api";

// =============================================================================
// statusProcessoBadge
// =============================================================================

describe("statusProcessoBadge", () => {
  it("ativo · servidor → 'Em tramitação' (success)", () => {
    expect(statusProcessoBadge({ ativo: true }, "servidor")).toMatchObject({
      intent: "success",
      label: "Em tramitação",
    });
  });
  it("ativo · cidadão → 'Em andamento' (success)", () => {
    expect(statusProcessoBadge({ ativo: true }, "cidadao")).toMatchObject({
      intent: "success",
      label: "Em andamento",
    });
  });
  it("inativo · servidor → 'Encerrado' (info)", () => {
    expect(statusProcessoBadge({ ativo: false }, "servidor")).toMatchObject({
      intent: "info",
      label: "Encerrado",
    });
  });
  it("inativo · cidadão → 'Concluído' (info)", () => {
    expect(statusProcessoBadge({ ativo: false }, "cidadao")).toMatchObject({
      intent: "info",
      label: "Concluído",
    });
  });
});

// =============================================================================
// prazoBadge — servidor (PrazoInfo, 6 status)
// =============================================================================

function p(status: PrazoInfo["status"], extras: Partial<PrazoInfo> = {}): PrazoInfo {
  return {
    status,
    prazo_servico_dias_snapshot: extras.prazo_servico_dias_snapshot ?? 30,
    prazo_previsto_em: extras.prazo_previsto_em ?? null,
    dias_restantes: extras.dias_restantes ?? null,
    dias_atraso: extras.dias_atraso ?? null,
    concluido_em: extras.concluido_em ?? null,
    origem: extras.origem ?? "servico",
  };
}

describe("prazoBadge (servidor)", () => {
  it("sem_prazo → null (omitido)", () => {
    expect(prazoBadge(p("sem_prazo"), "servidor")).toBeNull();
  });
  it("dentro_do_prazo · com dias_restantes → label com (N d.)", () => {
    expect(prazoBadge(p("dentro_do_prazo", { dias_restantes: 12 }), "servidor"))
      .toMatchObject({
        intent: "success",
        label: "Dentro do prazo (12 d.)",
      });
  });
  it("dentro_do_prazo · sem dias_restantes → label sem sufixo", () => {
    expect(prazoBadge(p("dentro_do_prazo", { dias_restantes: null }), "servidor"))
      .toMatchObject({
        intent: "success",
        label: "Dentro do prazo",
      });
  });
  it("vencendo · com dias_restantes → label com (N d.) e warning", () => {
    expect(prazoBadge(p("vencendo", { dias_restantes: 2 }), "servidor"))
      .toMatchObject({
        intent: "warning",
        label: "Vencendo (2 d.)",
      });
  });
  it("atrasado · com dias_atraso → 'Atrasado em N d.' (danger)", () => {
    expect(prazoBadge(p("atrasado", { dias_atraso: 5 }), "servidor"))
      .toMatchObject({
        intent: "danger",
        label: "Atrasado em 5 d.",
      });
  });
  it("concluido_no_prazo → success", () => {
    expect(prazoBadge(p("concluido_no_prazo"), "servidor")).toMatchObject({
      intent: "success",
      label: "Concluído no prazo",
    });
  });
  it("concluido_atrasado → warning", () => {
    expect(prazoBadge(p("concluido_atrasado"), "servidor")).toMatchObject({
      intent: "warning",
      label: "Concluído com atraso",
    });
  });
});

// =============================================================================
// prazoBadge — cidadão (PrazoCidadao, 5 status reduzidos)
// =============================================================================

function pc(status: PrazoCidadao["status"]): PrazoCidadao {
  return { status, prazo_estimado_em: null };
}

describe("prazoBadge (cidadão)", () => {
  it("sem_previsao → null", () => {
    expect(prazoBadge(pc("sem_previsao"), "cidadao")).toBeNull();
  });
  it("concluido → null (omitido — badge 'Concluído' já cobre)", () => {
    expect(prazoBadge(pc("concluido"), "cidadao")).toBeNull();
  });
  it("dentro_da_previsao → info", () => {
    expect(prazoBadge(pc("dentro_da_previsao"), "cidadao")).toMatchObject({
      intent: "info",
      label: "Dentro da previsão",
    });
  });
  it("proximo_do_prazo → warning", () => {
    expect(prazoBadge(pc("proximo_do_prazo"), "cidadao")).toMatchObject({
      intent: "warning",
      label: "Próximo do prazo",
    });
  });
  it("fora_da_previsao → danger", () => {
    expect(prazoBadge(pc("fora_da_previsao"), "cidadao")).toMatchObject({
      intent: "danger",
      label: "Fora da previsão",
    });
  });

  it("NUNCA expõe contagem de dias no modo cidadão (D-CIDADAO)", () => {
    const labels = (
      ["sem_previsao", "concluido", "dentro_da_previsao", "proximo_do_prazo",
       "fora_da_previsao"] as const
    ).map((s) => prazoBadge(pc(s), "cidadao")?.label ?? "");
    for (const label of labels) {
      expect(label).not.toMatch(/\d+\s*d\.?$/i);
      expect(label).not.toMatch(/dias?/i);
    }
  });

  it("linguagem cidadã não contém termos vetados", () => {
    const vetados = [
      "SLA",
      "garantia",
      "garantido",
      "prazo legal",
      "vencimento",
      "deferido",
      "indeferido",
    ];
    const labels = (
      ["sem_previsao", "concluido", "dentro_da_previsao", "proximo_do_prazo",
       "fora_da_previsao"] as const
    ).map((s) => prazoBadge(pc(s), "cidadao")?.label ?? "");
    for (const label of labels) {
      for (const v of vetados) {
        expect(label.toLowerCase()).not.toContain(v.toLowerCase());
      }
    }
  });
});

// =============================================================================
// documentoBadge
// =============================================================================

function ci(
  enviado: boolean,
  obrigatorio: boolean,
): ChecklistItem {
  return {
    key: "k",
    nome: "Doc",
    obrigatorio,
    descricao: null,
    enviado,
    anexos: [],
  };
}

describe("documentoBadge", () => {
  it("enviado → success ('Enviado')", () => {
    expect(documentoBadge(ci(true, true))).toMatchObject({
      intent: "success",
      label: "Enviado",
    });
    expect(documentoBadge(ci(true, false))).toMatchObject({
      intent: "success",
      label: "Enviado",
    });
  });
  it("pendente obrigatório → warning", () => {
    expect(documentoBadge(ci(false, true))).toMatchObject({
      intent: "warning",
      label: "Obrigatório · pendente",
    });
  });
  it("pendente opcional → neutral", () => {
    expect(documentoBadge(ci(false, false))).toMatchObject({
      intent: "neutral",
      label: "Opcional · pendente",
    });
  });
});

/**
 * P8 D3 (Task 6) — painel de workflow. `@/lib/api` mockado: fetch real fica
 * coberto pelos testes HTTP do backend (`test_transporte_p8_workflows.py`);
 * aqui só a renderização — estado atual, "fluxo ainda não iniciado" e a
 * timeline do log.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const getWorkflow = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    transporteWorkflow: {
      getWorkflow: (...args: unknown[]) => getWorkflow(...args),
    },
  },
}));

import { WorkflowTimeline } from "@/components/transporte/WorkflowTimeline";

function renderTimeline(entidadeTipo: "ocorrencia" | "alvara" | "convocacao", entidadeId: number) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <WorkflowTimeline entidadeTipo={entidadeTipo} entidadeId={entidadeId} />
    </QueryClientProvider>,
  );
}

describe("WorkflowTimeline", () => {
  it("mostra o estado atual, dias no estado e SLA", async () => {
    getWorkflow.mockResolvedValue({
      estado_atual: "em_apuracao",
      ativa: true,
      dias_no_estado: 3,
      sla_dias: 5,
      log: [
        {
          estado_de: "registrada",
          estado_para: "em_apuracao",
          transicao_label: "iniciar_apuracao",
          executada_em: "2026-08-10T10:00:00",
          id_usuario: 1,
        },
      ],
    });

    renderTimeline("ocorrencia", 42);

    expect(await screen.findByText("Em Apuracao")).toBeInTheDocument();
    expect(screen.getByText(/3 dias neste estado/)).toBeInTheDocument();
    expect(screen.getByText(/SLA de 5 dias/)).toBeInTheDocument();
    expect(screen.getByText("Iniciar Apuracao")).toBeInTheDocument();
    expect(getWorkflow).toHaveBeenCalledWith("ocorrencia", 42);
  });

  it('mostra "Fluxo ainda não iniciado" quando estado_atual é null', async () => {
    getWorkflow.mockResolvedValue({
      estado_atual: null,
      ativa: null,
      dias_no_estado: null,
      sla_dias: null,
      log: [],
    });

    renderTimeline("convocacao", 7);

    expect(await screen.findByText("Fluxo ainda não iniciado.")).toBeInTheDocument();
  });

  it("mostra mensagem discreta quando a busca falha (não some o painel)", async () => {
    getWorkflow.mockRejectedValue(new Error("500"));

    renderTimeline("alvara", 9);

    await waitFor(() =>
      expect(
        screen.getByText("Não foi possível carregar o fluxo de trabalho no momento."),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Fluxo de trabalho")).toBeInTheDocument();
  });

  it("renderiza a timeline com múltiplas transições em ordem", async () => {
    getWorkflow.mockResolvedValue({
      estado_atual: "deferido",
      ativa: false,
      dias_no_estado: 0,
      sla_dias: null,
      log: [
        {
          estado_de: "convocado",
          estado_para: "em_analise",
          transicao_label: "iniciar_analise",
          executada_em: "2026-08-01T10:00:00",
          id_usuario: 1,
        },
        {
          estado_de: "em_analise",
          estado_para: "deferido",
          transicao_label: "deferir",
          executada_em: "2026-08-05T10:00:00",
          id_usuario: 1,
        },
      ],
    });

    renderTimeline("convocacao", 3);

    await waitFor(() => expect(screen.getByText("Deferido")).toBeInTheDocument());
    const itens = screen.getAllByRole("listitem");
    expect(itens).toHaveLength(2);
    expect(itens[0]).toHaveTextContent("Iniciar Analise");
    expect(itens[1]).toHaveTextContent("Deferir");
  });
});

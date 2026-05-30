/**
 * PR 5a — Dashboard executivo por serviço.
 *
 * Cobre:
 * - regressão: KPIs antigos (Volume/Conclusão/SLA) renderizam com payload
 *   contendo blocos novos zerados;
 * - cards novos (documental + complementação) renderizam quando há dados;
 * - ranking por serviço renderiza linhas, incluindo a linha "legado" em
 *   destaque quando `id_servico === null`;
 * - filtro de serviço dispara nova query com `id_servico`;
 * - toggle "Incluir legado" alterna `incluir_legado` e re-dispara;
 * - 403 mostra mensagem dedicada (D-PERMISSAO);
 * - estado vazio do ranking ("Sem dados no período");
 * - tempo médio nulo renderiza "—".
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/(app)/dashboard/page";
import { ApiError, dashboardApi, servicosApi } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    dashboardApi: { kpis: vi.fn() },
    servicosApi: {
      list: vi.fn(),
      get: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      ativar: vi.fn(),
      desativar: vi.fn(),
    },
  };
});

vi.mock("@/components/UnidadePicker", () => ({
  UnidadePicker: ({
    value,
    onChange,
  }: {
    value: number | null;
    onChange: (v: number | null) => void;
  }) => (
    <select
      data-testid="unidade-picker"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
    >
      <option value="">Todas</option>
      <option value="1">Unidade 1</option>
    </select>
  ),
}));

// Recharts depende de ResizeObserver — stub para JSDOM.
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
// eslint-disable-next-line @typescript-eslint/no-explicit-any
(globalThis as any).ResizeObserver = ResizeObserverMock;

const kpisMock = dashboardApi.kpis as ReturnType<typeof vi.fn>;
const servicosMock = servicosApi.list as ReturnType<typeof vi.fn>;

function basePayload(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    periodo_dias: 30,
    id_unidade: null,
    volume: {
      abertos_periodo: 42,
      ativos_hoje: 17,
      externos_periodo: 5,
      sigilosos_periodo: 2,
    },
    conclusao: {
      arquivados_periodo: 10,
      taxa_conclusao_pct: 23.8,
      tempo_medio_dias: 4.2,
    },
    sla: { pendentes: 1, resolvidos_periodo: 3 },
    comparativo: {
      abertos_anterior: 30,
      externos_anterior: 3,
      sigilosos_anterior: 1,
      arquivados_anterior: 6,
      tempo_medio_dias_anterior: 5.0,
      taxa_conclusao_pct_anterior: 20.0,
      sla_resolvidos_anterior: 2,
    },
    por_tipo: [{ label: "Solicitação", count: 30 }],
    por_assunto: [{ label: "Iluminação", count: 18 }],
    por_unidade: [{ label: "Protocolo", count: 25 }],
    serie_temporal: [{ dia: "2026-05-29T00:00:00", count: 3 }],
    documental: {
      com_id_servico_periodo: 35,
      sem_id_servico_periodo: 7,
      checklist_pendente: 8,
      checklist_parcial: 5,
      checklist_completo: 12,
      sem_documentos_exigidos: 10,
    },
    complementacao: {
      abertas_agora: 4,
      solicitadas_periodo: 12,
      respondidas_periodo: 7,
      canceladas_periodo: 1,
      processos_com_aberta_agora: 3,
      tempo_medio_resposta_dias: 2.4,
    },
    por_servico: [
      {
        id_servico: 100,
        nome: "Serviço A",
        count: 30,
        complementacoes_abertas: 2,
        complementacoes_respondidas_periodo: 5,
        checklist_pendente: 4,
        checklist_parcial: 3,
        checklist_completo: 13,
        sem_documentos_exigidos: 10,
      },
      {
        id_servico: null,
        nome: "(sem serviço)",
        count: 7,
        complementacoes_abertas: 0,
        complementacoes_respondidas_periodo: 0,
        checklist_pendente: 0,
        checklist_parcial: 0,
        checklist_completo: 0,
        sem_documentos_exigidos: 7,
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  servicosMock.mockResolvedValue([
    { id: 100, nome: "Serviço A", slug: "sva", ativo: true },
    { id: 101, nome: "Serviço B", slug: "svb", ativo: true },
  ]);
});

describe("DashboardPage — PR 5a", () => {
  it("regressão: renderiza KPIs antigos sem quebrar com blocos novos", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    expect(await screen.findByText(/Abertos no período/i)).toBeInTheDocument();
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(await screen.findByText(/Ativos agora/i)).toBeInTheDocument();
    expect(await screen.findByText(/Concluídos no período/i)).toBeInTheDocument();
    expect(await screen.findByText(/SLA pendentes/i)).toBeInTheDocument();
  });

  it("renderiza cards documental + complementação com valores corretos", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    const wrapper = await screen.findByTestId("dashboard-pr5a-kpis");
    expect(wrapper).toBeInTheDocument();
    // Checklist pendente=8
    expect(wrapper).toHaveTextContent(/Checklist pendente/i);
    expect(wrapper).toHaveTextContent("8");
    // Complementações abertas=4
    expect(wrapper).toHaveTextContent(/Complementações abertas/i);
    expect(wrapper).toHaveTextContent("4");
    // Tempo médio de resposta=2.4d (pt-BR usa vírgula)
    expect(wrapper).toHaveTextContent(/Tempo médio de resposta/i);
    expect(wrapper).toHaveTextContent(/2,4d/);
  });

  it("ranking por serviço renderiza linhas e destaca o legado", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    const ranking = await screen.findByTestId("dashboard-ranking-servicos");
    expect(ranking).toHaveTextContent("Serviço A");
    // Linha legado tem rótulo "— legado" e marcador específico.
    const legadoRow = await screen.findByTestId("dashboard-ranking-legado");
    expect(legadoRow).toHaveTextContent(/legado/i);
    // Itens normais aparecem com o test-id correto.
    expect(screen.getAllByTestId("dashboard-ranking-item").length).toBeGreaterThan(0);
  });

  it("filtro por serviço dispara nova chamada com id_servico", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    await screen.findByText("42");
    // Aguarda servicosApi popular o select.
    await waitFor(() => expect(servicosMock).toHaveBeenCalled());

    const select = await screen.findByTestId("dashboard-filtro-servico");
    fireEvent.change(select, { target: { value: "100" } });

    await waitFor(() => {
      const calls = kpisMock.mock.calls;
      expect(
        calls.some((c) => (c[0] as { id_servico?: number })?.id_servico === 100),
      ).toBe(true);
    });
  });

  it("toggle incluir_legado alterna o filtro e re-dispara", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    await screen.findByText("42");

    const toggle = (await screen.findByTestId(
      "dashboard-toggle-legado",
    )) as HTMLInputElement;
    expect(toggle.checked).toBe(true); // default
    fireEvent.click(toggle);

    await waitFor(() => {
      const calls = kpisMock.mock.calls;
      expect(
        calls.some(
          (c) => (c[0] as { incluir_legado?: boolean })?.incluir_legado === false,
        ),
      ).toBe(true);
    });
  });

  it("tratamento 403: mostra mensagem dedicada de permissão", async () => {
    kpisMock.mockRejectedValue(new ApiError("Sem permissão", 403));
    renderPage();
    expect(await screen.findByTestId("dashboard-403")).toBeInTheDocument();
    expect(
      screen.getByText(/Sem permissão para o dashboard/i),
    ).toBeInTheDocument();
  });

  it("estado vazio: ranking exibe 'Sem dados no período' quando por_servico=[]", async () => {
    kpisMock.mockResolvedValue(basePayload({ por_servico: [] }));
    renderPage();
    const ranking = await screen.findByTestId("dashboard-ranking-servicos");
    expect(ranking).toHaveTextContent(/Sem dados no período/i);
  });

  it("tempo médio nulo mostra '—'", async () => {
    kpisMock.mockResolvedValue(
      basePayload({
        complementacao: {
          abertas_agora: 0,
          solicitadas_periodo: 0,
          respondidas_periodo: 0,
          canceladas_periodo: 0,
          processos_com_aberta_agora: 0,
          tempo_medio_resposta_dias: null,
        },
      }),
    );
    renderPage();
    const wrapper = await screen.findByTestId("dashboard-pr5a-kpis");
    expect(wrapper).toHaveTextContent("—");
  });

  // PR 5a-fix: novos casos.
  it("card 'Sem documentos exigidos' aparece separado de 'Checklist completo'", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    const wrapper = await screen.findByTestId("dashboard-pr5a-kpis");
    // O card existe.
    expect(wrapper).toHaveTextContent(/Sem documentos exigidos/i);
    // Os números são distintos (12 completo, 10 sem docs).
    expect(wrapper).toHaveTextContent("12");
    expect(wrapper).toHaveTextContent("10");
  });

  it("checkbox 'Incluir legado' fica disabled quando há id_servico", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    await screen.findByText("42");
    await waitFor(() => expect(servicosMock).toHaveBeenCalled());

    // Re-busca o elemento a cada checagem — mudar `idServico` muda a
    // queryKey e o componente passa por loading antes de re-renderizar.
    const initialToggle = (await screen.findByTestId(
      "dashboard-toggle-legado",
    )) as HTMLInputElement;
    expect(initialToggle.disabled).toBe(false);

    const select = await screen.findByTestId("dashboard-filtro-servico");
    fireEvent.change(select, { target: { value: "100" } });

    await waitFor(() => {
      const t = screen.getByTestId(
        "dashboard-toggle-legado",
      ) as HTMLInputElement;
      expect(t.disabled).toBe(true);
    });
  });

  it("URLs de export preservam id_servico e incluir_legado", async () => {
    kpisMock.mockResolvedValue(basePayload());
    renderPage();
    await screen.findByText("42");
    await waitFor(() => expect(servicosMock).toHaveBeenCalled());

    // Estado inicial: incluir_legado=true (default → não vai na querystring),
    // sem id_servico.
    const initialCsv = screen.getByTitle(/Baixar CSV/i) as HTMLAnchorElement;
    expect(initialCsv.href).toMatch(/periodo=30/);
    expect(initialCsv.href).not.toMatch(/incluir_legado=false/);

    // Toggle off ANTES de selecionar serviço (enquanto ainda está habilitado).
    const toggle = (await screen.findByTestId(
      "dashboard-toggle-legado",
    )) as HTMLInputElement;
    fireEvent.click(toggle);
    await waitFor(() => {
      const csv = screen.getByTitle(/Baixar CSV/i) as HTMLAnchorElement;
      expect(csv.href).toMatch(/incluir_legado=false/);
    });

    // Após escolher serviço, URL passa id_servico=100 (e mantém incluir_legado).
    const select = await screen.findByTestId("dashboard-filtro-servico");
    fireEvent.change(select, { target: { value: "100" } });
    await waitFor(() => {
      const csv = screen.getByTitle(/Baixar CSV/i) as HTMLAnchorElement;
      expect(csv.href).toMatch(/id_servico=100/);
    });
  });
});

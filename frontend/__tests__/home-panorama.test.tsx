/**
 * Panorama do Início — os números da prefeitura em movimento (2026-11-10).
 *
 * Protege o que não se vê no olho: cada bloco só aparece com o acesso do
 * módulo, o período troca a consulta, a variação compara com o período
 * anterior, a legenda do fluxo de caixa liga e desliga a série, e as
 * contagens da frota e dos alvarás batem com os dados.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const kpisMock = vi.fn();
const pagMock = vi.fn();
const frotaMock = vi.fn();
const alvarasMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    dashboardApi: { kpis: (p: unknown) => kpisMock(p) },
    api: {
      ...actual.api,
      pagamentos: { ...actual.api.pagamentos, dashboard: () => pagMock() },
      frota: { ...actual.api.frota, listAll: () => frotaMock() },
      alvaras: {
        ...actual.api.alvaras,
        relatorio: { ...actual.api.alvaras.relatorio, kpis: () => alvarasMock() },
      },
    },
  };
});

import { Panorama, type AcessoPanorama } from "@/components/home/Panorama";

const SEM: AcessoPanorama = { protocolo: false, pagamentos: false, frota: false, transporte: false };

function montar(acesso: Partial<AcessoPanorama>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Panorama acesso={{ ...SEM, ...acesso }} />
    </QueryClientProvider>,
  );
}

const kpis = {
  periodo_dias: 30,
  id_unidade: null,
  volume: { abertos_periodo: 12, ativos_hoje: 9, externos_periodo: 0, sigilosos_periodo: 0 },
  conclusao: { arquivados_periodo: 3, taxa_conclusao_pct: 25, tempo_medio_dias: 4 },
  sla: { pendentes: 0, resolvidos_periodo: 0 },
  comparativo: {
    abertos_anterior: 8,
    externos_anterior: 0,
    sigilosos_anterior: 0,
    arquivados_anterior: 3,
    tempo_medio_dias_anterior: null,
    taxa_conclusao_pct_anterior: null,
    sla_resolvidos_anterior: 0,
  },
  por_tipo: [],
  por_assunto: [
    { label: "Poda de árvore", count: 2 },
    { label: "Demanda Cidadã", count: 10 },
  ],
  por_unidade: [],
  serie_temporal: [],
  documental: {},
  complementacao: {},
  por_servico: [],
  prazos: {
    sem_prazo: 4,
    dentro_do_prazo: 3,
    vencendo: 1,
    atrasado: 1,
    concluido_no_prazo_periodo: 0,
    concluido_atrasado_periodo: 0,
    percentual_no_prazo: 60,
    tempo_medio_atraso_dias: null,
  },
};

const pagamentos = {
  kpis: {
    saldo_total: "1000000",
    disponivel_total: "800000",
    comprometido_total: "200000",
    a_pagar_30d: "0",
    vencidas_qtd: 0,
    vencidas_valor: "0",
    pago_no_mes: "27730",
    aguardando_aprovacao_qtd: 0,
    aguardando_autorizacao_qtd: 0,
  },
  fluxo_mensal: [
    { mes: "2026-10", entradas: "100000", saidas: "20000" },
    { mes: "2026-11", entradas: "0", saidas: "27730" },
  ],
  por_natureza: [
    { codigo: "3390.30", descricao: "Material de consumo", valor: "5000" },
    { codigo: "4490.52", descricao: "Equipamentos", valor: "40000" },
  ],
  por_fonte: [],
  maiores_debitos: [],
  alertas: { parcelas_vencidas: [], parcelas_7dias: [], contas_abaixo_minimo: [] },
};

beforeEach(() => {
  kpisMock.mockReset().mockResolvedValue(kpis);
  pagMock.mockReset().mockResolvedValue(pagamentos);
  frotaMock.mockReset().mockResolvedValue([]);
  alvarasMock.mockReset().mockResolvedValue({ total_alvaras: 0, ativos: 0, vencidos: 0, a_renovar_30d: 0, indefinidos: 0 });
});

describe("Panorama do Início", () => {
  it("sem acesso a módulo nenhum, não aparece nem consulta nada", () => {
    const { container } = montar({});
    expect(container).toBeEmptyDOMElement();
    expect(kpisMock).not.toHaveBeenCalled();
    expect(pagMock).not.toHaveBeenCalled();
  });

  it("só com Pagamentos, não mostra os blocos do Protocolo nem o seletor de período", async () => {
    montar({ pagamentos: true });
    expect(await screen.findByRole("region", { name: "Como o dinheiro entrou e saiu?" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Quantos processos entraram?" })).toBeNull();
    expect(screen.queryByRole("radiogroup", { name: "Período do panorama" })).toBeNull();
    expect(kpisMock).not.toHaveBeenCalled();
  });

  it("compara os abertos com o período anterior e o cartão leva ao dashboard", async () => {
    montar({ protocolo: true });
    const cartao = (await screen.findByText("Processos abertos")).closest("a")!;
    await waitFor(() => expect(within(cartao).getByText("12")).toBeInTheDocument());
    // 12 contra 8 no período anterior.
    expect(within(cartao).getByText("+50%")).toBeInTheDocument();
    expect(cartao).toHaveAttribute("href", "/dashboard");
  });

  it("trocar o período refaz a consulta com o novo recorte", async () => {
    montar({ protocolo: true });
    await waitFor(() => expect(kpisMock).toHaveBeenCalledWith(expect.objectContaining({ periodo: 30 })));
    fireEvent.click(screen.getByRole("radio", { name: "7 dias" }));
    await waitFor(() => expect(kpisMock).toHaveBeenCalledWith(expect.objectContaining({ periodo: 7 })));
    expect(screen.getByRole("radio", { name: "7 dias" })).toHaveAttribute("aria-checked", "true");
  });

  it("assuntos e naturezas vêm do maior para o menor", async () => {
    montar({ protocolo: true, pagamentos: true });
    const assuntos = within(await screen.findByRole("region", { name: "Do que tratam os processos?" }));
    await waitFor(() => expect(assuntos.getByText("Demanda Cidadã")).toBeInTheDocument());
    const ordemAssuntos = assuntos.getAllByRole("listitem").map((li) => li.textContent);
    expect(ordemAssuntos[0]).toContain("Demanda Cidadã");

    const naturezas = within(screen.getByRole("region", { name: "Para onde vai o dinheiro?" }));
    await waitFor(() => expect(naturezas.getByText("Equipamentos")).toBeInTheDocument());
    expect(naturezas.getAllByRole("listitem")[0].textContent).toContain("Equipamentos");
  });

  it("a legenda do fluxo de caixa liga e desliga a série", async () => {
    montar({ pagamentos: true });
    const saidas = await screen.findByRole("button", { name: "Saídas" });
    expect(saidas).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(saidas);
    expect(saidas).toHaveAttribute("aria-pressed", "false");
  });

  it("prazos: o anel soma os ativos e a legenda mostra cada fatia", async () => {
    montar({ protocolo: true });
    const prazos = within(await screen.findByRole("region", { name: "Os processos estão no prazo?" }));
    await waitFor(() => expect(prazos.getByText("Atrasados")).toBeInTheDocument());
    // 3 dentro + 1 vencendo + 1 atrasado + 4 sem prazo = 9 ativos.
    expect(prazos.getByText("ativos").previousSibling?.textContent).toBe("9");
  });

  it("frota: conta os veículos por situação", async () => {
    frotaMock.mockResolvedValue([
      { id: 1, situacao: "disponivel" },
      { id: 2, situacao: "disponivel" },
      { id: 3, situacao: "em_uso" },
      { id: 4, situacao: "baixado" },
    ]);
    montar({ frota: true });
    const frota = within(await screen.findByRole("region", { name: "Como está a frota agora?" }));
    await waitFor(() => expect(frota.getByText("4 veículos cadastrados.")).toBeInTheDocument());
    const linha = (rotulo: string) => frota.getByText(rotulo).closest("a, div")!.parentElement!.textContent;
    expect(linha("Disponíveis")).toContain("2");
    expect(linha("Fora de uso")).toContain("1");
  });
});

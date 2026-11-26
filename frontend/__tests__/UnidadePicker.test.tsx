/**
 * "Unidade proprietária" (e todo outro campo de unidade): um campo com busca
 * em vez do botão que só abria o organograma. A busca ignora acento e acha
 * pela sigla; cada opção mostra o caminho na hierarquia; o organograma
 * continua a um clique.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

vi.mock("@xyflow/react", () => ({
  Background: () => null,
  Controls: () => null,
  MarkerType: { ArrowClosed: "arrowclosed" },
  Position: { Top: "top", Bottom: "bottom" },
  ReactFlow: () => <div data-testid="organograma" />,
}));
vi.mock("@xyflow/react/dist/style.css", () => ({}));

const UNIDADES = [
  { id: 1, id_unidade_pai: null, unidade_trabalho: "Prefeitura", sigla: "PREF" },
  { id: 2, id_unidade_pai: 1, unidade_trabalho: "Secretaria de Saúde", sigla: "SMS" },
  { id: 3, id_unidade_pai: 2, unidade_trabalho: "Almoxarifado", sigla: null },
  { id: 4, id_unidade_pai: 1, unidade_trabalho: "Secretaria de Educação", sigla: "SME" },
].map((u) => ({ ...u, processos_ativos: 0, usuarios: 0, sla_pendentes: 0, tempo_medio_dias: null }));

vi.mock("@/lib/api", () => ({
  organogramaApi: { tree: () => Promise.resolve(UNIDADES) },
}));

import { UnidadePicker } from "@/components/UnidadePicker";

function montar(onChange = vi.fn(), value: number | null = null) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <UnidadePicker value={value} onChange={onChange} />
    </QueryClientProvider>,
  );
  return onChange;
}

describe("campo de unidade com busca", () => {
  it("busca sem acento e escolhe pela lista", async () => {
    const onChange = montar();
    const u = userEvent.setup();
    await u.click(screen.getByRole("combobox"));
    await u.type(screen.getByPlaceholderText(/buscar pelo nome ou pela sigla/i), "saude");
    const opcoes = await screen.findAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).toEqual([expect.stringContaining("Secretaria de Saúde")]);
    await u.click(opcoes[0]);
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("acha pela sigla do pai e mostra o caminho na hierarquia", async () => {
    montar();
    const u = userEvent.setup();
    await u.click(screen.getByRole("combobox"));
    await u.type(screen.getByPlaceholderText(/buscar pelo nome ou pela sigla/i), "sms");
    const nomes = (await screen.findAllByRole("option")).map((o) => o.textContent ?? "");
    // A própria SMS e o Almoxarifado, que fica dentro dela.
    expect(nomes.some((t) => t.includes("Almoxarifado") && t.includes("PREF › SMS"))).toBe(true);
  });

  it("mostra o nome da unidade escolhida já na abertura da tela", async () => {
    montar(vi.fn(), 4);
    await waitFor(() =>
      expect(screen.getByRole("combobox")).toHaveTextContent("Secretaria de Educação (SME)"),
    );
  });

  it("o organograma continua disponível", async () => {
    montar();
    const u = userEvent.setup();
    await u.click(screen.getByRole("combobox"));
    await u.click(await screen.findByRole("button", { name: /ver no organograma/i }));
    expect(await screen.findByTestId("organograma")).toBeInTheDocument();
  });
});

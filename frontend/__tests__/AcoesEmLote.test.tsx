/**
 * Seleção de processos e ações em lote numa caixa de trabalho (pedido da
 * reunião de 2026-10-20, item 2.2).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { LoteRequest, LoteResultado, ProcessoListItem } from "@/lib/api";

vi.mock("@/components/FavoritoStar", () => ({ FavoritoStar: () => null }));

const loteMock = vi.fn((_p: LoteRequest): Promise<LoteResultado> =>
  Promise.resolve({ itens: [], concluidos: 0, falhas: 0 }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      // Preguiçosos: o `vi.mock` sobe para antes das declarações acima.
      processos: { ...actual.api.processos, lote: (p: LoteRequest) => loteMock(p) },
      unidades: {
        ...actual.api.unidades,
        list: () => Promise.resolve({ items: [{ id: 9, unidade_trabalho: "Procuradoria" }], total: 1 }),
      },
      prioridades: () => Promise.resolve([{ id: 2, prioridade: "Normal", fator: 1, cor: "" }]),
    },
  };
});

import { AcoesEmLote } from "@/components/AcoesEmLote";
import { TabelaCaixaProcessos } from "@/components/TabelaCaixaProcessos";

function item(id: number): ProcessoListItem {
  return {
    id, numero_processo: `2026/00${id}`, nup: null, numero_origem: null, situacao: "protocolado",
    data_hora_abertura: "2026-10-01T10:00:00", parado_desde: "2026-10-10T10:00:00",
    ativo: true, publico: true, nivel_sigilo: "ostensivo", externo: false, assunto: "Licença",
    tipo_processo: "Pessoal", manifestante: "Fulano", manifestante_cpf_cnpj: null,
    unidade_proprietaria: "RH", local_atual: "RH", id_usuario_responsavel: null,
    responsavel: null, favorito: false, marcadores: [],
  } as ProcessoListItem;
}

const ITENS = [item(1), item(2), item(3)];

/** A caixa como a página monta: tabela com seleção + barra. */
function Caixa({ caixa }: { caixa: "entrada" | "analise" | "saida" }) {
  const [sel, setSel] = useState<Set<number>>(new Set());
  return (
    <>
      <AcoesEmLote
        caixa={caixa}
        selecionados={ITENS.filter((p) => sel.has(p.id))}
        idUsuario={42}
        onConcluido={() => setSel(new Set())}
      />
      <TabelaCaixaProcessos
        itens={ITENS}
        carregando={false}
        selecao={{
          ids: sel,
          alternar: (id) => setSel((a) => {
            const n = new Set(a);
            if (n.has(id)) n.delete(id);
            else n.add(id);
            return n;
          }),
          alternarPagina: (m) => setSel(m ? new Set(ITENS.map((p) => p.id)) : new Set()),
        }}
      />
    </>
  );
}

function abrir(caixa: "entrada" | "analise" | "saida") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Caixa caixa={caixa} />
    </QueryClientProvider>,
  );
}

const barra = () => within(screen.getByRole("toolbar", { name: "Ações em lote" }));

beforeEach(() => loteMock.mockClear());
afterEach(cleanup);

describe("ações em lote", () => {
  it("marcar um a um ou a página inteira conta na barra", () => {
    abrir("entrada");
    expect(barra().getByText("Nenhum processo selecionado")).toBeInTheDocument();
    expect(barra().getByRole("button", { name: "Receber" })).toBeDisabled();

    fireEvent.click(screen.getByRole("checkbox", { name: "Selecionar 2026/002" }));
    expect(barra().getByText("1 selecionado")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Marcar todos desta página" }));
    expect(barra().getByText("3 selecionados")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Desmarcar todos desta página" }));
    expect(barra().getByText("Nenhum processo selecionado")).toBeInTheDocument();
  });

  it("cada caixa oferece só as ações que valem para todos os seus processos", () => {
    abrir("entrada");
    expect(barra().getAllByRole("button").map((b) => b.textContent)).toEqual(["Receber"]);
    cleanup();
    abrir("analise");
    expect(barra().getAllByRole("button").map((b) => b.textContent)).toEqual(
      ["Encaminhar…", "Atribuir a mim", "Arquivar…"]);
  });

  it("receber em lote manda os selecionados e mostra o que falhou, com o número", async () => {
    loteMock.mockResolvedValueOnce({
      itens: [
        { id: 1, ok: true, erro: null },
        { id: 3, ok: false, erro: "Só quem é lotado na unidade de destino (Procuradoria) pode receber este processo." },
      ],
      concluidos: 1, falhas: 1,
    });
    abrir("entrada");
    fireEvent.click(screen.getByRole("checkbox", { name: "Selecionar 2026/001" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Selecionar 2026/003" }));
    fireEvent.click(barra().getByRole("button", { name: "Receber" }));

    await waitFor(() => expect(loteMock).toHaveBeenCalledWith({ acao: "receber", ids: [1, 3] }));
    const status = await screen.findByRole("status");
    expect(status).toHaveTextContent("1 processo concluído, 1 não pôde ser feito:");
    expect(within(status).getByText("2026/003")).toBeInTheDocument();
    expect(status).toHaveTextContent("unidade de destino (Procuradoria)");
    // A seleção zera depois de executar.
    expect(barra().getByText("Nenhum processo selecionado")).toBeInTheDocument();
  });

  it("atribuir a mim manda o usuário logado como responsável", async () => {
    abrir("analise");
    fireEvent.click(screen.getByRole("checkbox", { name: "Selecionar 2026/002" }));
    fireEvent.click(barra().getByRole("button", { name: "Atribuir a mim" }));
    await waitFor(() => expect(loteMock).toHaveBeenCalledWith({
      acao: "atribuir_responsavel", ids: [2], responsavel: { id_usuario: 42 } }));
  });

  it("encaminhar exige destino e prioridade, e manda o mesmo corpo para todos", async () => {
    abrir("analise");
    fireEvent.click(screen.getByRole("checkbox", { name: "Marcar todos desta página" }));
    fireEvent.click(barra().getByRole("button", { name: "Encaminhar…" }));

    const confirmar = await screen.findByRole("button", { name: "Confirmar encaminhamento" });
    expect(confirmar).toBeDisabled();
    await screen.findByRole("option", { name: "Procuradoria" });
    fireEvent.change(screen.getByLabelText("Unidade de destino"), { target: { value: "9" } });
    await screen.findByRole("option", { name: "Normal" });
    fireEvent.change(screen.getByLabelText("Prioridade"), { target: { value: "2" } });
    fireEvent.click(confirmar);

    await waitFor(() => expect(loteMock).toHaveBeenCalledWith({
      acao: "encaminhar", ids: [1, 2, 3],
      encaminhar: { id_unidade_destino: 9, id_prioridade: 2, data_prazo: null, despacho: null },
    }));
  });

  it("arquivar exige motivo", async () => {
    abrir("analise");
    fireEvent.click(screen.getByRole("checkbox", { name: "Selecionar 2026/001" }));
    fireEvent.click(barra().getByRole("button", { name: "Arquivar…" }));
    const confirmar = await screen.findByRole("button", { name: "Confirmar arquivamento" });
    fireEvent.change(screen.getByLabelText("Motivo do arquivamento"), { target: { value: "ok" } });
    expect(confirmar).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Motivo do arquivamento"), {
      target: { value: "Demanda atendida" } });
    fireEvent.click(confirmar);
    await waitFor(() => expect(loteMock).toHaveBeenCalledWith({
      acao: "arquivar", ids: [1], arquivar: { motivo: "Demanda atendida" } }));
  });

  it("caixa sem ação comum não mostra a barra", () => {
    abrir("saida");
    expect(screen.queryByRole("toolbar", { name: "Ações em lote" })).toBeNull();
  });
});

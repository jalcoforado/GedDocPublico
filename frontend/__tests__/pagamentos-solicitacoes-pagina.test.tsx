/**
 * Solicitações de pagamento: a listagem é paginada no SERVIDOR.
 *
 * A tela baixava a base inteira e buscava, cortava e contava no navegador. O
 * que se trava aqui é que cada controle da tela vira um pedido ao servidor —
 * e que a tela não volta a filtrar por conta própria o que recebeu.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SITUACOES_POR_ETAPA, getEtapaIndex } from "@/components/pagamentos/statusFluxo";
import type { SituacaoTramitacao } from "@/lib/api";

const debito = (id: number, situacao: string, descricao = "Compra de material") => ({
  id, id_fornecedor: 1, nome_fornecedor: "Fornecedor X", id_natureza: 1, id_fonte_recursos: 1,
  id_conta: null, id_conta_pagadora: null, id_contrato: null, valor_total: "100.00",
  competencia: "2026-10", numero_ne: null, numero_nf: null, criticidade: "MEDIA", urgente: false,
  justificativa_urgencia: null, descricao, situacao_tramitacao: situacao,
  situacao_fila: "NAO_REGISTRADA", situacao_pagamento: "NAO_INICIADA", id_unidade: 1, versao: 1,
  lock_version: 0, id_gestor_decisor: null, id_validador: null, id_usuario_solicitante: 1,
  liquidacao_confirmada: false, data_liquidacao: null, criado_em: "2026-10-01T10:00:00Z",
  atualizado_em: null,
});

let resposta = { items: [debito(9, "RASCUNHO")], total: 60, page: 1, page_size: 25 };
const paginaMock = vi.fn((_p?: Record<string, unknown>) => Promise.resolve(resposta));
const contagemMock = vi.fn((_q?: string) =>
  Promise.resolve({ RASCUNHO: 40, AGUARDANDO_GESTOR: 12, AJUSTE_GESTOR: 3, AUTORIZADA: 5 }),
);
const listMock = vi.fn(() => Promise.resolve([]));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      pagamentos: {
        ...actual.api.pagamentos,
        debitos: {
          ...actual.api.pagamentos.debitos,
          pagina: paginaMock, contagemPorSituacao: contagemMock, list: listMock,
        },
      },
    },
  };
});

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Auditor", is_super_usuario: false },
    perms: ["pagamento_auditar"], loading: false,
    can: (c: string) => c === "pagamento_auditar",
  }),
}));

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/pagamentos/solicitacoes/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
  await screen.findByText("#9");
}
const ultima = () => paginaMock.mock.calls.at(-1)?.[0] as Record<string, unknown>;

beforeEach(() => {
  resposta = { items: [debito(9, "RASCUNHO")], total: 60, page: 1, page_size: 25 };
  paginaMock.mockClear();
  contagemMock.mockClear();
  listMock.mockClear();
});

describe("solicitações — paginação no servidor", () => {
  it("pede UMA página ao servidor e não baixa a listagem inteira", async () => {
    await abrir();
    expect(ultima()).toEqual({
      situacao_tramitacao: undefined, q: undefined, page: 1, page_size: 25,
    });
    expect(listMock).not.toHaveBeenCalled();
    // O total é o do servidor, não o número de linhas na tela.
    expect(screen.getByText("60 solicitações")).toBeInTheDocument();
    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
  });

  it("os cartões somam a contagem do servidor por etapa", async () => {
    await abrir();
    const cartao = (nome: string) =>
      within(screen.getByRole("button", { name: new RegExp(`^${nome}`) }));
    await waitFor(() => expect(cartao("Rascunho").getByText("40")).toBeInTheDocument());
    // Gestor = aguardando (12) + em ajuste (3).
    expect(cartao("Gestor").getByText("15")).toBeInTheDocument();
    expect(cartao("Validação").getByText("0")).toBeInTheDocument();
    expect(cartao("Concluído").getByText("5")).toBeInTheDocument();
  });

  it("avançar a página pede a próxima ao servidor", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
    await waitFor(() => expect(ultima().page).toBe(2));
  });

  it("clicar numa etapa manda as situações dela e volta para a página 1", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Próxima página" }));
    await waitFor(() => expect(ultima().page).toBe(2));
    fireEvent.click(screen.getByRole("button", { name: /^Gestor/ }));
    await waitFor(() =>
      expect(ultima()).toMatchObject({
        situacao_tramitacao: ["AGUARDANDO_GESTOR", "AJUSTE_GESTOR", "REJEITADA_GESTOR"],
        page: 1,
      }),
    );
  });

  it("escolher uma situação no seletor substitui o filtro de etapa", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: /^Gestor/ }));
    fireEvent.change(screen.getByLabelText("Situação"), { target: { value: "AUTORIZADA" } });
    await waitFor(() => expect(ultima().situacao_tramitacao).toEqual(["AUTORIZADA"]));
    expect(screen.getByRole("button", { name: /^Gestor/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("a busca vai ao servidor, na página e na contagem", async () => {
    await abrir();
    fireEvent.change(screen.getByLabelText("Pesquisar solicitações"), {
      target: { value: "  telhado " },
    });
    await waitFor(() => expect(ultima()).toMatchObject({ q: "telhado", page: 1 }));
    await waitFor(() => expect(contagemMock).toHaveBeenLastCalledWith("telhado"));
  });

  it("mostra o que o servidor devolveu, sem refiltrar no navegador", async () => {
    // O servidor casou pelo nome do fornecedor; a descrição não contém o termo.
    resposta = { items: [debito(9, "RASCUNHO", "Outra coisa")], total: 1, page: 1, page_size: 25 };
    await abrir();
    fireEvent.change(screen.getByLabelText("Pesquisar solicitações"), {
      target: { value: "telhado" },
    });
    await waitFor(() => expect(ultima().q).toBe("telhado"));
    expect(await screen.findByText("Outra coisa")).toBeInTheDocument();
    expect(screen.getByText("1 solicitação")).toBeInTheDocument();
  });
});

describe("etapas × situações", () => {
  it("SITUACOES_POR_ETAPA é o inverso de getEtapaIndex, sem situação repetida", () => {
    const vistas = new Set<SituacaoTramitacao>();
    SITUACOES_POR_ETAPA.forEach((situacoes, idx) => {
      for (const s of situacoes) {
        expect(getEtapaIndex(s), s).toBe(idx);
        expect(vistas.has(s), `${s} repetida`).toBe(false);
        vistas.add(s);
      }
    });
    // Toda situação que a tela oferece no seletor pertence a alguma etapa.
    expect(vistas.size).toBe(11);
  });
});

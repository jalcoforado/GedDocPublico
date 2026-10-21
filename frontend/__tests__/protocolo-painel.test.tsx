/**
 * "Painel de controle" do protocolo (pedido da reunião de 2026-10-20,
 * referência: Painel de Controle do SEI), em `/m/protocolo/painel`. Morou na
 * tela inicial até a decisão de 2026-10-21 de trazê-lo para o módulo; estes
 * testes vieram junto. Cada quadro mostra o número da unidade e leva à lista
 * que o conta.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import type { LotacaoOut, PainelUnidade } from "@/lib/api";

/** `perms` aceita "processo" (ler) e "processo:inserir" (abrir). */
const estado: { perms: string[]; lotacoes: LotacaoOut[]; unidadeContexto: number | null } = {
  perms: [],
  lotacoes: [],
  unidadeContexto: null,
};

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: 77,
      nome: "Maria Souza",
      id_unidade_trabalho: 3,
      unidade_contexto_id: estado.unidadeContexto,
      lotacoes: estado.lotacoes,
    },
    perms: { is_super_usuario: false },
    loading: false,
    can: (codigo: string, action?: string) =>
      estado.perms.includes(action ? `${codigo}:${action}` : codigo),
  }),
}));

let painel: PainelUnidade;
const painelMock = vi.fn(() => Promise.resolve(painel));
const notifMock = vi.fn(() => Promise.resolve({ items: [], nao_lidas: 4 }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    // Preguiçosos: o `vi.mock` sobe para antes das declarações acima.
    api: { ...actual.api, processos: { ...actual.api.processos, painel: () => painelMock() } },
    notificacoesApi: { ...actual.notificacoesApi, listarMinhas: () => notifMock() },
  };
});

function painelBase(): PainelUnidade {
  return {
    caixas: {
      entrada: 3, saida: 2, analise: 12, externos: 1, aguardando_assinatura: 5,
      enviado_para_assinatura: 1, arquivados: 40, recusados: 2,
    },
    atribuidos_a_mim: 4,
    sem_responsavel: 6,
    prazos: { vencidos: 2, vencendo: 3, no_prazo: 5, sem_prazo: 2 },
    aguardando_retorno: { total: 2, atrasados: 1 },
  };
}

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/protocolo/painel/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      {/* O `useLotacaoAtiva` (nome da unidade no subtítulo) pede o toast. */}
      <ToastProvider>
        <Pagina />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** O link do quadro que tem aquele rótulo. */
const quadro = (rotulo: string) => screen.getByText(rotulo).closest("a") as HTMLAnchorElement;
/** O quadro inteiro, seja link ou não (o de Notificações não é). */
const caixaDo = (rotulo: string) =>
  screen.getByText(rotulo).closest("[data-quadro]") as HTMLElement;
const valorDo = (rotulo: string) =>
  within(caixaDo(rotulo)).getByTestId("kpi-valor").textContent;

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = ["processo"];
  estado.lotacoes = [];
  estado.unidadeContexto = null;
  painel = painelBase();
  painelMock.mockClear();
  notifMock.mockClear();
  window.localStorage.clear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.useRealTimers();
});

const CHAVE = "aprimora:painel-quadros:77";
/** Rótulos dos quadros, na ordem em que aparecem. */
const rotulosVisiveis = () =>
  Array.from(
    screen.getByRole("region", { name: "Quadros de processos" }).querySelectorAll("[data-quadro]"),
  ).map((q) => q.firstElementChild?.querySelector("span")?.textContent);

describe("painel de controle", () => {
  it("cada quadro mostra o número da unidade e leva à lista que o conta", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));

    expect(valorDo("A receber")).toBe("3");
    expect(valorDo("Enviados")).toBe("2");
    expect(valorDo("Recusados")).toBe("2");
    expect(valorDo("Atribuídos a mim")).toBe("4");
    expect(valorDo("Sem responsável")).toBe("6");
    expect(valorDo("Para assinar")).toBe("5");
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));

    expect(quadro("A receber")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=entrada&ativos=0");
    expect(quadro("Recusados")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=recusados&ativos=0");
    expect(quadro("Atribuídos a mim")).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=analise&escopo=meus&ativos=0");
    expect(quadro("Para assinar")).toHaveAttribute("href", "/para-assinar");
    // Notificações não é link: levava a /perfil, que não lista nenhuma. A
    // explicação aponta o sino, onde a lista está.
    expect(quadro("Notificações")).toBeNull();
    expect(caixaDo("Notificações").querySelector("[title]")?.getAttribute("title")).toMatch(/sino/);
  });

  it("recusados ficam em destaque quando há algum, e quietos quando não há", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Recusados")).toBe("2"));
    expect(quadro("Recusados").innerHTML).toContain("border-l-danger");

    cleanup();
    painel = { ...painelBase(), caixas: { ...painelBase().caixas, recusados: 0 } };
    await abrir();
    await waitFor(() => expect(valorDo("Recusados")).toBe("0"));
    expect(quadro("Recusados").innerHTML).not.toContain("border-l-danger");
  });

  it("as tabelas de prazo, retorno e assinatura trazem os números do painel", async () => {
    await abrir();
    const prazos = within(await screen.findByRole("region", { name: "Controle de prazos" }));
    expect(prazos.getByRole("row", { name: /Prazo vencido 2/ })).toBeInTheDocument();
    expect(prazos.getByRole("row", { name: /Vencendo 3/ })).toBeInTheDocument();
    expect(prazos.getByRole("row", { name: /No prazo 5/ })).toBeInTheDocument();

    const retorno = within(
      screen.getByRole("region", { name: "Aguardando retorno de outras unidades" }));
    expect(retorno.getByRole("row", { name: /Prazo vencido 1/ })).toBeInTheDocument();
    expect(retorno.getByRole("row", { name: /Total enviado 2/ })).toBeInTheDocument();

    const assinaturas = within(screen.getByRole("region", { name: "Assinaturas" }));
    expect(assinaturas.getByRole("link", { name: "5" })).toHaveAttribute("href", "/para-assinar");
  });

  it("sem nenhum prazo na unidade, diz isso em vez de três zeros", async () => {
    painel = { ...painelBase(), prazos: { vencidos: 0, vencendo: 0, no_prazo: 0, sem_prazo: 12 } };
    await abrir();
    const prazos = within(await screen.findByRole("region", { name: "Controle de prazos" }));
    expect(prazos.getByText("Nenhum processo com prazo na unidade.")).toBeInTheDocument();
    expect(prazos.queryByText("Vencendo")).toBeNull();
  });

  it("quem não opera processos vê só as notificações, e o painel não é pedido", async () => {
    estado.perms = [];
    await abrir();
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));
    expect(screen.queryByText("Na unidade")).toBeNull();
    expect(screen.queryByRole("region", { name: "Controle de prazos" })).toBeNull();
    expect(painelMock).not.toHaveBeenCalled();
  });

  it("falha ao carregar o painel avisa e oferece tentar de novo", async () => {
    painelMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Não foi possível carregar os números da unidade.");
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });
});

describe("painel de controle — mais perto do SEI", () => {
  it("barra de proporção só nas partes de “Na unidade”, com o “x de y” por extenso", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));

    expect(within(quadro("Atribuídos a mim")).getByText("4 de 12 na unidade")).toBeInTheDocument();
    expect(within(quadro("Sem responsável")).getByText("6 de 12 na unidade")).toBeInTheDocument();
    const barras = screen.getAllByTestId("proporcao");
    expect(barras).toHaveLength(2);
    // A parte visual é decorativa; o texto é que fala.
    expect(barras[0].querySelector("[aria-hidden='true']")).not.toBeNull();
    expect(within(quadro("A receber")).queryByTestId("proporcao")).toBeNull();
  });

  it("sem processo na unidade não há base, e a barra não aparece", async () => {
    painel = { ...painelBase(), caixas: { ...painelBase().caixas, analise: 0 } };
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("0"));
    expect(screen.queryByTestId("proporcao")).toBeNull();
  });

  it("cada quadro explica o que conta, no title e para o leitor de tela", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    const link = quadro("A receber");
    expect(link.getAttribute("title")).toMatch(/ninguém da sua unidade recebeu/);
    expect(link).toHaveAccessibleDescription(link.getAttribute("title") as string);
  });

  it("configurar esconde e reordena quadros, e guarda a escolha por usuário", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(rotulosVisiveis()[0]).toBe("Na unidade");

    fireEvent.click(screen.getByRole("button", { name: "Configurar" }));
    const dialogo = within(screen.getByRole("dialog", { name: "Configurar quadros" }));
    fireEvent.click(dialogo.getByLabelText("Enviados"));
    fireEvent.click(dialogo.getByRole("button", { name: "Subir A receber" }));
    fireEvent.click(dialogo.getByRole("button", { name: "Salvar" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByText("Enviados")).toBeNull();
    expect(rotulosVisiveis().slice(0, 2)).toEqual(["A receber", "Na unidade"]);

    const salvo = JSON.parse(window.localStorage.getItem(CHAVE) as string);
    expect(salvo.ocultos).toEqual(["saida"]);
    expect(salvo.ordem.slice(0, 2)).toEqual(["entrada", "analise"]);

    // Reabrir a tela lê a escolha de volta.
    cleanup();
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(screen.queryByText("Enviados")).toBeNull();
    expect(rotulosVisiveis()[0]).toBe("A receber");
  });

  it("restaurar padrão volta todos os quadros na ordem original", async () => {
    window.localStorage.setItem(CHAVE, JSON.stringify({ ordem: ["notificacoes"], ocultos: ["analise"] }));
    await abrir();
    await waitFor(() => expect(rotulosVisiveis()[0]).toBe("Notificações"));
    expect(screen.queryByText("Na unidade")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Configurar" }));
    const dialogo = within(screen.getByRole("dialog"));
    fireEvent.click(dialogo.getByRole("button", { name: "Restaurar padrão" }));
    fireEvent.click(dialogo.getByRole("button", { name: "Salvar" }));

    expect(rotulosVisiveis()).toEqual([
      "Na unidade", "A receber", "Enviados", "Recusados",
      "Atribuídos a mim", "Sem responsável", "Para assinar", "Notificações",
    ]);
  });

  it("id de quadro desconhecido é ignorado e quadro novo entra no fim", async () => {
    window.localStorage.setItem(
      CHAVE,
      JSON.stringify({ ordem: ["quadro_que_saiu", "recusados", "analise"], ocultos: ["outro_que_saiu"] }),
    );
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    const rotulos = rotulosVisiveis();
    expect(rotulos.slice(0, 2)).toEqual(["Recusados", "Na unidade"]);
    expect(rotulos).toHaveLength(8);
  });

  it("armazenamento quebrado ou lixo não derrubam a tela", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(rotulosVisiveis()).toHaveLength(8);

    // Salvar sem armazenamento ainda muda a tela, só não sobrevive ao recarregar.
    fireEvent.click(screen.getByRole("button", { name: "Configurar" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByLabelText("Recusados"));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Salvar" }));
    expect(screen.queryByText("Recusados")).toBeNull();

    vi.restoreAllMocks();
    cleanup();
    window.localStorage.setItem(CHAVE, "{isto não é json");
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(rotulosVisiveis()).toHaveLength(8);
  });

  it("diz há quanto tempo atualizou, e se atualiza sozinho", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(screen.getByTestId("atualizado-ha")).toHaveTextContent("Atualizado agora");

    await act(async () => {
      vi.advanceTimersByTime(90_000);
    });
    expect(screen.getByTestId("atualizado-ha")).toHaveTextContent("Atualizado há 1 min");
    expect(painelMock).toHaveBeenCalledTimes(1);

    // Aos 2 minutos o painel e as notificações são pedidos de novo.
    await act(async () => {
      vi.advanceTimersByTime(40_000);
    });
    await waitFor(() => expect(painelMock).toHaveBeenCalledTimes(2));
    expect(notifMock.mock.calls.length).toBeGreaterThanOrEqual(2);
    await waitFor(() =>
      expect(screen.getByTestId("atualizado-ha")).toHaveTextContent("Atualizado agora"));
  });

  it("painel em erro e notificações em dia não dizem “Atualizado agora”", async () => {
    painelMock.mockRejectedValue(new Error("fora do ar"));
    await abrir();
    await screen.findByRole("alert");
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));
    expect(screen.queryByTestId("atualizado-ha")).toBeNull();
    expect(screen.queryByText(/Atualizado agora/)).toBeNull();
  });

  it("a renovação do painel que falha esconde o rótulo, mesmo com as notificações renovadas", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    expect(screen.getByTestId("atualizado-ha")).toHaveTextContent("Atualizado agora");

    painelMock.mockRejectedValue(new Error("fora do ar"));
    await act(async () => {
      vi.advanceTimersByTime(130_000);
    });
    await screen.findByRole("alert");
    expect(notifMock.mock.calls.length).toBeGreaterThanOrEqual(2);
    // Os quadros ainda mostram o número velho; o rótulo não pode avalizá-lo.
    expect(valorDo("Na unidade")).toBe("12");
    expect(screen.queryByTestId("atualizado-ha")).toBeNull();
  });

  it("quem não opera processos vê o horário das notificações", async () => {
    estado.perms = [];
    await abrir();
    await waitFor(() => expect(valorDo("Notificações")).toBe("4"));
    expect(screen.getByTestId("atualizado-ha")).toHaveTextContent("Atualizado agora");
  });

  it("reordenar pelo teclado não perde o foco e anuncia a nova posição", async () => {
    await abrir();
    await waitFor(() => expect(valorDo("Na unidade")).toBe("12"));
    fireEvent.click(screen.getByRole("button", { name: "Configurar" }));
    const dialogo = within(screen.getByRole("dialog", { name: "Configurar quadros" }));

    // Descer: o <li> do próprio quadro muda de lugar no DOM.
    const descer = dialogo.getByRole("button", { name: "Descer Na unidade" });
    descer.focus();
    fireEvent.click(descer);
    await waitFor(() =>
      expect(document.activeElement).toBe(dialogo.getByRole("button", { name: "Descer Na unidade" })));
    expect(screen.getByTestId("anuncio-posicao")).toHaveTextContent(
      "Na unidade na posição 2 de 8");

    // Subir até o topo: a seta fica inativa e o foco vai para a oposta.
    const subir = dialogo.getByRole("button", { name: "Subir Na unidade" });
    subir.focus();
    fireEvent.click(subir);
    await waitFor(() =>
      expect(document.activeElement).toBe(dialogo.getByRole("button", { name: "Descer Na unidade" })));
    expect(dialogo.getByRole("button", { name: "Subir Na unidade" })).toBeDisabled();
    expect(screen.getByTestId("anuncio-posicao")).toHaveTextContent(
      "Na unidade na posição 1 de 8");

    // Descer até o fim: o foco vai para "Subir".
    const ultimo = dialogo.getByRole("button", { name: "Descer Para assinar" });
    ultimo.focus();
    fireEvent.click(ultimo);
    await waitFor(() =>
      expect(document.activeElement).toBe(dialogo.getByRole("button", { name: "Subir Para assinar" })));
    expect(dialogo.getByRole("button", { name: "Descer Para assinar" })).toBeDisabled();
  });

  it("primeiro uso: unidade sem processo nenhum convida a abrir o primeiro", async () => {
    estado.perms = ["processo", "processo:inserir"];
    painel = {
      ...painelBase(),
      caixas: {
        entrada: 0, saida: 0, analise: 0, externos: 0, aguardando_assinatura: 2,
        enviado_para_assinatura: 0, arquivados: 0, recusados: 0,
      },
    };
    await abrir();
    const aviso = within(await screen.findByRole("region", { name: "Primeiros passos" }));
    expect(aviso.getByRole("link", { name: /Abrir o primeiro processo/ })).toHaveAttribute(
      "href", "/m/protocolo/processos/novo");
    expect(aviso.getByRole("link", { name: /Ver o caminho do processo/ })).toHaveAttribute(
      "href", "/m/protocolo/fluxo");
  });

  it("primeiro uso: quem não pode inserir processo não recebe o link de abrir", async () => {
    painel = {
      ...painelBase(),
      caixas: {
        entrada: 0, saida: 0, analise: 0, externos: 0, aguardando_assinatura: 0,
        enviado_para_assinatura: 0, arquivados: 0, recusados: 0,
      },
    };
    await abrir();
    const aviso = within(await screen.findByRole("region", { name: "Primeiros passos" }));
    expect(aviso.queryByRole("link", { name: /Abrir o primeiro processo/ })).toBeNull();
    expect(aviso.getByRole("link", { name: /Ver o caminho do processo/ })).toBeInTheDocument();
  });

  it("primeiro uso não aparece quando a unidade tem algum processo, nem arquivado", async () => {
    estado.perms = ["processo", "processo:inserir"];
    painel = {
      ...painelBase(),
      caixas: {
        entrada: 0, saida: 0, analise: 0, externos: 0, aguardando_assinatura: 0,
        enviado_para_assinatura: 0, arquivados: 1, recusados: 0,
      },
    };
    await abrir();
    await screen.findByRole("region", { name: "Controle de prazos" });
    expect(screen.queryByRole("region", { name: "Primeiros passos" })).toBeNull();
  });

  it("o subtítulo nomeia a unidade ATIVA, que é a dos números", async () => {
    estado.lotacoes = [
      { id: 3, nome: "Secretaria de Administração", principal: true },
      { id: 9, nome: "Secretaria de Saúde", principal: false },
    ];
    // Com outra lotação ativa, o painel conta por ela — e é ela que se nomeia.
    estado.unidadeContexto = 9;
    await abrir();
    expect(await screen.findByText(/números da unidade Secretaria de Saúde/)).toBeInTheDocument();
    expect(screen.queryByText(/Secretaria de Administração/)).toBeNull();
  });

  it("sem lotação ativa escolhida, nomeia a principal", async () => {
    estado.lotacoes = [
      { id: 3, nome: "Secretaria de Administração", principal: true },
      { id: 9, nome: "Secretaria de Saúde", principal: false },
    ];
    await abrir();
    expect(
      await screen.findByText(/números da unidade Secretaria de Administração/),
    ).toBeInTheDocument();
  });

  it("ativa que deixou de ser lotação do usuário cai na principal, como no cabeçalho", async () => {
    estado.lotacoes = [{ id: 3, nome: "Secretaria de Administração", principal: true }];
    estado.unidadeContexto = 9;
    await abrir();
    expect(
      await screen.findByText(/números da unidade Secretaria de Administração/),
    ).toBeInTheDocument();
  });

  it("o título vem do cabeçalho padrão das telas, e nomeia a aba", async () => {
    await abrir();
    expect(screen.getByRole("heading", { level: 1, name: "Painel de controle" })).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Painel de controle — Aprimora"));
  });

  it("sem o nome da unidade, mantém o texto genérico", async () => {
    await abrir();
    expect(await screen.findByText(/os números são da sua unidade/)).toBeInTheDocument();
  });
});

/**
 * Início (`/home`) — a tela que atravessa os módulos.
 *
 * Até 2026-11-05 ela redirecionava quem opera processos para o painel do
 * Protocolo, e "Início" virou um segundo link para "Painel de controle". Hoje
 * ela fica: um cartão por módulo contratado que a pessoa alcança, cada número
 * levando à lista que o conta; notificações; e os processos acompanhados.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const estado: { perms: string[]; su: boolean } = { perms: [], su: false };
const replace = vi.fn();
const notifMock = vi.fn();
const modulosMock = vi.fn();
const marcarLidaMock = vi.fn();
const marcarTodasMock = vi.fn();
const painelMock = vi.fn();
const listMock = vi.fn();
const dashboardMock = vi.fn();
const solicitacoesMock = vi.fn();
const alvarasKpisMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/home",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { id: 5, nome: "João Lima" },
    perms: { is_super_usuario: estado.su },
    loading: false,
    // Como o `can` real: super-usuário responde `true` a qualquer código.
    can: (codigo: string, action?: string) =>
      estado.su || estado.perms.includes(action ? `${codigo}:${action}` : codigo),
  }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      modulos: () => modulosMock(),
      processos: { ...actual.api.processos, painel: () => painelMock(), list: (f: unknown) => listMock(f) },
      pagamentos: { ...actual.api.pagamentos, dashboard: () => dashboardMock() },
      solicitacoes: { ...actual.api.solicitacoes, listAll: () => solicitacoesMock() },
      alvaras: {
        ...actual.api.alvaras,
        relatorio: { ...actual.api.alvaras.relatorio, kpis: () => alvarasKpisMock() },
      },
    },
    notificacoesApi: {
      ...actual.notificacoesApi,
      listarMinhas: () => notifMock(),
      marcarLida: (id: number) => marcarLidaMock(id),
      marcarTodasLidas: () => marcarTodasMock(),
    },
  };
});

vi.setConfig({ testTimeout: 20_000 });

const modulo = (slug: string) => ({ slug, nome: slug, descricao: null, ordem: 1 });

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/home/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
}

const cartao = async (nome: string) => within(await screen.findByRole("region", { name: nome }));

beforeEach(() => {
  estado.perms = [];
  estado.su = false;
  replace.mockClear();
  modulosMock.mockReset();
  modulosMock.mockResolvedValue({ itens: [modulo("protocolo"), modulo("frota")] });
  painelMock.mockReset();
  painelMock.mockResolvedValue({
    caixas: {
      entrada: 3, saida: 0, analise: 12, externos: 0, aguardando_assinatura: 0,
      enviado_para_assinatura: 0, arquivados: 0, recusados: 0,
    },
    atribuidos_a_mim: 0,
    sem_responsavel: 0,
    prazos: { vencidos: 2, vencendo: 0, no_prazo: 0, sem_prazo: 10 },
    aguardando_retorno: { total: 0, atrasados: 0 },
  });
  listMock.mockReset();
  listMock.mockResolvedValue({ items: [], total: 0 });
  dashboardMock.mockReset();
  dashboardMock.mockResolvedValue({
    kpis: { aguardando_aprovacao_qtd: 5, aguardando_autorizacao_qtd: 0, vencidas_qtd: 1 },
  });
  solicitacoesMock.mockReset();
  solicitacoesMock.mockResolvedValue([{ status: "solicitada" }, { status: "aprovada" }, { status: "solicitada" }]);
  alvarasKpisMock.mockReset();
  alvarasKpisMock.mockResolvedValue({ total_alvaras: 9, ativos: 6, vencidos: 1, a_renovar_30d: 2, indefinidos: 0 });
  marcarLidaMock.mockReset();
  marcarLidaMock.mockResolvedValue(undefined);
  marcarTodasMock.mockReset();
  marcarTodasMock.mockResolvedValue(undefined);
  notifMock.mockReset();
  notifMock.mockResolvedValue({
    nao_lidas: 2,
    items: [
      {
        id: 1, canal: "in_app", tipo: "x", titulo: "Processo recebido",
        mensagem: "Chegou o 123/2026.", link_url: "/m/protocolo/processos/123",
        payload: null, prioridade: "normal", criado_em: "2026-10-21T10:00:00Z",
        lido_em: null, enviado_em: null, erro: null,
      },
      {
        id: 2, canal: "in_app", tipo: "x", titulo: "Aviso sem link",
        mensagem: "Manutenção às 18h.", link_url: null,
        payload: null, prioridade: "baixa", criado_em: "2026-10-21T09:00:00Z",
        lido_em: null, enviado_em: null, erro: null,
      },
    ],
  });
});
afterEach(cleanup);

describe("Início — não é mais um atalho para o painel", () => {
  it("quem opera processos FICA no Início: nada de redirecionar", async () => {
    estado.perms = ["processo"];
    await abrir();
    await screen.findByRole("region", { name: "Protocolo" });
    expect(replace).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Início" })).toBeInTheDocument();
  });
});

describe("o que precisa de você hoje", () => {
  it("um cartão por módulo contratado que a pessoa alcança — e só esses", async () => {
    estado.perms = ["processo", "frota", "transporte_regulado", "pagamento_gerir"];
    // Pagamentos e transporte NÃO contratados: não aparecem, mesmo com permissão.
    await abrir();
    await screen.findByRole("region", { name: "Protocolo" });
    expect(screen.getByRole("region", { name: "Frota" })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Pagamentos" })).toBeNull();
    expect(screen.queryByRole("region", { name: "Transporte Regulado" })).toBeNull();
    expect(dashboardMock).not.toHaveBeenCalled();
    expect(alvarasKpisMock).not.toHaveBeenCalled();
  });

  it("módulo contratado sem a permissão de leitura não aparece", async () => {
    estado.perms = ["processo"];
    await abrir();
    await screen.findByRole("region", { name: "Protocolo" });
    expect(screen.queryByRole("region", { name: "Frota" })).toBeNull();
    expect(solicitacoesMock).not.toHaveBeenCalled();
  });

  it("protocolo: cada número leva à lista que o conta", async () => {
    estado.perms = ["processo"];
    await abrir();
    const p = await cartao("Protocolo");
    expect(await p.findByRole("link", { name: /A receber na unidade: 3/ })).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=entrada&ativos=0");
    expect(p.getByRole("link", { name: /Na mesa da unidade: 12/ })).toHaveAttribute(
      "href", "/m/protocolo/processos?caixa=analise&ativos=0");
    expect(p.getByRole("link", { name: /Com prazo vencido: 2/ })).toBeInTheDocument();
    // Zero não é link: não há lista para abrir.
    expect(p.queryByRole("link", { name: /Esperando a sua assinatura/ })).toBeNull();
  });

  it("frota conta as solicitações aguardando aprovação; pagamentos e transporte usam os KPIs do módulo", async () => {
    estado.su = true;
    modulosMock.mockResolvedValue({
      itens: [modulo("protocolo"), modulo("frota"), modulo("pagamentos"), modulo("transporte")],
    });
    await abrir();
    expect(await (await cartao("Frota")).findByRole("link", { name: /aguardando aprovação: 2/ })).toBeInTheDocument();
    expect(await (await cartao("Pagamentos")).findByRole("link", { name: /Aguardando aprovação: 5/ })).toBeInTheDocument();
    expect((await cartao("Pagamentos")).getByRole("link", { name: /Parcelas vencidas: 1/ })).toBeInTheDocument();
    expect(await (await cartao("Transporte Regulado")).findByRole("link", { name: /Alvarás vencidos: 1/ })).toBeInTheDocument();
  });

  it("número que não carregou diz isso, em vez de zero", async () => {
    estado.perms = ["processo"];
    painelMock.mockRejectedValue(new Error("fora do ar"));
    await abrir();
    expect(
      await (await cartao("Protocolo")).findByText(/Não foi possível carregar os números deste módulo/),
    ).toBeInTheDocument();
  });

  it("sem nenhum módulo ao alcance, explica onde estão os módulos", async () => {
    modulosMock.mockResolvedValue({ itens: [modulo("protocolo")] });
    await abrir();
    expect(await screen.findByText(/Nenhum módulo com pendências para o seu perfil/)).toBeInTheDocument();
  });

  it("'Abrir processo' só para quem pode inserir", async () => {
    estado.perms = ["processo"];
    await abrir();
    await screen.findByRole("region", { name: "Protocolo" });
    expect(screen.queryByRole("link", { name: /Abrir processo/ })).toBeNull();
    cleanup();
    estado.perms = ["processo", "processo:inserir"];
    await abrir();
    expect(await screen.findByRole("link", { name: /Abrir processo/ })).toHaveAttribute(
      "href", "/m/protocolo/processos/novo");
  });
});

describe("processos que você acompanha", () => {
  it("lista os favoritos e onde cada um está agora", async () => {
    estado.perms = ["processo"];
    listMock.mockResolvedValue({
      items: [{ id: 9, nup: null, numero_processo: "P9", assunto: "Poda", local_atual: "Sec. de Obras", ativo: true }],
      total: 1,
    });
    await abrir();
    const secao = within(await screen.findByRole("region", { name: "Processos que você acompanha" }));
    expect(await secao.findByRole("link", { name: "P9" })).toHaveAttribute("href", "/m/protocolo/processos/9");
    expect(secao.getByText("Sec. de Obras")).toBeInTheDocument();
    expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ favoritos: true, apenas_ativos: false }));
  });

  it("sem favorito, ensina como acompanhar", async () => {
    estado.perms = ["processo"];
    await abrir();
    expect(await screen.findByText(/Marque a estrela de um processo/)).toBeInTheDocument();
  });

  it("quem não opera processos não vê a seção", async () => {
    await abrir();
    await screen.findByText("Processo recebido");
    expect(screen.queryByRole("region", { name: "Processos que você acompanha" })).toBeNull();
    expect(listMock).not.toHaveBeenCalled();
  });
});

describe("notificações", () => {
  it("mostra as não lidas, com link quando há", async () => {
    await abrir();
    const lista = within(screen.getByRole("region", { name: "Notificações não lidas" }));
    expect(await lista.findByRole("link", { name: "Processo recebido" })).toHaveAttribute(
      "href", "/m/protocolo/processos/123");
    expect(lista.getByText("Aviso sem link")).toBeInTheDocument();
    expect(lista.queryByRole("link", { name: "Aviso sem link" })).toBeNull();
  });

  it("abrir uma notificação a marca como lida e recarrega a lista", async () => {
    await abrir();
    const lista = within(screen.getByRole("region", { name: "Notificações não lidas" }));
    const link = await lista.findByRole("link", { name: "Processo recebido" });
    expect(notifMock).toHaveBeenCalledTimes(1);
    fireEvent.click(link);
    await waitFor(() => expect(marcarLidaMock).toHaveBeenCalledWith(1));
    await waitFor(() => expect(notifMock).toHaveBeenCalledTimes(2));
  });

  it("marcar todas como lidas zera o que a tela mostra", async () => {
    await abrir();
    const lista = within(screen.getByRole("region", { name: "Notificações não lidas" }));
    await lista.findByRole("link", { name: "Processo recebido" });
    notifMock.mockResolvedValue({ nao_lidas: 0, items: [] });
    fireEvent.click(lista.getByRole("button", { name: /Marcar todas como lidas/ }));
    await waitFor(() => expect(marcarTodasMock).toHaveBeenCalled());
    expect(await lista.findByText("Nenhuma notificação nova.")).toBeInTheDocument();
  });

  it("sem notificação nova, diz isso", async () => {
    notifMock.mockResolvedValue({ nao_lidas: 0, items: [] });
    await abrir();
    expect(await screen.findByText("Nenhuma notificação nova.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar todas/ })).toBeNull();
  });

  it("leva aos módulos e às assinaturas", async () => {
    await abrir();
    expect(screen.getByRole("link", { name: /Meus módulos/ })).toHaveAttribute("href", "/modulos");
    expect(screen.getByRole("link", { name: /Para assinar/ })).toHaveAttribute("href", "/para-assinar");
  });
});

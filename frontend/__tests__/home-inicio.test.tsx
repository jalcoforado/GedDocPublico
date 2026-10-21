/**
 * Tela inicial depois que o painel de controle foi para o módulo Protocolo
 * (decisão de 2026-10-21): quem opera processos num tenant que contratou o
 * Protocolo é levado ao painel; os demais veem saudação, notificações e os
 * atalhos.
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
    can: (codigo: string) => estado.su || estado.perms.includes(codigo),
  }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, modulos: () => modulosMock() },
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

beforeEach(() => {
  estado.perms = [];
  estado.su = false;
  replace.mockClear();
  modulosMock.mockReset();
  modulosMock.mockResolvedValue({ itens: [modulo("protocolo"), modulo("frota")] });
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

describe("tela inicial", () => {
  it("quem opera processos vai direto para o painel do protocolo, sem ver a tela simples", async () => {
    estado.perms = ["processo"];
    await abrir();
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/m/protocolo/painel"));
    // Nada da tela simples piscou antes, e as notificações nem foram pedidas.
    expect(screen.queryByText(/Olá/)).toBeNull();
    expect(screen.queryByRole("link", { name: /Meus módulos/ })).toBeNull();
    expect(notifMock).not.toHaveBeenCalled();
  });

  it("enquanto a contratação não chega, não desenha nada nem redireciona", async () => {
    estado.perms = ["processo"];
    modulosMock.mockReturnValue(new Promise(() => {}));
    await abrir();
    await waitFor(() => expect(modulosMock).toHaveBeenCalled());
    expect(screen.queryByText(/Olá/)).toBeNull();
    expect(replace).not.toHaveBeenCalled();
  });

  it("super-usuário num tenant sem o Protocolo fica na tela simples", async () => {
    // `can()` é true para todo SU; sem olhar a contratação, a /home levaria
    // todo mundo de um tenant só de Frota para um módulo que ele não tem.
    estado.su = true;
    modulosMock.mockResolvedValue({ itens: [modulo("frota")] });
    await abrir();
    expect(await screen.findByText("Olá, João.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("quem tem `processo` num tenant sem o Protocolo fica na tela simples", async () => {
    estado.perms = ["processo"];
    modulosMock.mockResolvedValue({ itens: [modulo("pagamentos")] });
    await abrir();
    expect(await screen.findByText("Olá, João.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("se a contratação não puder ser lida, fica na tela simples", async () => {
    estado.perms = ["processo"];
    modulosMock.mockRejectedValue(new Error("rede"));
    await abrir();
    expect(await screen.findByText("Olá, João.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("quem não opera processos fica na tela inicial, sem nem consultar os módulos", async () => {
    await abrir();
    expect(await screen.findByText("Olá, João.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
    expect(modulosMock).not.toHaveBeenCalled();
  });

  it("a tela simples mostra as notificações não lidas", async () => {
    await abrir();
    const kpi = screen.getByText("Notificações").closest("[data-testid], div") as HTMLElement;
    await waitFor(() =>
      expect(screen.getByTestId("kpi-valor").textContent).toBe("2"));
    // O quadro não é link: não há tela que liste notificações (/perfil, para
    // onde ia, só tem as preferências) — a lista está logo abaixo.
    expect(kpi.closest("a")).toBeNull();

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
    expect(screen.getByTestId("kpi-valor").textContent).toBe("0");
  });

  it("sem notificação nova, diz isso", async () => {
    notifMock.mockResolvedValue({ nao_lidas: 0, items: [] });
    await abrir();
    expect(await screen.findByText("Nenhuma notificação nova.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Marcar todas/ })).toBeNull();
  });

  it("a tela simples leva aos módulos e às assinaturas", async () => {
    await abrir();
    expect(screen.getByRole("link", { name: /Meus módulos/ })).toHaveAttribute("href", "/modulos");
    expect(screen.getByRole("link", { name: /Para assinar/ })).toHaveAttribute("href", "/para-assinar");
  });
});

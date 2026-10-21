/**
 * Tela inicial depois que o painel de controle foi para o módulo Protocolo
 * (decisão de 2026-10-21): quem opera processos é levado ao painel; quem não
 * opera vê saudação, notificações e os atalhos.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const estado: { perms: string[] } = { perms: [] };
const replace = vi.fn();
const notifMock = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace, prefetch: vi.fn() }),
  usePathname: () => "/home",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { id: 5, nome: "João Lima" },
    perms: { is_super_usuario: false },
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    notificacoesApi: { ...actual.notificacoesApi, listarMinhas: () => notifMock() },
  };
});

vi.setConfig({ testTimeout: 20_000 });

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
  replace.mockClear();
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

  it("quem não opera processos fica na tela inicial", async () => {
    await abrir();
    expect(await screen.findByText("Olá, João.")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("a tela simples mostra as notificações não lidas", async () => {
    await abrir();
    const kpi = screen.getByText("Notificações").closest("a") as HTMLAnchorElement;
    await waitFor(() => expect(within(kpi).getByTestId("kpi-valor").textContent).toBe("2"));
    expect(kpi).toHaveAttribute("href", "/perfil");

    const lista = within(screen.getByRole("region", { name: "Notificações não lidas" }));
    expect(await lista.findByRole("link", { name: "Processo recebido" })).toHaveAttribute(
      "href", "/m/protocolo/processos/123");
    expect(lista.getByText("Aviso sem link")).toBeInTheDocument();
    expect(lista.queryByRole("link", { name: "Aviso sem link" })).toBeNull();
  });

  it("sem notificação nova, diz isso", async () => {
    notifMock.mockResolvedValue({ nao_lidas: 0, items: [] });
    await abrir();
    expect(await screen.findByText("Nenhuma notificação nova.")).toBeInTheDocument();
  });

  it("a tela simples leva aos módulos e às assinaturas", async () => {
    await abrir();
    expect(screen.getByRole("link", { name: /Meus módulos/ })).toHaveAttribute("href", "/modulos");
    expect(screen.getByRole("link", { name: /Para assinar/ })).toHaveAttribute("href", "/para-assinar");
  });
});

/**
 * Acessibilidade e responsividade do popover de notificações (UX-03N).
 * O que se afirma aqui: o sino tem nome acessível que carrega o contador,
 * expõe estado expandido, fecha por ESC devolvendo o foco, fecha ao clicar
 * fora, NÃO se anuncia como dialog (não implementa focus-trap) e o painel
 * carrega o clamp responsivo que o impede de estourar viewport estreita.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const listarMock = vi.fn();
vi.mock("@/lib/api", () => ({
  notificacoesApi: {
    listarMinhas: () => listarMock(),
    marcarLida: vi.fn().mockResolvedValue({}),
    marcarTodasLidas: vi.fn().mockResolvedValue({}),
  },
}));

import { NotificacoesBell } from "@/components/NotificacoesBell";

function renderBell() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NotificacoesBell />
    </QueryClientProvider>,
  );
}

const DUAS_NAO_LIDAS = {
  nao_lidas: 2,
  items: [
    {
      id: 1,
      titulo: "Processo tramitado",
      mensagem: "O processo 2026/001 foi encaminhado.",
      criado_em: new Date().toISOString(),
      lido_em: null,
      link_url: null,
      prioridade: "normal",
    },
    {
      id: 2,
      titulo: "Assinatura pendente",
      mensagem: "Há um documento aguardando sua assinatura.",
      criado_em: new Date().toISOString(),
      lido_em: null,
      link_url: null,
      prioridade: "alta",
    },
  ],
};

beforeEach(() => {
  listarMock.mockReset();
  listarMock.mockResolvedValue(DUAS_NAO_LIDAS);
});

describe("NotificacoesBell — acessibilidade do popover", () => {
  it("o sino tem nome acessível com o contador e expõe aria-expanded", async () => {
    renderBell();
    const sino = await waitFor(() =>
      screen.getByRole("button", { name: /notificações, 2 não lidas/i }),
    );
    expect(sino).toHaveAttribute("aria-expanded", "false");
    expect(sino).toHaveAttribute("aria-haspopup", "true");

    fireEvent.click(sino);
    expect(sino).toHaveAttribute("aria-expanded", "true");
    // aria-controls só aponta para o painel enquanto ele existe no DOM
    const painel = screen.getByRole("region", { name: /notificações/i });
    expect(sino).toHaveAttribute("aria-controls", painel.id);
  });

  it("não se anuncia como dialog — não implementa a semântica completa (focus-trap etc.)", async () => {
    renderBell();
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /notificações/i })));
    expect(screen.getByRole("region", { name: /notificações/i })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("ESC fecha o popover e devolve o foco ao sino", async () => {
    renderBell();
    const sino = await waitFor(() => screen.getByRole("button", { name: /notificações/i }));
    fireEvent.click(sino);
    expect(screen.getByRole("region", { name: /notificações/i })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("region", { name: /notificações/i })).toBeNull();
    expect(sino).toHaveAttribute("aria-expanded", "false");
    expect(sino).toHaveFocus();
  });

  it("clique fora fecha o popover", async () => {
    renderBell();
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /notificações/i })));
    expect(screen.getByRole("region", { name: /notificações/i })).toBeInTheDocument();

    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("region", { name: /notificações/i })).toBeNull();
  });

  it("o painel carrega o clamp responsivo: cheio em telas estreitas, 360px a partir de sm", async () => {
    renderBell();
    fireEvent.click(await waitFor(() => screen.getByRole("button", { name: /notificações/i })));
    const painel = screen.getByRole("region", { name: /notificações/i });
    // Mobile-first: ancorado à viewport com margem lateral, nunca mais largo que ela
    expect(painel.className).toContain("inset-x-3");
    // A partir de sm volta a ser popover ancorado ao sino, com largura fixa clampada
    expect(painel.className).toContain("sm:w-[360px]");
    expect(painel.className).toContain("sm:max-w-[calc(100vw-2rem)]");
  });
});

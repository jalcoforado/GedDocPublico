/**
 * Portal do cidadão — "Entrar com gov.br" (backend: PR #76, backlog 2.6).
 *
 * O botão só aparece quando o gov.br está configurado (GET
 * /auth/govbr/disponivel) — hoje não está em ambiente nenhum, e um botão que
 * leva a um 503 seria pior que nenhum. Quando o login falha, o backend devolve
 * o navegador a esta tela com `?govbr=<motivo>`, e a tela explica o motivo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const govbrDisponivel = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: { ...real.api, cidadao: { ...real.api.cidadao, govbrDisponivel: () => govbrDisponivel() } },
  };
});

import CidadaoLoginPage from "@/app/cidadao/login/page";

function montar(no: ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{no}</QueryClientProvider>);
}

beforeEach(() => govbrDisponivel.mockReset());
afterEach(() => window.history.replaceState({}, "", "/"));

describe("login do cidadão — gov.br", () => {
  it("sem gov.br configurado, não mostra o botão", async () => {
    govbrDisponivel.mockResolvedValue({ disponivel: false });
    montar(<CidadaoLoginPage />);
    await vi.waitFor(() => expect(govbrDisponivel).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /gov\.br/i })).not.toBeInTheDocument();
  });

  it("com gov.br configurado, o botão leva ao login gov.br voltando aos processos", async () => {
    govbrDisponivel.mockResolvedValue({ disponivel: true });
    montar(<CidadaoLoginPage />);
    const link = await screen.findByRole("link", { name: /Entrar com gov\.br/i });
    const href = link.getAttribute("href") ?? "";
    expect(href).toMatch(/\/auth\/govbr\/login\?next=%2Fcidadao%2Fprocessos$/);
  });

  it.each([
    ["cancelado", /cancelado/i],
    ["inativo", /inativo/i],
    ["indisponivel", /indisponível/i],
    ["falhou", /não foi possível/i],
  ])("volta do gov.br com motivo %s e explica", async (motivo, texto) => {
    govbrDisponivel.mockResolvedValue({ disponivel: true });
    window.history.replaceState({}, "", `/cidadao/login?govbr=${motivo}`);
    montar(<CidadaoLoginPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(texto);
  });

  it("motivo desconhecido na URL não vira texto na tela", async () => {
    govbrDisponivel.mockResolvedValue({ disponivel: true });
    window.history.replaceState({}, "", "/cidadao/login?govbr=%3Cscript%3E");
    montar(<CidadaoLoginPage />);
    await screen.findByRole("link", { name: /Entrar com gov\.br/i });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

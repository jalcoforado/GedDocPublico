/**
 * As caixas de trabalho como abas da tela de Processos.
 *
 * O que importa: as nove (Todos + oito caixas) na ordem de `CAIXAS`, cada uma
 * levando à SUA lista; uma só marcada como atual; o número de cada aba vindo
 * da contagem das caixas; e a falta da contagem não derrubando a navegação.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const caixasMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { processos: { caixas: () => caixasMock() } },
}));

import { AbasCaixas } from "@/components/protocolo/AbasCaixas";
import type { CaixaProcesso } from "@/lib/api";
import { CAIXAS, hrefDaCaixa } from "@/lib/caixas-processos";

const CONTAGEM = {
  entrada: 18,
  saida: 1,
  analise: 26,
  externos: 0,
  aguardando_assinatura: 22,
  enviado_para_assinatura: 19,
  arquivados: 56,
  recusados: 3,
};

function renderAbas(caixa?: CaixaProcesso) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AbasCaixas caixa={caixa} />
    </QueryClientProvider>,
  );
}

const abas = () => screen.getAllByRole("link");
const atuais = () => abas().filter((a) => a.getAttribute("aria-current") === "page");

beforeEach(() => {
  caixasMock.mockReset();
  caixasMock.mockResolvedValue(CONTAGEM);
});

describe("abas das caixas de trabalho", () => {
  it("Todos e as oito caixas, na ordem, cada uma com o link da sua lista", () => {
    renderAbas();
    expect(abas().map((a) => a.getAttribute("href"))).toEqual([
      "/m/protocolo/processos",
      ...CAIXAS.map((c) => hrefDaCaixa(c.caixa)),
    ]);
    expect(screen.getByRole("navigation", { name: "Caixas de trabalho" })).toBeTruthy();
  });

  it("navegação, não abas ARIA: links com aria-current, sem role=tab", () => {
    renderAbas("entrada");
    expect(screen.queryAllByRole("tab")).toHaveLength(0);
    expect(atuais()).toHaveLength(1);
  });

  it("sem caixa, a atual é 'Todos'", () => {
    renderAbas();
    expect(atuais()).toHaveLength(1);
    expect(atuais()[0].textContent).toContain("Todos");
  });

  it("com uma caixa aberta, só ela é a atual", () => {
    renderAbas("analise");
    expect(atuais()).toHaveLength(1);
    expect(atuais()[0].getAttribute("href")).toBe(hrefDaCaixa("analise"));
  });

  it("mostra a contagem de cada caixa, com unidade para leitor de tela", async () => {
    renderAbas();
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /^Entrada \(Caixa de entrada\)\s*18 processos$/ })).toBeTruthy(),
    );
    expect(screen.getByRole("link", { name: /^Saída \(Caixa de saída\)\s*1 processo$/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /^Externos\s*0 processos$/ })).toBeTruthy();
    // "Todos" não é uma caixa: não tem número.
    expect(screen.getByRole("link", { name: "Todos" })).toBeTruthy();
  });

  it("se a contagem falhar, as abas continuam lá — só sem número", async () => {
    caixasMock.mockRejectedValue(new Error("fora do ar"));
    renderAbas();
    await waitFor(() => expect(caixasMock).toHaveBeenCalled());
    expect(abas()).toHaveLength(CAIXAS.length + 1);
    for (const a of abas()) expect(a.textContent).not.toMatch(/\d/);
  });
});

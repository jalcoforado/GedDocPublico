/**
 * Coluna de caixas da tela de Processos.
 *
 * O que importa travar: (1) o link de cada caixa abre uma visão LIMPA — só a
 * caixa, sem os filtros em curso —, porque é isso que faz o número ao lado do
 * rótulo ser o total da lista; (2) a caixa aberta é anunciada como tal, não só
 * pintada; (3) contagem ausente não derruba a navegação.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  CAIXAS,
  CaixasProcessos,
  caixaDaUrl,
  hrefDaCaixa,
} from "@/components/CaixasProcessos";
import type { CaixasContagem } from "@/lib/api";

const BASE = "/m/protocolo/processos";
const CONTAGEM: CaixasContagem = {
  entrada: 18,
  saida: 1,
  analise: 26,
  externos: 0,
  aguardando_assinatura: 22,
  enviado_para_assinatura: 19,
  arquivados: 56,
};

describe("caixas de processos", () => {
  it("lista as sete caixas, na ordem do layout, mais 'Todos os processos'", () => {
    render(<CaixasProcessos base={BASE} ativa={undefined} contagem={CONTAGEM} />);
    const nav = screen.getByRole("navigation", { name: "Caixas de processos" });
    const rotulos = within(nav)
      .getAllByRole("link")
      .map((a) => a.textContent ?? "");
    expect(rotulos[0]).toContain("Todos os processos");
    CAIXAS.forEach((c, i) => expect(rotulos[i + 1]).toContain(c.rotulo));
    expect(rotulos).toHaveLength(CAIXAS.length + 1);
  });

  it("o link da caixa carrega SÓ a caixa — não herda filtros em curso", () => {
    render(<CaixasProcessos base={BASE} ativa={undefined} contagem={CONTAGEM} />);
    const entrada = screen.getByRole("link", { name: /Caixa de entrada/ });
    expect(entrada.getAttribute("href")).toBe(`${BASE}?caixa=entrada&ativos=0`);
    const todos = screen.getByRole("link", { name: /Todos os processos/ });
    expect(todos.getAttribute("href")).toBe(`${BASE}?ativos=0`);
  });

  it("mostra o contador de cada caixa, com unidade para leitor de tela", () => {
    render(<CaixasProcessos base={BASE} ativa={undefined} contagem={CONTAGEM} />);
    expect(screen.getByRole("link", { name: /Caixa de entrada\s*18 processos/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Caixa de saída\s*1 processo$/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Externos\s*0 processos/ })).toBeTruthy();
  });

  it("anuncia a caixa aberta com aria-current, e só ela", () => {
    render(<CaixasProcessos base={BASE} ativa="analise" contagem={CONTAGEM} />);
    const atuais = screen
      .getAllByRole("link")
      .filter((a) => a.getAttribute("aria-current") === "page");
    expect(atuais).toHaveLength(1);
    expect(atuais[0].textContent).toContain("Análise");
  });

  it("sem caixa aberta, a atual é 'Todos os processos'", () => {
    render(<CaixasProcessos base={BASE} ativa={undefined} contagem={CONTAGEM} />);
    const atual = screen
      .getAllByRole("link")
      .find((a) => a.getAttribute("aria-current") === "page");
    expect(atual?.textContent).toContain("Todos os processos");
  });

  it("sem contagem (carregando ou erro) continua navegável, só sem números", () => {
    render(<CaixasProcessos base={BASE} ativa={undefined} contagem={undefined} />);
    const entrada = screen.getByRole("link", { name: /Caixa de entrada/ });
    expect(entrada.getAttribute("href")).toBe(`${BASE}?caixa=entrada&ativos=0`);
    expect(entrada.textContent).not.toMatch(/\d/);
  });
});

describe("caixa ↔ URL", () => {
  it("aceita só valor da lista — 'recusados' e lixo viram undefined, não 422", () => {
    expect(caixaDaUrl("entrada")).toBe("entrada");
    expect(caixaDaUrl("recusados")).toBeUndefined();
    expect(caixaDaUrl("")).toBeUndefined();
    expect(caixaDaUrl(null)).toBeUndefined();
  });

  it("hrefDaCaixa é o inverso de caixaDaUrl para toda caixa", () => {
    for (const { caixa } of CAIXAS) {
      const url = new URL(hrefDaCaixa(BASE, caixa), "http://x");
      expect(caixaDaUrl(url.searchParams.get("caixa"))).toBe(caixa);
    }
  });
});

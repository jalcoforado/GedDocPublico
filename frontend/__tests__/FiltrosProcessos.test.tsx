/**
 * Barra de busca e filtros da tela de Processos.
 *
 * O que importa: a busca aplica com Enter; o resto dos filtros fica fechado
 * até pedir, e o botão conta quantos estão valendo; cada filtro valendo vira
 * um chip que se remove sozinho; o escopo fica à vista e aplica no clique.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FiltrosProcessos, contarAvancados } from "@/components/protocolo/FiltrosProcessos";
import type { ProcessoListFilters } from "@/lib/api";

const ASSUNTOS = [{ id: 7, nome: "Poda de árvore" }];
const UNIDADES = [{ id: 3, nome: "Protocolo Geral" }];

function renderBarra(filtros: ProcessoListFilters, total: number | undefined = 12) {
  const aoAplicar = vi.fn();
  const aoLimpar = vi.fn();
  render(
    <FiltrosProcessos
      filtros={filtros}
      aoAplicar={aoAplicar}
      aoLimpar={aoLimpar}
      assuntos={ASSUNTOS}
      unidades={UNIDADES}
      total={total}
    />,
  );
  return { aoAplicar, aoLimpar };
}

describe("barra de busca e filtros", () => {
  it("Enter na busca aplica o que foi digitado", () => {
    const { aoAplicar } = renderBarra({ apenas_ativos: true });
    const busca = screen.getByRole("textbox", { name: /Busca por número/ });
    fireEvent.change(busca, { target: { value: "jose" } });
    fireEvent.submit(busca.closest("form")!);
    expect(aoAplicar).toHaveBeenCalledWith(expect.objectContaining({ q: "jose", apenas_ativos: true }));
  });

  it("os demais filtros ficam fechados até pedir", () => {
    renderBarra({ apenas_ativos: true });
    const botao = screen.getByRole("button", { name: /Filtros/ });
    expect(botao.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById("filtros-processos-painel")?.hidden).toBe(true);
    fireEvent.click(botao);
    expect(botao.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById("filtros-processos-painel")?.hidden).toBe(false);
  });

  it("o botão conta os filtros do painel que estão valendo", () => {
    renderBarra({ id_assunto: 7, favoritos: true, apenas_ativos: true });
    expect(screen.getByRole("button", { name: /Filtros\s*2 filtros ativos/ })).toBeTruthy();
    // "Só ativos" é o padrão da tela: vira chip, mas não conta no botão.
    expect(contarAvancados({ apenas_ativos: true })).toBe(0);
  });

  it("cada filtro valendo vira um chip com nome legível, e remover aplica sem ele", () => {
    const { aoAplicar } = renderBarra({ q: "jose", id_assunto: 7, id_unidade: 3, apenas_ativos: true });
    expect(screen.getByRole("button", { name: "Remover filtro “jose”" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remover filtro Assunto: Poda de árvore" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remover filtro Unidade: Protocolo Geral" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Remover filtro Só ativos" }));
    expect(aoAplicar).toHaveBeenLastCalledWith(
      expect.objectContaining({ q: "jose", id_assunto: 7, apenas_ativos: false }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Remover filtro Assunto: Poda de árvore" }));
    expect(aoAplicar).toHaveBeenLastCalledWith(expect.objectContaining({ id_assunto: undefined, q: "jose" }));
  });

  it("'Limpar tudo' só aparece com mais de um chip", () => {
    const { aoLimpar } = renderBarra({ q: "jose", apenas_ativos: true });
    fireEvent.click(screen.getByRole("button", { name: "Limpar tudo" }));
    expect(aoLimpar).toHaveBeenCalled();
  });

  it("sem filtro nenhum, sem chip — só o total", () => {
    renderBarra({ apenas_ativos: false }, 1);
    expect(screen.getByText("1 processo")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Remover filtro/ })).toBeNull();
  });

  it("o escopo fica à vista, marca o atual e aplica no clique", () => {
    const { aoAplicar } = renderBarra({ escopo: "unidade", apenas_ativos: true });
    const grupo = screen.getByRole("group", { name: "Escopo" });
    const marcado = grupo.querySelector("[aria-pressed=true]");
    expect(marcado?.textContent).toBe("Da minha unidade");
    fireEvent.click(screen.getByRole("button", { name: "Meus" }));
    expect(aoAplicar).toHaveBeenLastCalledWith(expect.objectContaining({ escopo: "meus" }));
    fireEvent.click(screen.getByRole("button", { name: "Todos" }));
    expect(aoAplicar).toHaveBeenLastCalledWith(expect.objectContaining({ escopo: undefined }));
  });
});

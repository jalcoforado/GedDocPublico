/**
 * Menu por área (2026-11-14): a barra tem seções por ÁREA de trabalho
 * (Atendimento, Financeiro, Mobilidade) montadas a partir dos menus dos
 * módulos, em vez de uma seção por módulo que repetia "Visão geral",
 * "Dashboard", "Relatórios" e "Cadastros".
 *
 * O que este teste protege: que nenhuma tela de trabalho suma em silêncio
 * (toda tela "barra" de um módulo está numa área), que nenhuma área aponte
 * para tela que não existe, e o comportamento com módulos não contratados.
 */
import { describe, expect, it } from "vitest";

import { MENUS } from "@/lib/menus";
import {
  AREAS,
  acharItem,
  ehIndiceDeCadastro,
  modulosDasAreas,
  navPorArea,
  orfasDaBarra,
} from "@/lib/menus/areas";

const nome = (s: string) => `[${s}]`;
const TODOS = ["protocolo", "pagamentos", "frota", "transporte", "administracao"];

describe("áreas do menu", () => {
  it("toda tela de trabalho dos módulos está numa área (nenhuma cai na rede de segurança)", () => {
    const orfas = Array.from(modulosDasAreas()).flatMap((m) =>
      orfasDaBarra(m)
        .filter((i) => !ehIndiceDeCadastro(i))
        .map((i) => `${m}: ${i.label} (${i.href})`),
    );
    expect(orfas, "tela 'barra' sem área — acrescente em lib/menus/areas.ts").toEqual([]);
  });

  it("toda referência de área aponta para uma tela que existe no menu do módulo", () => {
    const quebradas: string[] = [];
    for (const area of AREAS)
      for (const r of area.itens)
        for (const x of "subgrupo" in r ? r.itens : [r])
          if (!acharItem(x.modulo, x.href)) quebradas.push(`${area.titulo}: ${x.modulo} ${x.href}`);
    expect(quebradas).toEqual([]);
  });

  it("com tudo contratado: Atendimento, Financeiro, Mobilidade, Cadastros, Administração por último", () => {
    const nav = navPorArea(TODOS, nome);
    expect(nav.map((g) => g.title)).toEqual([
      "Atendimento",
      "Financeiro",
      "Mobilidade",
      "Cadastros e configuração",
      "[administracao]",
    ]);
    expect(nav[nav.length - 1].quieto).toBe(true);
    expect(nav.find((g) => g.title === "Cadastros e configuração")?.items.map((i) => i.href)).toEqual([
      "/cadastros",
    ]);
  });

  it("o que saiu da barra: Dashboard (virou aba Indicadores) e os índices de cadastro de cada módulo", () => {
    const hrefs = navPorArea(TODOS, nome).flatMap((g) =>
      g.items.flatMap((i) => [i.href, ...(i.children ?? []).map((c) => c.href)]),
    );
    expect(hrefs).not.toContain("/m/pagamentos/dashboard");
    expect(hrefs).not.toContain("/m/protocolo/cadastros");
    expect(hrefs).not.toContain("/m/pagamentos/cadastros");
    // Mas continuam no menu do módulo: Ctrl+K e guardas de rota leem de lá.
    expect(acharItem("pagamentos", "/m/pagamentos/dashboard")?.label).toBe("Indicadores");
  });

  it("Mobilidade com os dois módulos: um subgrupo para cada (Frota pública, Transporte regulado)", () => {
    const mob = navPorArea(TODOS, nome).find((g) => g.title === "Mobilidade")!;
    expect(mob.items.map((i) => i.label)).toEqual(["Frota pública", "Transporte regulado"]);
    expect(mob.items[0].children?.map((c) => c.href)).toEqual(["/m/frota", "/m/frota/veiculos", "/m/frota/solicitacoes"]);
  });

  it("Mobilidade com um módulo só: sem acordeão, as telas sobem direto", () => {
    const mob = navPorArea(["frota"], nome).find((g) => g.title === "Mobilidade")!;
    expect(mob.items.map((i) => i.href)).toEqual(["/m/frota", "/m/frota/veiculos", "/m/frota/solicitacoes"]);
    expect(mob.items.every((i) => !i.children)).toBe(true);
  });

  it("módulo não contratado: a área dele não aparece", () => {
    const titulos = navPorArea(["pagamentos"], nome).map((g) => g.title);
    expect(titulos).toEqual(["Financeiro", "Cadastros e configuração"]);
  });

  it("só Administração contratada: nem áreas nem a entrada de cadastros", () => {
    expect(navPorArea(["administracao"], nome).map((g) => g.title)).toEqual(["[administracao]"]);
  });

  it("os itens da barra são os do menu do módulo (mesma permissão) — a área só reorganiza", () => {
    const nav = navPorArea(TODOS, nome);
    const conc = nav.flatMap((g) => g.items).find((i) => i.href === "/m/pagamentos/conciliacao")!;
    const original = acharItem("pagamentos", "/m/pagamentos/conciliacao")!;
    expect(conc.perm).toBe(original.perm);
    expect(conc.anyOf).toEqual(original.anyOf);
    // Nenhuma área inventa módulo: todo slug citado existe em MENUS.
    for (const m of modulosDasAreas()) expect(MENUS[m], m).toBeDefined();
  });
});

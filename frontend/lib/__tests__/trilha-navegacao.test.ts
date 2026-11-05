import { beforeEach, describe, expect, it } from "vitest";

import {
  comFiltrosLembrados,
  destinoDeVolta,
  registrarVisita,
} from "@/lib/trilha-navegacao";

function trilha(): string[] {
  return JSON.parse(window.sessionStorage.getItem("aprimora.trilha.v1") ?? "[]");
}

const LISTA = "/m/protocolo/processos";
const LISTA_FILTRADA = `${LISTA}?situacao=rascunho&ativos=1`;

beforeEach(() => window.sessionStorage.clear());

describe("trilha de navegação (SI-17/18)", () => {
  it("lista filtrada → processo: a seta volta para a lista com os filtros", () => {
    registrarVisita(LISTA);
    registrarVisita(LISTA_FILTRADA); // trocar filtro atualiza, não empilha
    registrarVisita("/m/protocolo/processos/7");
    expect(trilha()).toEqual([LISTA_FILTRADA, "/m/protocolo/processos/7"]);
    expect(destinoDeVolta(trilha(), "/m/protocolo/processos/7")).toBe(LISTA_FILTRADA);
  });

  it("veio do painel, volta ao painel — a página anterior de verdade", () => {
    registrarVisita("/m/protocolo/painel");
    registrarVisita("/m/protocolo/processos/7");
    expect(destinoDeVolta(trilha(), "/m/protocolo/processos/7")).toBe("/m/protocolo/painel");
  });

  it("editar e salvar não prende a seta no formulário", () => {
    registrarVisita(LISTA_FILTRADA);
    registrarVisita("/m/protocolo/processos/7");
    registrarVisita("/m/protocolo/processos/7/editar");
    registrarVisita("/m/protocolo/processos/7"); // salvou e voltou ao processo
    expect(trilha()).toEqual([LISTA_FILTRADA, "/m/protocolo/processos/7"]);
    expect(destinoDeVolta(trilha(), "/m/protocolo/processos/7")).toBe(LISTA_FILTRADA);
  });

  it("aba nova, sem histórico: não há destino, e a seta cai na tela-mãe", () => {
    registrarVisita("/m/protocolo/processos/7");
    expect(destinoDeVolta(trilha(), "/m/protocolo/processos/7")).toBeNull();
  });

  it("antes de a visita atual ser anotada, o destino já é a página anterior", () => {
    // O PageHeader pode ler a trilha antes do rastreador do shell gravar a
    // visita atual (efeitos rodam do filho para o pai).
    registrarVisita(LISTA_FILTRADA);
    expect(destinoDeVolta(trilha(), "/m/protocolo/processos/7")).toBe(LISTA_FILTRADA);
  });

  it("link para a lista ganha os filtros lembrados; link com query fica como está", () => {
    registrarVisita(LISTA_FILTRADA);
    registrarVisita("/m/protocolo/processos/7");
    expect(comFiltrosLembrados(trilha(), LISTA)).toBe(LISTA_FILTRADA);
    expect(comFiltrosLembrados(trilha(), `${LISTA}?caixa=entrada`)).toBe(`${LISTA}?caixa=entrada`);
    expect(comFiltrosLembrados(trilha(), "/m/frota")).toBe("/m/frota");
  });
});

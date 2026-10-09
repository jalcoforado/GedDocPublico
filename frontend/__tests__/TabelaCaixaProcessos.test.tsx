/**
 * Tabela de uma caixa de trabalho: a coluna "Tempo na caixa" e o destaque de
 * quem espera há muito.
 *
 * O destaque é cor — e cor sozinha não chega a quem não a enxerga. Por isso há
 * teste para o texto de leitor de tela, não só para o limiar.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/FavoritoStar", () => ({ FavoritoStar: () => null }));

import {
  DIAS_ATENCAO,
  DIAS_CRITICO,
  TabelaCaixaProcessos,
  nivelDeEspera,
} from "@/components/TabelaCaixaProcessos";
import type { ProcessoListItem } from "@/lib/api";

const AGORA = new Date("2026-10-09T12:00:00");
const haDias = (d: number) => new Date(AGORA.getTime() - d * 86_400_000).toISOString();

function item(id: number, extra: Partial<ProcessoListItem> = {}): ProcessoListItem {
  return {
    id,
    numero_processo: `2026/00000${id}`,
    nup: null,
    numero_origem: null,
    situacao: "protocolado",
    data_hora_abertura: haDias(60),
    parado_desde: haDias(1),
    ativo: true,
    publico: true,
    nivel_sigilo: "ostensivo",
    externo: false,
    assunto: "Aposentadoria compulsória",
    tipo_processo: "Pessoal",
    manifestante: "Franc. da Silva",
    manifestante_cpf_cnpj: null,
    unidade_proprietaria: "RH",
    local_atual: "RH",
    id_usuario_responsavel: 7,
    responsavel: "José de Brito",
    favorito: false,
    marcadores: [],
    ...extra,
  };
}

function renderTabela(itens: ProcessoListItem[] | undefined, carregando = false) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <TabelaCaixaProcessos itens={itens} carregando={carregando} />
    </QueryClientProvider>,
  );
}

describe("nível de espera", () => {
  it("muda de faixa exatamente nos limiares", () => {
    expect(nivelDeEspera(haDias(DIAS_ATENCAO - 1), AGORA)).toBe("normal");
    expect(nivelDeEspera(haDias(DIAS_ATENCAO), AGORA)).toBe("atencao");
    expect(nivelDeEspera(haDias(DIAS_CRITICO - 1), AGORA)).toBe("atencao");
    expect(nivelDeEspera(haDias(DIAS_CRITICO), AGORA)).toBe("critico");
  });

  it("data ausente ou inválida não vira alarme", () => {
    expect(nivelDeEspera(null, AGORA)).toBe("normal");
    expect(nivelDeEspera("não é data", AGORA)).toBe("normal");
  });
});

describe("tabela da caixa", () => {
  it("tem as colunas do layout de referência, com 'Tempo na caixa'", () => {
    renderTabela([item(1)]);
    const cabecalhos = screen.getAllByRole("columnheader").map((th) => th.textContent);
    expect(cabecalhos).toEqual([
      "Nº do processo",
      "Assunto",
      "Tempo na caixa",
      "Envolvido",
      "Responsável",
      "Ações",
    ]);
  });

  it("o número do processo e 'Abrir' levam ao detalhe em /m/protocolo/", () => {
    renderTabela([item(42)]);
    const links = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/m/protocolo/processos/42", "/m/protocolo/processos/42"]);
  });

  it("quem espera há muito é dito em texto, não só em cor", () => {
    const antigo = new Date(Date.now() - (DIAS_CRITICO + 5) * 86_400_000).toISOString();
    renderTabela([item(1, { parado_desde: antigo })]);
    expect(screen.getByText(/parado há muito tempo/)).toBeTruthy();
  });

  it("processo recente não carrega aviso nenhum", () => {
    renderTabela([item(1, { parado_desde: new Date().toISOString() })]);
    expect(screen.queryByText(/parado há muito tempo|atenção/)).toBeNull();
  });

  it("sem responsável é um estado nomeado, não um travessão", () => {
    renderTabela([item(1, { responsavel: null, id_usuario_responsavel: null })]);
    expect(screen.getByText("Sem responsável")).toBeTruthy();
  });

  it("caixa vazia diz que está vazia", () => {
    renderTabela([]);
    expect(screen.getByText("Nenhum processo nesta caixa")).toBeTruthy();
  });
});

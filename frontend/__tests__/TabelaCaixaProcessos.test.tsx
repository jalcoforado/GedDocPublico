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
  TabelaCaixaProcessos,
  nivelDeEspera,
  textoDoPrazo,
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
  it("vem do prazo, não do tempo parado", () => {
    expect(nivelDeEspera("atrasado")).toBe("critico");
    expect(nivelDeEspera("vencendo")).toBe("atencao");
    expect(nivelDeEspera("dentro_do_prazo")).toBe("normal");
  });

  it("sem prazo, ou sem o campo, não vira alarme", () => {
    expect(nivelDeEspera("sem_prazo")).toBe("normal");
    expect(nivelDeEspera(undefined)).toBe("normal");
    expect(nivelDeEspera(null)).toBe("normal");
  });
});

describe("prazo em palavras", () => {
  const em = (dias: number, hora = "23:59:59") => {
    const d = new Date(AGORA.getTime() + dias * 86_400_000);
    const p = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${hora}`;
  };

  it("conta dias de calendário até o vencimento", () => {
    expect(textoDoPrazo("dentro_do_prazo", em(10), AGORA)).toBe("vence em 10 dias");
    expect(textoDoPrazo("vencendo", em(1), AGORA)).toBe("vence amanhã");
    expect(textoDoPrazo("vencendo", em(0), AGORA)).toBe("vence hoje");
  });

  it("diz há quanto tempo venceu", () => {
    expect(textoDoPrazo("atrasado", em(-1), AGORA)).toBe("prazo vencido ontem");
    expect(textoDoPrazo("atrasado", em(-6), AGORA)).toBe("prazo vencido há 6 dias");
    // Prazo de serviço que venceu mais cedo no mesmo dia.
    expect(textoDoPrazo("atrasado", em(0, "08:00:00"), AGORA)).toBe("prazo vencido hoje");
  });

  it("sem prazo não há o que dizer", () => {
    expect(textoDoPrazo("sem_prazo", null, AGORA)).toBeNull();
    expect(textoDoPrazo(undefined, em(3), AGORA)).toBeNull();
    expect(textoDoPrazo("vencendo", "não é data", AGORA)).toBeNull();
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

  it("prazo vencido é dito em texto visível, não só em cor", () => {
    const ha3dias = new Date(Date.now() - 3 * 86_400_000).toISOString();
    renderTabela([
      item(1, {
        prazo_caixa_status: "atrasado",
        prazo_caixa_vence_em: ha3dias,
        prazo_caixa_origem: "encaminhamento",
      }),
    ]);
    const aviso = screen.getByText("prazo vencido há 3 dias");
    expect(aviso.className).toContain("text-danger-soft-foreground");
    expect(aviso.getAttribute("title")).toBe("Prazo fixado no encaminhamento");
  });

  it("parado há muito, mas sem prazo, não é destacado", () => {
    const antigo = new Date(Date.now() - 40 * 86_400_000).toISOString();
    renderTabela([item(1, { parado_desde: antigo, prazo_caixa_status: "sem_prazo" })]);
    expect(screen.queryByText(/vence|vencido/)).toBeNull();
    expect(screen.getByText("40 d").className).not.toMatch(/danger|warning/);
  });

  it("dentro do prazo mostra quando vence, sem alarme", () => {
    const em9dias = new Date(Date.now() + 9 * 86_400_000).toISOString();
    renderTabela([
      item(1, {
        prazo_caixa_status: "dentro_do_prazo",
        prazo_caixa_vence_em: em9dias,
        prazo_caixa_origem: "servico",
      }),
    ]);
    const aviso = screen.getByText("vence em 9 dias");
    expect(aviso.className).not.toMatch(/danger|warning/);
    expect(aviso.getAttribute("title")).toBe("Prazo do serviço, contado da abertura");
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

describe("marcadores na linha da caixa", () => {
  const mk = (id: number, nome: string) => ({ id, nome, cor: "rgb(200, 30, 30)" });

  it("mostra a etiqueta com o nome do marcador", () => {
    renderTabela([item(1, { marcadores: [mk(1, "Urgente")] })]);
    expect(screen.getByTitle("Urgente").textContent).toBe("Urgente");
    expect(screen.getByText("Marcadores: Urgente")).toBeTruthy();
  });

  it("mais de três vira +N na própria linha", () => {
    renderTabela([
      item(1, { marcadores: [mk(1, "A"), mk(2, "B"), mk(3, "C"), mk(4, "D")] }),
    ]);
    expect(screen.getByText("+1").getAttribute("title")).toBe("D");
  });

  it("sem marcadores não desenha etiqueta nenhuma", () => {
    renderTabela([item(1)]);
    expect(screen.queryByText(/^Marcadores:/)).toBeNull();
  });
});

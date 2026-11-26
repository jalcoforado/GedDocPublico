/**
 * "Fluxo do processo" de protocolo: o caminho do processo, com as quantidades
 * das caixas de trabalho da unidade de quem está logado.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FASES } from "@/components/protocolo/MapaDoProtocolo";
import { CAIXAS } from "@/lib/caixas-processos";

const estado: { perms: string[] } = { perms: [] };

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: estado.perms,
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
  }),
}));

const CONTAGEM = {
  entrada: 3, saida: 1, analise: 12, externos: 2, aguardando_assinatura: 1,
  enviado_para_assinatura: 4, arquivados: 40, recusados: 2,
};
const caixasMock = vi.fn(() => Promise.resolve(CONTAGEM));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      // Preguiçoso: o `vi.mock` sobe para antes das declarações acima.
      processos: { ...actual.api.processos, caixas: () => caixasMock() },
    },
  };
});

async function abrir() {
  const { default: Pagina } = await import("@/app/(app)/m/protocolo/fluxo/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Pagina />
    </QueryClientProvider>,
  );
}

const passo = (key: string) => within(screen.getByTestId(`passo-${key}`));

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  estado.perms = ["processo"];
  caixasMock.mockClear();
});
afterEach(cleanup);

describe("fluxo do processo de protocolo", () => {
  it("mostra os seis passos na ordem, em três fases", async () => {
    await abrir();
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual([
      "Passo 1: Abrir o processo",
      "Passo 2: Encaminhar",
      "Passo 3: Receber ou recusar",
      "Passo 4: Analisar",
      "Passo 5: Assinar",
      "Passo 6: Arquivar",
    ]);
    for (const fase of ["Abertura", "Tramitação", "Conclusão"]) {
      expect(screen.getByRole("region", { name: `Fase: ${fase}` })).toBeInTheDocument();
    }
  });

  it("cada passo mostra a quantidade da caixa dele e leva à caixa", async () => {
    await abrir();
    await passo("receber").findByText("3 processos aqui agora");
    expect(passo("encaminhar").getByText("1 processo aqui agora")).toBeInTheDocument();
    expect(passo("analisar").getByText("12 processos aqui agora")).toBeInTheDocument();
    expect(passo("assinar").getByText("1 processo espera sua assinatura aqui agora"))
      .toBeInTheDocument();
    // Abrir não tem caixa: não inventa quantidade.
    expect(passo("abrir").queryByText(/aqui agora/)).toBeNull();

    expect(passo("receber").getByRole("link", { name: "Abrir caixa de entrada" }))
      .toHaveAttribute("href", "/m/protocolo/processos?caixa=entrada&ativos=0");
    expect(passo("assinar").getByRole("link", { name: "Abrir para assinar" }))
      .toHaveAttribute("href", "/para-assinar");
    // Protocolo não tem "sua etapa": todo operador faz todos os passos.
    expect(screen.queryByText("Sua etapa")).toBeNull();
  });

  it("recusar aparece como saída de quem recebe, e os recusados têm atalho", async () => {
    await abrir();
    const saidas = within(
      passo("receber").getByRole("list", { name: "Saídas de Receber ou recusar" }));
    expect(saidas.getByText("volta para quem enviou")).toBeInTheDocument();

    expect(await screen.findByText("2 recusados")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Abrir recusados" }))
      .toHaveAttribute("href", "/m/protocolo/processos?caixa=recusados&ativos=0");
  });

  it("quem não opera processos vê o mapa, sem quantidades nem atalhos de trabalho", async () => {
    estado.perms = [];
    await abrir();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(6);
    expect(caixasMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/aqui agora/)).toBeNull();
    expect(passo("receber").queryByRole("link")).toBeNull();
  });

  it("falha ao buscar quantidades não derruba o mapa", async () => {
    caixasMock.mockRejectedValueOnce(new Error("fora do ar"));
    await abrir();
    await screen.findByText(/Não foi possível carregar as quantidades/);
    await waitFor(() => expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(6));
  });
});

describe("o mapa aponta para caixas que existem", () => {
  it("toda caixa citada num passo está no catálogo de caixas", () => {
    const existentes = new Set(CAIXAS.map((c) => c.caixa));
    const citadas = FASES.flatMap((f) => f.passos).flatMap((p) => (p.caixa ? [p.caixa] : []));
    expect(citadas.length).toBeGreaterThan(0);
    expect(citadas.filter((c) => !existentes.has(c))).toEqual([]);
    expect(new Set(citadas).size).toBe(citadas.length);
  });
});

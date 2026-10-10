/**
 * As caixas de trabalho no menu lateral, direto no grupo "Processos".
 *
 * As oito entradas compartilham o CAMINHO (`/m/protocolo/processos`) e só a
 * query as distingue. O modo de falha que importa é o menu marcar todas como
 * abertas — ou nenhuma —, que é o que a comparação só por caminho faria.
 *
 * O outro é a promessa do número: o contador ao lado do rótulo tem de vir da
 * mesma contagem que a tela usa, e a falta dele não pode derrubar a navegação.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const onde = { pathname: "/m/protocolo/processos", busca: "" };
vi.mock("next/navigation", () => ({
  usePathname: () => onde.pathname,
  useSearchParams: () => new URLSearchParams(onde.busca),
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: true },
    perms: [],
    loading: false,
    can: () => true,
    logout: vi.fn(),
  }),
}));

const caixasMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () => Promise.resolve({ itens: [{ slug: "protocolo", nome: "Protocolo", icone: "FileText", ordem: 1 }] }),
    processos: { caixas: () => caixasMock() },
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { CAIXAS, caixaDaUrl, hrefDaCaixa } from "@/lib/caixas-processos";
import { ThemeProvider } from "@/lib/theme";

const CONTAGEM = {
  entrada: 18,
  saida: 1,
  analise: 26,
  externos: 0,
  aguardando_assinatura: 22,
  enviado_para_assinatura: 19,
  arquivados: 56,
};

window.matchMedia =
  window.matchMedia ??
  (((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia);

function renderSidebar(props: ComponentProps<typeof Sidebar>) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <Sidebar {...props} />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

/** Os links da tela de Processos no menu: "Todos os processos" e as caixas. */
async function subitens() {
  await waitFor(() => expect(screen.getByRole("link", { name: /Todos os processos/ })).toBeTruthy());
  return screen
    .getAllByRole("link")
    .filter((a) => (a.getAttribute("href") ?? "").split("?")[0] === "/m/protocolo/processos");
}

const atuais = (links: HTMLElement[]) =>
  links.filter((a) => a.getAttribute("aria-current") === "page").map((a) => a.textContent ?? "");

beforeEach(() => {
  onde.pathname = "/m/protocolo/processos";
  onde.busca = "";
  caixasMock.mockReset();
  caixasMock.mockResolvedValue(CONTAGEM);
});

describe("caixas no menu lateral", () => {
  it("'Processos' aparece UMA vez — o título do grupo, sem item repetindo o nome", async () => {
    // As caixas chegaram a ser subitens de um item "Processos" dentro do grupo
    // "Processos": o nome aparecia duas vezes, uma em cima da outra.
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await subitens();
    expect(screen.getAllByText("Processos")).toHaveLength(1);
    expect(screen.queryByRole("link", { name: "Processos" })).toBeNull();
    // E não há um nível a mais: as caixas são itens do próprio grupo.
    expect(document.getElementById("nav-sub-processos")).toBeNull();
  });

  it("'Todos os processos' e as sete caixas, na ordem", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const links = await subitens();
    expect(links.map((a) => a.getAttribute("href"))).toEqual([
      "/m/protocolo/processos",
      ...CAIXAS.map((c) => hrefDaCaixa(c.caixa)),
    ]);
    expect(links[0].textContent).toContain("Todos os processos");
  });

  it("com ?caixa=analise só a Análise é a página atual", async () => {
    onde.busca = "caixa=analise&ativos=0";
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const marcados = atuais(await subitens());
    expect(marcados).toHaveLength(1);
    expect(marcados[0]).toContain("Análise");
  });

  it("sem caixa na URL, a atual é 'Todos os processos' — e só ela", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const marcados = atuais(await subitens());
    expect(marcados).toHaveLength(1);
    expect(marcados[0]).toContain("Todos os processos");
  });

  it("filtrar DENTRO da caixa não tira a marca dela", async () => {
    // `ativos=1` e a busca vêm do formulário da tela, não do link do menu.
    onde.busca = "q=jose&caixa=entrada&ativos=1&page=2";
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const marcados = atuais(await subitens());
    expect(marcados).toHaveLength(1);
    expect(marcados[0]).toContain("Caixa de entrada");
  });

  it("no detalhe de um processo, quem fica marcado é 'Todos os processos'", async () => {
    onde.pathname = "/m/protocolo/processos/42";
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const marcados = atuais(await subitens());
    expect(marcados).toHaveLength(1);
    expect(marcados[0]).toContain("Todos os processos");
  });

  it("mostra o contador de cada caixa, com unidade para leitor de tela", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /Caixa de entrada\s*18 processos/ })).toBeTruthy(),
    );
    expect(screen.getByRole("link", { name: /Caixa de saída\s*1 processo$/ })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Externos\s*0 processos/ })).toBeTruthy();
    // "Todos os processos" não é uma caixa: não tem número.
    expect(screen.getByRole("link", { name: "Todos os processos" })).toBeTruthy();
  });

  it("se a contagem falhar, os itens continuam lá — só sem número", async () => {
    caixasMock.mockRejectedValue(new Error("fora do ar"));
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const links = await subitens();
    await waitFor(() => expect(caixasMock).toHaveBeenCalled());
    expect(links).toHaveLength(CAIXAS.length + 1);
    for (const a of links) expect(a.textContent).not.toMatch(/\d/);
  });
});

describe("caixa ↔ URL", () => {
  it("aceita só valor da lista — 'recusados' e lixo viram undefined, não 422", () => {
    expect(caixaDaUrl("entrada")).toBe("entrada");
    expect(caixaDaUrl("recusados")).toBeUndefined();
    expect(caixaDaUrl("")).toBeUndefined();
    expect(caixaDaUrl(null)).toBeUndefined();
  });

  it("o link da caixa carrega SÓ a caixa — não herda filtros em curso", () => {
    expect(hrefDaCaixa("entrada")).toBe("/m/protocolo/processos?caixa=entrada&ativos=0");
    expect(hrefDaCaixa(undefined)).toBe("/m/protocolo/processos?ativos=0");
  });

  it("hrefDaCaixa é o inverso de caixaDaUrl para toda caixa", () => {
    for (const { caixa } of CAIXAS) {
      const url = new URL(hrefDaCaixa(caixa), "http://x");
      expect(caixaDaUrl(url.searchParams.get("caixa"))).toBe(caixa);
    }
  });
});

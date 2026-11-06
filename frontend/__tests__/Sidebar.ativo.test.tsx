/**
 * O menu lateral lista TELAS, e marca uma só como a atual.
 *
 * As caixas de trabalho chegaram a ser oito itens do menu, todos com o mesmo
 * caminho (`/m/protocolo/processos?caixa=…`): o menu virava o filtro de uma
 * tela. Hoje são abas da própria tela (`AbasCaixas.test.tsx`), e o menu tem
 * um item só para ela.
 *
 * O outro modo de falha é marcar duas páginas atuais: o caminho de um item
 * casa também com as subpáginas dele, então irmãos aninhados casavam juntos
 * ("Visão geral" `/m/pagamentos` e "Dashboard" `/m/pagamentos/dashboard`).
 * Vence o mais específico.
 */
import type { ComponentProps } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const onde = { pathname: "/m/protocolo/processos", busca: "", podeInserir: true, semProtocolo: false };
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
    // Ler tudo pode; criar depende de `onde.podeInserir`.
    can: (_codigo: string, action?: string) => (action === "inserir" ? onde.podeInserir : true),
    logout: vi.fn(),
  }),
}));

const caixasMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () =>
      Promise.resolve({
        itens: [
          ...(onde.semProtocolo ? [] : [{ slug: "protocolo", nome: "Protocolo", icone: "FileText", ordem: 1 }]),
          { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
        ],
      }),
    processos: { caixas: () => caixasMock() },
  },
}));

import { Sidebar } from "@/components/Sidebar";
import { CAIXAS, caixaDaUrl, hrefDaCaixa } from "@/lib/caixas-processos";
import { ThemeProvider } from "@/lib/theme";

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

const atuais = () =>
  screen
    .getAllByRole("link")
    .filter((a) => a.getAttribute("aria-current") === "page")
    .map((a) => a.textContent ?? "");

beforeEach(() => {
  onde.pathname = "/m/protocolo/processos";
  onde.busca = "";
  onde.podeInserir = true;
  onde.semProtocolo = false;
  caixasMock.mockReset();
  window.localStorage.clear();
});

describe("ação principal do módulo", () => {
  it("o protocolo tem 'Abrir processo' no alto do menu, levando ao formulário", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    const abrir = await screen.findByRole("link", { name: "Abrir processo" });
    expect(abrir.getAttribute("href")).toBe("/m/protocolo/processos/novo");
    // Não é uma tela para navegar: não disputa a marca de página atual.
    expect(abrir.getAttribute("aria-current")).toBeNull();
  });

  it("quem só consulta (sem 'inserir') não vê o botão", async () => {
    onde.podeInserir = false;
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Caixas de trabalho" });
    expect(screen.queryByRole("link", { name: "Abrir processo" })).toBeNull();
  });

  it("no menu único o botão vale em qualquer tela — inclusive fora do Protocolo", async () => {
    onde.pathname = "/m/pagamentos";
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    expect(await screen.findByRole("link", { name: "Abrir processo" })).toBeInTheDocument();
  });

  it("prefeitura sem o Protocolo contratado não ganha botão", async () => {
    onde.pathname = "/m/pagamentos";
    onde.semProtocolo = true;
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    await screen.findByRole("link", { name: "Visão geral" });
    expect(screen.queryByRole("link", { name: "Abrir processo" })).toBeNull();
  });
});

describe("menu do protocolo — telas, não filtros", () => {
  it("a tela de processos tem UM link no menu, e nenhuma caixa vira item", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await waitFor(() => expect(screen.getByRole("link", { name: "Caixas de trabalho" })).toBeTruthy());

    const daTela = screen
      .getAllByRole("link")
      .filter((a) => (a.getAttribute("href") ?? "").split("?")[0] === "/m/protocolo/processos");
    expect(daTela).toHaveLength(1);
    expect(daTela[0].getAttribute("href")).toBe("/m/protocolo/processos");
    for (const { rotulo } of CAIXAS) {
      expect(screen.queryByRole("link", { name: new RegExp(`^${rotulo}`) })).toBeNull();
    }
  });

  it("a barra não pede a contagem das caixas — quem conta são as abas da tela", async () => {
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await waitFor(() => expect(screen.getByRole("link", { name: "Caixas de trabalho" })).toBeTruthy());
    expect(caixasMock).not.toHaveBeenCalled();
  });

  it("dentro de uma caixa, a atual continua sendo 'Caixas de trabalho' — e só ela", async () => {
    onde.busca = "caixa=analise&ativos=0";
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Caixas de trabalho"]));
  });

  it("no detalhe de um processo, a atual é 'Caixas de trabalho'", async () => {
    onde.pathname = "/m/protocolo/processos/42";
    renderSidebar({ modulo: "protocolo", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Caixas de trabalho"]));
  });
});

describe("irmãos aninhados — vence o mais específico", () => {
  it("em /m/pagamentos/dashboard, só 'Dashboard' (não 'Visão geral')", async () => {
    onde.pathname = "/m/pagamentos/dashboard";
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Dashboard"]));
  });

  it("numa etapa (aba) de Solicitações, a atual na barra é 'Solicitações'", async () => {
    // "Aguardando Gestor" virou aba de Solicitações (menu único): fora da
    // barra, quem acende é a tela que contém a aba.
    onde.pathname = "/m/pagamentos/solicitacoes/gestor";
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Solicitações"]));
  });

  it("sem irmão mais específico, o item segue aceso nas próprias subpáginas", async () => {
    onde.pathname = "/m/pagamentos/solicitacoes/123";
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Solicitações"]));
  });

  it("na raiz do módulo, a raiz", async () => {
    onde.pathname = "/m/pagamentos";
    renderSidebar({ modulo: "pagamentos", open: true, onClose: () => {} });
    await waitFor(() => expect(atuais()).toEqual(["Visão geral"]));
  });
});

describe("caixa ↔ URL", () => {
  it("aceita só valor da lista — caixa inexistente e lixo viram undefined, não 422", () => {
    expect(caixaDaUrl("entrada")).toBe("entrada");
    expect(caixaDaUrl("recusados")).toBe("recusados");
    expect(caixaDaUrl("devolvidos")).toBeUndefined();
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

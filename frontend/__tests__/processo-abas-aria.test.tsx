/**
 * Detalhe do processo — as 4 abas e o vínculo ARIA que lhes faltava.
 *
 * Esta é a tela mais usada do sistema, e era uma das seis que reimplementavam
 * `role="tablist"` à mão: sem `aria-controls`, sem `role="tabpanel"`, sem
 * navegação por setas. Quem usa leitor de tela ouvia "aba" e não encontrava o
 * painel.
 *
 * Vive num arquivo separado das outras telas migradas
 * (`__tests__/tabs-telas.test.tsx`) porque só ela precisa deste tanto de mock:
 * `useParams`, `useAuth`, e uma carga de processo com os ~20 campos que a
 * página lê. Misturar essa montagem com as telas leves faria o arquivo inteiro
 * quebrar quando qualquer um desses campos mudar de nome.
 *
 * Duas coisas que estes testes NÃO cobrem, ditas aqui para ninguém supor o
 * contrário:
 *
 *   - Aparência. A migração preserva as classes, mas asserção de classe
 *     Tailwind quebra a cada refactor sem indicar defeito. Isso é revisão
 *     visual.
 *   - O estado da aba na URL (`?tab=`). O `router.replace` está mockado, então
 *     o que se prova aqui é que a troca chama o roteador — não que o deep link
 *     sobreviva a um reload de verdade.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "42" }),
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/m/protocolo/processos/42",
}));

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: () => true }) }));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/components/ui/confirm", () => ({
  useConfirm: () => () => Promise.resolve(false),
  usePrompt: () => () => Promise.resolve(null),
  ConfirmProvider: ({ children }: { children: React.ReactNode }) => children,
}));

/** Carga mínima com todos os campos que a página lê. */
const PROCESSO = {
  id: 42,
  numero_processo: "2026/000042",
  nup: "12345.000042/2026-11",
  numero_origem: null,
  assunto: "Assunto de teste",
  tipo_processo: "Ofício",
  manifestante: "Fulano",
  manifestante_cpf_cnpj: "000.000.000-00",
  unidade_proprietaria: "Protocolo Geral",
  local_atual: "Protocolo Geral",
  data_hora_abertura: "2026-08-01T10:00:00",
  // `prazo` é `PrazoInfo` NÃO-nulo no contrato (`lib/api.ts`), e a página faz
  // `prazoBadge(prazo, ...)` direto. Passar `null` aqui derruba o render antes
  // de chegar nas abas — foi o segundo mock meu a errar o formato hoje.
  prazo: {
    status: "sem_prazo",
    prazo_servico_dias_snapshot: null,
    prazo_previsto_em: null,
    dias_restantes: null,
    dias_atraso: null,
    concluido_em: null,
  },
  corpo: "Corpo do processo",
  observacao: null,
  publico: true,
  externo: false,
  nivel_sigilo: "ostensivo",
  id_processo_pai: null,
  movimentacoes: [],
  anexos: [],
};

/**
 * Herda o módulo real e substitui só o que faz rede. Enumerar os exports à mão
 * vira caça a talharim: `lib/api.ts` tem ~4,4k linhas e exporta constantes
 * (`GRAUS_SIGILO_LEGAL`, helpers de URL) que a página consome sem passar por
 * HTTP. A primeira versão deste mock listava seis nomes e morreu no sétimo.
 */
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  // Resposta vazia que serve aos dois contratos: quem faz `.map` direto
  // (endpoints que devolvem `list[X]`) e quem lê `.items` (os `Paginated`). Um
  // array com `items`/`total` pendurados satisfaz ambos, e evita ter de saber
  // qual dos ~40 endpoints desta página usa qual.
  const vazio = () => Promise.resolve(Object.assign([] as unknown[], { items: [], total: 0 }));
  const paginado = vazio;
  const rede = new Proxy(vazio, { get: () => vazio, apply: () => vazio() });
  return {
    ...real,
    api: new Proxy(
      { processos: { get: () => Promise.resolve(PROCESSO), list: paginado } } as Record<
        string,
        unknown
      >,
      { get: (alvo, chave: string) => (chave in alvo ? alvo[chave] : rede) },
    ),
    apensamentoApi: { listarApensados: vazio, listarHistorico: vazio, desapensar: vi.fn() },
    volumesApi: { list: vazio, create: vi.fn(), update: vi.fn(), delete: vi.fn() },
    desentranhamentoApi: { desentranhar: vi.fn() },
  };
});

function montar(no: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{no}</QueryClientProvider>);
}

beforeEach(() => {
  replaceMock.mockClear();
  // jsdom não implementa scrollIntoView; componentes de foco podem chamá-lo.
  Element.prototype.scrollIntoView = vi.fn();
});

async function renderizarPagina() {
  const { default: Page } = await import("@/app/(app)/m/protocolo/processos/[id]/page");
  montar(<Page />);
  await waitFor(() => expect(screen.getAllByRole("tab").length).toBe(4));
  return screen.getAllByRole("tab");
}

describe("detalhe do processo — abas", () => {
  it("a aba ativa aponta para um painel que existe, e o painel responde", async () => {
    const tabs = await renderizarPagina();

    const ativa = tabs.find((t) => t.getAttribute("aria-selected") === "true");
    expect(ativa, "nenhuma aba marcada como ativa").toBeTruthy();

    const idPainel = ativa?.getAttribute("aria-controls");
    expect(idPainel, "aba ativa sem aria-controls").toBeTruthy();

    const painel = document.getElementById(idPainel as string);
    expect(painel, `aria-controls aponta para id inexistente: ${idPainel}`).toBeTruthy();
    expect(painel?.getAttribute("role")).toBe("tabpanel");
    // O vínculo de volta: sem ele, quem chega ao painel por outro caminho não
    // sabe de qual aba ele veio.
    expect(painel?.getAttribute("aria-labelledby")).toBe(ativa?.id);
  });

  it("aba inativa não promete um painel que não está no DOM", async () => {
    const tabs = await renderizarPagina();

    for (const tab of tabs) {
      if (tab.getAttribute("aria-selected") === "true") continue;
      const idPainel = tab.getAttribute("aria-controls");
      // Ou não anuncia nada, ou anuncia um id que resolve. O que não pode é
      // apontar para o vazio: IDREF que não resolve é violação de ARIA.
      if (idPainel) expect(document.getElementById(idPainel)).toBeTruthy();
    }
  });

  it("apenas a aba ativa está na ordem de tabulação (roving tabindex)", async () => {
    const tabs = await renderizarPagina();
    expect(tabs.filter((t) => t.getAttribute("tabindex") === "0").length).toBe(1);
  });

  it("o contador ao lado do rótulo não polui o nome acessível", async () => {
    const tabs = await renderizarPagina();
    // `Movimentações` e `Documentos` mostram um badge com a contagem. O número
    // repete o que a lista abaixo já diz, então é decorativo: `aria-hidden` no
    // badge e `nomeAcessivel` legível no lugar.
    const docs = tabs.find((t) => t.getAttribute("aria-label")?.startsWith("Documentos"));
    expect(docs?.getAttribute("aria-label")).toBe("Documentos (0)");
  });

  it("seta para a direita troca de aba pelo teclado", async () => {
    await renderizarPagina();
    const tablist = screen.getByRole("tablist");

    fireEvent.keyDown(tablist, { key: "ArrowRight" });

    // A tela guarda a aba na URL, então trocar de aba é navegar. O que se prova
    // aqui é que o teclado ACIONA a troca — antes da migração, as setas não
    // faziam absolutamente nada.
    await waitFor(() => expect(replaceMock).toHaveBeenCalled());
    expect(String(replaceMock.mock.calls[0][0])).toContain("tab=movimentacoes");
  });
});

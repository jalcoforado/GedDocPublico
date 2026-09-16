/**
 * As telas migradas para o primitivo de abas, cada uma com o vínculo ARIA que
 * lhes faltava.
 *
 * Por que testar tela por tela em vez de confiar no primitivo: o defeito nunca
 * foi o primitivo — ele sempre esteve correto e testado. O defeito era **não
 * usá-lo**. Um teste só do primitivo continuaria verde com as seis telas
 * reimplementando abas à mão ao lado, que é exatamente o estado em que o
 * repositório passou sete meses.
 *
 * Então o que estes testes travam é o USO: cada tela renderizada de verdade,
 * com a pergunta "esta aba aponta para um painel que existe?".
 *
 * Nenhum deles é sobre aparência. `variant="pill"` preserva as classes das
 * telas de pagamentos e isso não está coberto aqui — asserção de classe Tailwind
 * quebra a cada refactor sem indicar defeito real. O que cobre é a revisão
 * visual, e está dito no PR.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

// --- mocks de infraestrutura -------------------------------------------
// As telas de pagamentos e jobs falam com a API na montagem. Aqui só interessa
// a estrutura das abas, então a API devolve vazio e as telas renderizam o
// esqueleto — que é onde as abas moram.

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/",
}));

/**
 * Resposta vazia que serve aos dois contratos do repositório: os endpoints de
 * jobs devolvem `list[JobOut]` (a tela faz `.map`), os de pagamentos devolvem
 * `Paginated` (a tela lê `.items`). Um array com `items`/`total` pendurados
 * satisfaz ambos sem que o teste precise saber qual tela chama qual.
 *
 * Não é para esconder divergência de contrato: essa é assunto de
 * `backend/tests/test_guarda_contrato_paginado.py`, e aqui os dois foram
 * conferidos contra o `response_model` antes de escrever isto.
 */
function respostaVazia() {
  return Object.assign([] as unknown[], { items: [], total: 0, paginas: 0 });
}

vi.mock("@/lib/api", () => ({
  api: new Proxy(
    {},
    {
      get: () =>
        new Proxy(() => Promise.resolve(respostaVazia()), {
          get: () => () => Promise.resolve(respostaVazia()),
          apply: () => Promise.resolve(respostaVazia()),
        }),
    },
  ),
}));

/**
 * Os providers que estas telas exigem para montar. Não são detalhe do teste:
 * `useToast`/`usePrompt` lançam fora do provider, e sem eles a tela nem chega a
 * renderizar as abas.
 */
function envolver(no: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>{no}</ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * A asserção que todas as telas compartilham: cada `role="tab"` aponta, por
 * `aria-controls`, para um elemento que existe, é `role="tabpanel"` e responde
 * com `aria-labelledby` de volta.
 *
 * O vínculo de volta importa tanto quanto o de ida: sem ele, quem chega ao
 * painel por outro caminho (busca do leitor de tela, âncora) não sabe de qual
 * aba ele veio.
 */
async function conferirVinculoDeAbas(quantasAbas: number) {
  await waitFor(() => expect(screen.getAllByRole("tab").length).toBe(quantasAbas));
  const tabs = screen.getAllByRole("tab");

  for (const tab of tabs) {
    const idPainel = tab.getAttribute("aria-controls");
    const ativa = tab.getAttribute("aria-selected") === "true";

    if (!idPainel) {
      // Aba inativa cujo painel está desmontado NÃO deve anunciar
      // `aria-controls`: IDREF que não resolve é violação de ARIA — o leitor
      // promete um destino que não está no documento. Ausente é o certo aqui.
      expect(ativa, `a aba ATIVA "${tab.textContent}" tem de ter aria-controls`).toBe(false);
      continue;
    }

    const painel = document.getElementById(idPainel);
    expect(painel, `aria-controls aponta para id inexistente: ${idPainel}`).toBeTruthy();
    expect(painel?.getAttribute("role")).toBe("tabpanel");
    expect(painel?.getAttribute("aria-labelledby")).toBe(tab.id);
  }

  // A aba ativa sempre tem painel — é o mínimo que "aba" significa.
  const ativa = tabs.find((t) => t.getAttribute("aria-selected") === "true");
  expect(ativa, "nenhuma aba marcada como ativa").toBeTruthy();
  expect(ativa?.getAttribute("aria-controls"), "aba ativa sem painel").toBeTruthy();

  // Roving tabindex: exatamente uma aba na ordem de tabulação.
  expect(
    tabs.filter((t) => t.getAttribute("tabindex") === "0").length,
    "deve haver exatamente uma aba com tabindex=0",
  ).toBe(1);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("jobs em background", () => {
  it("as 2 abas apontam para painéis que existem", async () => {
    const { default: JobsPage } = await import("@/app/(app)/m/administracao/jobs/page");
    envolver(<JobsPage />);
    await conferirVinculoDeAbas(2);
  });
});

describe("autorização de pagamentos", () => {
  it("as 2 abas apontam para painéis que existem", async () => {
    const { default: Page } = await import("@/app/(app)/m/pagamentos/autorizacao/page");
    envolver(<Page />);
    await conferirVinculoDeAbas(2);
  });
});

describe("tesouraria", () => {
  it("as 3 abas apontam para painéis que existem", async () => {
    const { default: Page } = await import("@/app/(app)/m/pagamentos/tesouraria/page");
    envolver(<Page />);
    await conferirVinculoDeAbas(3);
  });
});

describe("relatórios — navegação, não abas", () => {
  it('não usa `role="tab"`: são links para outras rotas', async () => {
    const { RelatoriosNav } = await import("@/components/RelatoriosNav");
    envolver(<RelatoriosNav />);

    // A correção aqui foi TIRAR os papéis, não completá-los. O APG não admite
    // `role="tab"` em link que navega para outra página: a promessa de um
    // `tabpanel` na mesma página não pode ser cumprida.
    expect(screen.queryAllByRole("tab")).toEqual([]);
    expect(screen.queryByRole("tablist")).toBeNull();

    const nav = screen.getByRole("navigation", { name: "Tipos de relatório" });
    expect(nav).toBeTruthy();
    expect(screen.getAllByRole("link").length).toBe(3);
  });
});

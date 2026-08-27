/**
 * Abas "Dados" / "Módulos" da edição de tenant. Achado MINOR do review
 * final: a troca de aba era condicional (`aba === "dados" ? A : B`), que
 * desmonta a aba inativa — o admin marcava módulos, olhava "Dados" e
 * voltava achando as marcações perdidas, sem aviso. Passou a manter as
 * duas abas montadas o tempo todo, alternando só a visibilidade (`hidden`).
 *
 * Testa `TenantEditTabs` (components/admin/TenantEditTabs.tsx) direto, não
 * a página de rota: a página só descompacta `params` (Promise, via `use()`)
 * e delega pra cá — mesma separação que `TenantModulosTab` já usa, pelo
 * mesmo motivo (page.tsx só pode exportar nomes que o App Router reconhece).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const tenantDetalhe = vi.fn();
const tenantModulos = vi.fn();
const salvarModulos = vi.fn((_id: number, _slugs: string[]) => Promise.resolve());
vi.mock("@/lib/api", () => ({
  api: {
    admin: { tenants: { detalhe: (id: number) => tenantDetalhe(id) } },
    adminTenantModulos: (id: number) => tenantModulos(id),
    adminTenantContratarModulos: (id: number, slugs: string[]) => salvarModulos(id, slugs),
  },
}));

const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn(), warning: vi.fn() };
vi.mock("@/components/ui/toast", () => ({ useToast: () => toast }));

import { TenantEditTabs } from "@/components/admin/TenantEditTabs";

function renderTabs() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <TenantEditTabs tenantId={7} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  tenantDetalhe.mockReset();
  tenantDetalhe.mockResolvedValue({
    id: 7,
    slug: "sobral",
    nome: "Sobral",
    cnpj: null,
    plano: "basico",
    cor_primaria: null,
    limite_usuarios: null,
    limite_armazenamento_mb: null,
    modulos: ["protocolo"],
  });
  tenantModulos.mockReset();
  tenantModulos.mockResolvedValue([
    { slug: "protocolo", nome: "Protocolo", contratado: true, ativo: true, ordem: 1 },
    { slug: "frota", nome: "Frota", contratado: false, ativo: true, ordem: 3 },
  ]);
  salvarModulos.mockClear();
});

describe("edição de tenant — abas", () => {
  it("marcar um módulo e trocar de aba não perde a marcação ao voltar", async () => {
    renderTabs();

    // Aba Módulos: marca "Frota" (ainda não contratado).
    fireEvent.click(await waitFor(() => screen.getByRole("tab", { name: "Módulos" })));
    const frota = (await waitFor(() => screen.getByLabelText("Frota"))) as HTMLInputElement;
    fireEvent.click(frota);
    expect(frota.checked).toBe(true);

    // Vai para "Dados" e volta.
    fireEvent.click(screen.getByRole("tab", { name: "Dados" }));
    await waitFor(() => expect(screen.getByDisplayValue("Sobral")).toBeTruthy());
    fireEvent.click(screen.getByRole("tab", { name: "Módulos" }));

    // A marcação sobreviveu à troca — não foi resetada por desmontagem.
    const frotaDeNovo = (await waitFor(() => screen.getByLabelText("Frota"))) as HTMLInputElement;
    expect(frotaDeNovo.checked).toBe(true);
  });

  // --- Semântica ARIA (resíduo 1.0.9 da F2) -------------------------------
  //
  // Estes quatro reprovam a implementação anterior, que era `role="tablist"` +
  // `role="tab"` à mão e mais nada. Para quem usa leitor de tela, aquilo
  // anunciava "aba" sem painel associado: não dava para saber o que a aba
  // controla nem pular para o conteúdo. Nada disso quebrava tela, então
  // nenhum teste existente ficou vermelho por sete meses.

  it("cada tab aponta para o painel que controla, e o painel responde", async () => {
    renderTabs();
    const tabs = await waitFor(() => screen.getAllByRole("tab"));
    expect(tabs.length).toBe(2);

    for (const tab of tabs) {
      const idPainel = tab.getAttribute("aria-controls");
      expect(idPainel, `tab "${tab.textContent}" sem aria-controls`).toBeTruthy();

      const painel = document.getElementById(idPainel as string);
      expect(painel, `aria-controls aponta para id inexistente: ${idPainel}`).toBeTruthy();
      expect(painel?.getAttribute("role")).toBe("tabpanel");
      // O vínculo é de mão dupla — sem a volta, o leitor não sabe de qual aba
      // o painel veio quando o usuário chega nele por outro caminho.
      expect(painel?.getAttribute("aria-labelledby")).toBe(tab.id);
    }
  });

  it("apenas a aba ativa está na ordem de tabulação (roving tabindex)", async () => {
    renderTabs();
    const [dados, modulos] = await waitFor(() => screen.getAllByRole("tab"));
    expect(dados.getAttribute("tabindex")).toBe("0");
    expect(modulos.getAttribute("tabindex")).toBe("-1");
  });

  it("seta para a direita troca de aba pelo teclado", async () => {
    renderTabs();
    const tablist = await waitFor(() => screen.getByRole("tablist"));
    const [dados, modulos] = screen.getAllByRole("tab");
    expect(dados.getAttribute("aria-selected")).toBe("true");

    fireEvent.keyDown(tablist, { key: "ArrowRight" });

    await waitFor(() => expect(modulos.getAttribute("aria-selected")).toBe("true"));
    expect(dados.getAttribute("aria-selected")).toBe("false");
  });

  it("o painel oculto sai da ordem de tabulação", async () => {
    renderTabs();
    await waitFor(() => expect(screen.getByDisplayValue("Sobral")).toBeTruthy());
    const paineis = document.querySelectorAll('[role="tabpanel"]');
    expect(paineis.length).toBe(2);

    for (const painel of Array.from(paineis)) {
      const oculto = painel.hasAttribute("hidden");
      // Painel escondido com tabIndex=0 faria o Tab parar num lugar invisível.
      expect(painel.getAttribute("tabindex")).toBe(oculto ? "-1" : "0");
    }
  });

  it("aba inativa fica presente no DOM (hidden), não desmontada", async () => {
    renderTabs();
    // Campo da aba "Dados" (ativa por padrão) e o catálogo de módulos (aba
    // oculta) coexistem no DOM ao mesmo tempo.
    await waitFor(() => expect(screen.getByDisplayValue("Sobral")).toBeTruthy());
    await waitFor(() => expect(screen.getByLabelText("Frota")).toBeTruthy());
  });
});

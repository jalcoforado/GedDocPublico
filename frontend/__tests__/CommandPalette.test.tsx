/**
 * A paleta (Ctrl+K) tinha uma lista estática de rotas, sem filtro de módulo
 * nem de permissão — Ctrl+K oferecia "Processos" mesmo num tenant sem o
 * módulo protocolo contratado, o 403 que a fatia inteira existe para evitar.
 * Estes testes protegem o comportamento novo: a paleta monta a lista a
 * partir de `lib/menus`, e um item só aparece se o módulo dono estiver
 * contratado E a permissão (quando exigida) bater — os dois filtros são
 * independentes, nenhum substitui o outro.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/lib/theme", () => ({
  useTheme: () => ({ setPreference: vi.fn(), setDensity: vi.fn() }),
}));

const canMock = vi.fn((_perm: string) => true);
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ logout: vi.fn(), can: (perm: string) => canMock(perm) }),
}));

const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { modulos: () => modulosMock() },
  buscaApi: {
    global: () => Promise.resolve({ processos: [], manifestantes: [], usuarios: [] }),
  },
}));

import { CommandPalette } from "@/components/CommandPalette";

// jsdom não implementa scrollIntoView; o efeito de "rolar até o item ativo"
// dispara ao montar. Sem isso a montagem quebra antes de qualquer asserção.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

function renderPalette() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CommandPalette open onOpenChange={() => {}} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  canMock.mockReset();
  canMock.mockReturnValue(true);
  modulosMock.mockReset();
});

describe("CommandPalette — módulo e permissão", () => {
  it("não oferece item de módulo não contratado", async () => {
    modulosMock.mockResolvedValue({ itens: [{ slug: "protocolo", nome: "Protocolo", icone: null, ordem: 1 }] });
    renderPalette();

    await waitFor(() => expect(screen.getByText("Processos")).toBeTruthy());
    // Frota e administração não estão contratados — seus itens não podem
    // aparecer, mesmo que o usuário tenha permissão para tudo.
    expect(screen.queryByText("Frota Pública")).toBeNull();
    expect(screen.queryByText("Usuários")).toBeNull();
    expect(screen.queryByText("Contas a pagar")).toBeNull();
    // "comum" nunca é bloqueado por módulo.
    expect(screen.getByText("Meu perfil")).toBeTruthy();
  });

  it("não oferece item cuja permissão o usuário não tem, mesmo com o módulo contratado", async () => {
    modulosMock.mockResolvedValue({ itens: [{ slug: "protocolo", nome: "Protocolo", icone: null, ordem: 1 }] });
    canMock.mockImplementation((perm: string) => perm !== "processo");
    renderPalette();

    // "Workflows" não exige perm — aparece.
    await waitFor(() => expect(screen.getByText("Workflows")).toBeTruthy());
    // "Processos" exige perm "processo", negada — some, embora o módulo
    // protocolo esteja contratado.
    expect(screen.queryByText("Processos")).toBeNull();
    // O atalho "Novo processo" (não vem de lib/menus, é item extra) usa a
    // MESMA regra de permissão — também some.
    expect(screen.queryByText("Novo processo")).toBeNull();
    // "Novo workflow" não exige perm — continua oferecido.
    expect(screen.getByText("Novo workflow")).toBeTruthy();
  });

  it("com nenhum módulo contratado, mantém os itens transversais (comum) e os atalhos que não são de módulo", async () => {
    modulosMock.mockResolvedValue({ itens: [] });
    renderPalette();

    await waitFor(() => expect(screen.getByText("Meu perfil")).toBeTruthy());
    expect(screen.getByText("Preferências de notificações")).toBeTruthy();
    expect(screen.getByText("Início")).toBeTruthy();
    // Itens de módulo (nenhum contratado) somem.
    expect(screen.queryByText("Processos")).toBeNull();
    expect(screen.queryByText("Novo processo")).toBeNull();
    // Ações que não são navegação por módulo (preferências, conta) continuam.
    expect(screen.getByText("Sair")).toBeTruthy();
    expect(screen.getByText(/tema: claro/i)).toBeTruthy();
  });
});

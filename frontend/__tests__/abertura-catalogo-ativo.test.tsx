/**
 * SI-54 — a abertura de processo não oferece tipo nem assunto INATIVO.
 *
 * Antes, desativar um assunto no cadastro não tirava nada do Novo processo
 * nem do Balcão: `GET /assuntos` devolve os inativos (e deve, para o cadastro
 * e para os filtros de processos antigos), e as telas de abertura não os
 * separavam. O item já escolhido num rascunho continua aparecendo, para o
 * campo não ficar em branco ao reabrir.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ativosOuEscolhido } from "@/lib/catalogo-ativo";

const TIPOS = [
  { id: 1, tipo_processo: "Tributação", exige_processo_pai: false, ativo: true },
  { id: 2, tipo_processo: "Tipo Desativado", exige_processo_pai: false, ativo: false },
];
const ASSUNTOS = [
  {
    id: 10, assunto: "Parcelamento de débitos", id_tipo_processo: 1,
    exige_processo_pai: false, ativo: true, id_assunto_pai: null, nivel: 1, codigo: null,
  },
  {
    id: 11, assunto: "Assunto Desativado", id_tipo_processo: 1,
    exige_processo_pai: false, ativo: false, id_assunto_pai: null, nivel: 1, codigo: null,
  },
];

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: {
      id: 1,
      nome: "Ana",
      id_unidade_trabalho: 12,
      lotacoes: [{ id: 12, nome: "Secretaria de Obras", principal: true }],
    },
  }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      tiposProcesso: { list: () => Promise.resolve(TIPOS) },
      templatesDocumento: { list: () => Promise.resolve([]) },
    },
    organogramaApi: { tree: () => Promise.resolve([]) },
  };
});
vi.mock("@/lib/assuntos", () => ({
  useAssuntosAll: () => ({ data: ASSUNTOS, isLoading: false }),
}));
vi.mock("@/lib/manifestantes", () => ({
  useManifestantesBusca: () => ({
    options: [],
    selectedOption: null,
    onQueryChange: () => {},
    loading: false,
    selecionado: null,
  }),
}));
vi.mock("@/components/ui/rich-text-editor", () => ({ RichTextEditor: () => null }));
vi.mock("@/components/UnidadePicker", () => ({
  UnidadePicker: ({ id }: { id?: string }) => (
    <button type="button" id={id}>
      unidade
    </button>
  ),
}));

import { FormularioProcesso } from "@/components/protocolo/FormularioProcesso";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

function montar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <FormularioProcesso />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function opcoes(): string[] {
  return screen.getAllByRole("option").map((o) => o.textContent ?? "");
}

afterEach(cleanup);

describe("ativosOuEscolhido", () => {
  it("tira os inativos", () => {
    expect(ativosOuEscolhido(ASSUNTOS, "").map((a) => a.id)).toEqual([10]);
  });

  it("mantém o inativo que já está escolhido (rascunho)", () => {
    expect(ativosOuEscolhido(ASSUNTOS, 11).map((a) => a.id)).toEqual([10, 11]);
  });
});

describe("Novo processo — catálogo ativo", () => {
  it("o combo de assunto não oferece assunto inativo", async () => {
    montar();
    fireEvent.click(document.getElementById("assunto")!);
    await waitFor(() => expect(opcoes().join("|")).toContain("Parcelamento de débitos"));
    expect(opcoes().join("|")).not.toContain("Assunto Desativado");
  });

  it("o combo de tipo não oferece tipo inativo", async () => {
    montar();
    const combo = screen.getAllByRole("combobox").find((c) =>
      /Todos os tipos/.test(c.textContent ?? ""),
    )!;
    fireEvent.click(combo);
    await waitFor(() => expect(opcoes().join("|")).toContain("Tributação"));
    expect(opcoes().join("|")).not.toContain("Tipo Desativado");
  });
});

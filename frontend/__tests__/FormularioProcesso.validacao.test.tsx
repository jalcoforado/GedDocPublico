/**
 * Abertura de processo no padrão de formulário: erro sob o campo só depois
 * de tentar enviar (nunca ao abrir), foco no primeiro que falta, o status da
 * barra dizendo o que falta, e a unidade sugerida pelo NOME (antes a dica
 * mostrava "#12", o id cru).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createMock = vi.fn();

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
      tiposProcesso: { list: () => Promise.resolve([]) },
      templatesDocumento: { list: () => Promise.resolve([]) },
      processos: { ...actual.api.processos, create: (d: unknown) => createMock(d) },
    },
    organogramaApi: { tree: () => Promise.resolve([]) },
  };
});
vi.mock("@/lib/assuntos", () => ({ useAssuntosAll: () => ({ data: [], isLoading: false }) }));
vi.mock("@/lib/manifestantes", () => ({
  useManifestantesBusca: () => ({
    options: [],
    selectedOption: null,
    onQueryChange: () => {},
    loading: false,
    selecionado: null,
  }),
}));
// O editor (tiptap) e o organograma (React Flow) não são o assunto aqui.
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

beforeEach(() => {
  window.localStorage.clear();
  createMock.mockReset();
});
afterEach(cleanup);

describe("FormularioProcesso — validação", () => {
  it("ao abrir, nenhum erro: só o status do que falta", () => {
    montar();
    expect(screen.queryByText(/Escolha o manifestante/)).toBeNull();
    expect(screen.queryByText(/Escolha o assunto/)).toBeNull();
    // A unidade já vem preenchida com a do usuário, então não falta.
    expect(screen.getAllByText("Falta: Manifestante e Assunto.").length).toBeGreaterThan(0);
  });

  it("a unidade sugerida aparece pelo nome, não pelo id", () => {
    montar();
    expect(
      screen.getByText(/Preenchida com a sua unidade \(Secretaria de Obras\)/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/#12/)).toBeNull();
  });

  it("ao tentar abrir incompleto: erros sob os campos, foco no primeiro e nada enviado", () => {
    montar();
    const abrir = screen.getByRole("button", { name: /Abrir processo/ });
    // Nunca desabilitado por validação: clicar é o que mostra o que falta.
    expect(abrir).not.toBeDisabled();
    fireEvent.click(abrir);

    expect(screen.getByText(/Escolha o manifestante/)).toBeInTheDocument();
    expect(screen.getByText(/Escolha o assunto/)).toBeInTheDocument();
    expect(document.activeElement?.id).toBe("manif");
    expect(createMock).not.toHaveBeenCalled();
  });
});

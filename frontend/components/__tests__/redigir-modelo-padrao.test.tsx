/**
 * SI-53 — o modelo padrão da prefeitura já vem selecionado ao redigir. A
 * pré-seleção acontece uma vez por abertura: quem troca para "Documento em
 * branco" não é desfeito por uma nova busca da lista.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const modelo = (id: number, nome: string, padrao: boolean) => ({
  id, nome, descricao: null, id_especie_documental: null, id_unidade_trabalho: null,
  corpo_html: "<p>x</p>", placeholders_utilizados: [], ativo: true, padrao,
  id_usuario_criacao: null, criado_em: "2026-11-23T00:00:00", atualizado_em: null,
});

let LISTA = [modelo(1, "Ofício simples", false), modelo(2, "Documento padrão — Prefeitura de Itaitinga", true)];

vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      templatesDocumento: {
        list: () => Promise.resolve(LISTA),
        estiloImpressao: () =>
          Promise.resolve({ css: "", css_tela: "", cabecalho_html: "", rodape_html: "" }),
      },
      users: { getGoogleCredential: () => Promise.resolve({ connected: false, configurado: true }) },
    },
  };
});

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";

function Tela({ open, client }: { open: boolean; client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <RedigirDocumentoDialog open={open} onClose={() => {}} processoId={1} />
    </QueryClientProvider>
  );
}

const select = () => document.getElementById("minuta-template") as HTMLSelectElement;

describe("Redigir documento — modelo padrão (SI-53)", () => {
  beforeEach(() => {
    LISTA = [modelo(1, "Ofício simples", false), modelo(2, "Documento padrão — Prefeitura de Itaitinga", true)];
  });

  it("abre com o modelo padrão selecionado e marcado na lista", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<Tela open client={client} />);
    await waitFor(() => expect(select().value).toBe("2"));
    expect(screen.getByRole("option", { name: /Itaitinga \(padrão\)/ })).toBeInTheDocument();
  });

  it("sem modelo padrão, continua em Documento em branco", async () => {
    LISTA = [modelo(1, "Ofício simples", false)];
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<Tela open client={client} />);
    await screen.findByRole("option", { name: "Ofício simples" });
    expect(select().value).toBe("");
  });

  it("quem escolhe Documento em branco não é desfeito por nova busca da lista", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<Tela open client={client} />);
    await waitFor(() => expect(select().value).toBe("2"));

    fireEvent.change(select(), { target: { value: "" } });
    await client.invalidateQueries({ queryKey: ["templates-documento"] });

    await waitFor(() => expect(select().value).toBe(""));
  });

  it("reabrir o diálogo seleciona o padrão de novo", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const r = render(<Tela open client={client} />);
    await waitFor(() => expect(select().value).toBe("2"));
    fireEvent.change(select(), { target: { value: "1" } });

    r.rerender(<Tela open={false} client={client} />);
    r.rerender(<Tela open client={client} />);

    await waitFor(() => expect(select().value).toBe("2"));
  });
});

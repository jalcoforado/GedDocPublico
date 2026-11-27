/**
 * SI-72 — redigir a VERSÃO NOVA de um documento do processo. O rascunho leva
 * `id_anexo_substitui` e o "o que mudou"; o título vem do documento; se o
 * anterior foi redigido, não há escolha de modelo (o texto vem dele).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const create = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      templatesDocumento: {
        list: () => Promise.resolve([{
          id: 2, nome: "Documento padrão", descricao: null, id_especie_documental: null,
          id_unidade_trabalho: null, corpo_html: "<p>x</p>", placeholders_utilizados: [],
          ativo: true, padrao: true, id_usuario_criacao: null,
          criado_em: "2026-11-23T00:00:00", atualizado_em: null,
        }]),
        estiloImpressao: () =>
          Promise.resolve({ css: "", css_tela: "", cabecalho_html: "", rodape_html: "" }),
      },
      users: { getGoogleCredential: () => Promise.resolve({ connected: false, configurado: true }) },
      minutas: { ...real.api.minutas, create: (...a: unknown[]) => create(...a) },
    },
  };
});

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";

function abrir(redigido: boolean) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RedigirDocumentoDialog
        open
        onClose={() => {}}
        processoId={7}
        versaoDe={{ id: 33, descricao: "Parecer técnico", versao: 2, redigido }}
        motivoVersao="Corrigido o valor"
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  create.mockReset().mockResolvedValue({ id: 9, corpo_html: "<p>texto</p>", versao: 1, origem: "interno" });
});

describe("Redigir nova versão (SI-72)", () => {
  it("documento redigido: título do documento, sem modelo, e o rascunho aponta a versão", async () => {
    abrir(true);
    expect(screen.getByRole("dialog", { name: "Redigir nova versão" })).toBeInTheDocument();
    expect(screen.getByText(/entra no processo como versão/)).toHaveTextContent("versão 3");
    expect(document.getElementById("minuta-template")).toBeNull();
    expect((document.getElementById("minuta-titulo") as HTMLInputElement).value).toBe("Parecer técnico");

    await userEvent.click(screen.getByRole("button", { name: "Criar rascunho" }));
    await waitFor(() => expect(create).toHaveBeenCalled());
    const [processoId, corpo] = create.mock.calls[0];
    expect(processoId).toBe(7);
    expect(corpo).toMatchObject({
      titulo: "Parecer técnico",
      id_anexo_substitui: 33,
      motivo_versao: "Corrigido o valor",
      id_template_origem: null,
    });
  });

  it("documento enviado como arquivo: continua podendo escolher modelo", async () => {
    abrir(false);
    await waitFor(() =>
      expect((document.getElementById("minuta-template") as HTMLSelectElement).value).toBe("2"),
    );
  });
});

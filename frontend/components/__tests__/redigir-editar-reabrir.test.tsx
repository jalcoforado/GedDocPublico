/**
 * "Editar" abria o documento em branco. O diálogo fica montado e zera os
 * campos a cada abertura; com a minuta já no cache, o React Query devolve o
 * mesmo objeto e o efeito que preenchia (só em `[minutaQ.data]`) não rodava
 * de novo. Primeira abertura funcionava; reabrir — ou abrir de novo depois de
 * salvar — mostrava título e texto vazios.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const MINUTAS: Record<number, object> = {
  5: { id: 5, id_processo: 1, titulo: "Ofício 12/2026", destinatario: "Secretaria de Obras",
       origem: "interno", status: "rascunho", versao: 3, corpo_html: "<p>Texto do ofício</p>",
       google_doc_id: null, google_doc_url: null },
  8: { id: 8, id_processo: 1, titulo: "Despacho 4/2026", destinatario: null,
       origem: "interno", status: "rascunho", versao: 1, corpo_html: "<p>Outro texto</p>",
       google_doc_id: null, google_doc_url: null },
};
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      minutas: { get: (id: number) => Promise.resolve(MINUTAS[id]) },
      templatesDocumento: {
        list: () => Promise.resolve([]),
        estiloImpressao: () => Promise.resolve({ css: "", css_tela: "" }),
      },
      users: { getGoogleCredential: () => Promise.resolve({ connected: false, configurado: true }) },
    },
  };
});

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";

const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
function Tela({ open, minutaId }: { open: boolean; minutaId?: number }) {
  return (
    <QueryClientProvider client={client}>
      <RedigirDocumentoDialog open={open} onClose={() => {}} processoId={1} minutaId={minutaId} />
    </QueryClientProvider>
  );
}

describe("Editar documento", () => {
  it("reabrir o mesmo documento traz título e destinatário de volta (não em branco)", async () => {
    const r = render(<Tela open minutaId={5} />);
    expect(await screen.findByDisplayValue("Ofício 12/2026")).toBeInTheDocument();

    r.rerender(<Tela open={false} minutaId={5} />);
    r.rerender(<Tela open minutaId={5} />);

    expect(await screen.findByDisplayValue("Ofício 12/2026")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Secretaria de Obras")).toBeInTheDocument();
  });

  it("trocar de documento mostra o novo, não o anterior", async () => {
    const r = render(<Tela open={false} minutaId={5} />);
    r.rerender(<Tela open minutaId={8} />);
    expect(await screen.findByDisplayValue("Despacho 4/2026")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("Ofício 12/2026")).toBeNull();
  });
});

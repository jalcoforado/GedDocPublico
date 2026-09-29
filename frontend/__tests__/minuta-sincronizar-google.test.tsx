/**
 * Minuta de origem Google: "Sincronizar do Google Docs" traz o conteúdo
 * editado no Google para a plataforma (backend: PR #70,
 * `POST /minutas/{id}/sincronizar-google`). Antes disso a tela só dizia "é
 * editado no Google Docs" e o texto nunca voltava — backlog 2.4.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const MINUTA_GOOGLE = {
  id: 7, id_processo: 1, titulo: "Ofício ao DNIT", destinatario: null, origem: "google",
  status: "rascunho", versao: 1, corpo_html: null,
  google_doc_id: "doc-1", google_doc_url: "https://docs.google.com/document/d/doc-1/edit",
};
const get = vi.fn();
const sincronizarGoogle = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      minutas: { get: (id: number) => get(id), sincronizarGoogle: (id: number) => sincronizarGoogle(id) },
      templatesDocumento: { list: () => Promise.resolve([]) },
    },
  };
});

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";

function montar(no: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}>{no}</QueryClientProvider>);
}

beforeEach(() => {
  get.mockReset(); sincronizarGoogle.mockReset();
  toast.success.mockReset(); toast.error.mockReset(); toast.info.mockReset();
  get.mockResolvedValue(MINUTA_GOOGLE);
});

describe("minuta do Google — sincronizar de volta", () => {
  it("traz o conteúdo, mostra a prévia e avisa a versão nova", async () => {
    sincronizarGoogle.mockResolvedValue({ ...MINUTA_GOOGLE, versao: 2, corpo_html: "<p>Texto do Google</p>" });
    get.mockResolvedValueOnce(MINUTA_GOOGLE).mockResolvedValue({ ...MINUTA_GOOGLE, versao: 2, corpo_html: "<p>Texto do Google</p>" });
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={1} minutaId={7} />);

    await userEvent.click(await screen.findByRole("button", { name: /Sincronizar do Google Docs/ }));

    expect(sincronizarGoogle).toHaveBeenCalledWith(7);
    await waitFor(() => expect(screen.getByText("Texto do Google")).toBeInTheDocument());
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining("v2"));
  });

  it("sem mudança no Google, diz que nada mudou em vez de fingir versão nova", async () => {
    const jaSincronizada = { ...MINUTA_GOOGLE, versao: 3, corpo_html: "<p>Igual</p>" };
    get.mockResolvedValue(jaSincronizada);
    sincronizarGoogle.mockResolvedValue(jaSincronizada);
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={1} minutaId={7} />);

    await userEvent.click(await screen.findByRole("button", { name: /Sincronizar do Google Docs/ }));

    await waitFor(() => expect(toast.info).toHaveBeenCalledWith(expect.stringMatching(/nada mudou/i)));
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("erro do backend (ex.: Google desconectado) vira mensagem, sem quebrar a tela", async () => {
    sincronizarGoogle.mockRejectedValue(new Error("Erro ao sincronizar do Google Docs: token revogado"));
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={1} minutaId={7} />);

    await userEvent.click(await screen.findByRole("button", { name: /Sincronizar do Google Docs/ }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(expect.stringContaining("token revogado")));
    expect(screen.getByRole("button", { name: /Abrir no Google Docs/ })).toBeInTheDocument();
  });

  it("antes de sincronizar, avisa que ainda não há conteúdo trazido", async () => {
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={1} minutaId={7} />);
    expect(await screen.findByText(/ainda não foi trazido/i)).toBeInTheDocument();
  });
});

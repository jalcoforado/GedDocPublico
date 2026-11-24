/**
 * SI-32 — conectar a conta Google. A tela sabe se o servidor tem a integração
 * configurada (GET /auth/google/status) e, se não tem, explica em vez de
 * oferecer um "Conectar" que levaria a um erro; e a tela de erro volta para o
 * processo de onde a conexão partiu.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
let busca = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(busca),
  usePathname: () => "/",
}));

const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
vi.mock("@/components/ui/toast", () => ({
  useToast: () => toast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const statusGoogle = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      users: { getGoogleCredential: () => statusGoogle() },
      templatesDocumento: { list: () => Promise.resolve([]) },
    },
    // o original, para testar o mapeamento do /auth/google/status
    __real: real,
  };
});

import MinutaErrorPage from "@/app/(app)/minuta-error/page";
import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";

function montar(no: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{no}</QueryClientProvider>);
}

beforeEach(() => {
  push.mockReset();
  statusGoogle.mockReset();
  busca = "";
});

describe("Redigir documento — opção Google Docs", () => {
  it("servidor sem a integração: explica e não oferece conectar", async () => {
    statusGoogle.mockResolvedValue({ connected: false, configurado: false });
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={3} />);
    expect(await screen.findByText(/ainda não foi configurada neste servidor/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Conectar agora/ })).toBeNull();
    expect(screen.getByRole("radio", { name: /Google Docs/ })).toBeDisabled();
  });

  it("configurado e sem conta conectada: oferece conectar", async () => {
    statusGoogle.mockResolvedValue({ connected: false, configurado: true });
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={3} />);
    expect(await screen.findByRole("button", { name: /Conectar agora/ })).toBeInTheDocument();
    expect(screen.queryByText(/ainda não foi configurada/)).toBeNull();
  });

  it("conectado: a opção Google Docs fica disponível", async () => {
    statusGoogle.mockResolvedValue({ connected: true, configurado: true });
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={3} />);
    await vi.waitFor(() => expect(screen.getByRole("radio", { name: /Google Docs/ })).toBeEnabled());
  });
});

describe("api.users.getGoogleCredential", () => {
  const fetchOriginal = globalThis.fetch;
  afterEach(() => {
    globalThis.fetch = fetchOriginal;
  });

  it("lê /auth/google/status e traduz os nomes", async () => {
    const mod = (await import("@/lib/api")) as unknown as {
      __real: typeof import("@/lib/api");
    };
    globalThis.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ configurado: false, conectado: false, conectado_em: null })),
    ) as unknown as typeof fetch;
    await expect(mod.__real.api.users.getGoogleCredential()).resolves.toEqual({
      connected: false,
      configurado: false,
    });
    expect(String(vi.mocked(globalThis.fetch).mock.calls[0][0])).toContain("/auth/google/status");
  });
});

describe("tela de erro da conexão", () => {
  it("diz que não está configurado e volta para o processo de onde partiu", async () => {
    busca = "error=google_nao_configurado&processo=12";
    render(<MinutaErrorPage />);
    expect(screen.getByText(/ainda não foi configurada neste servidor/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voltar ao processo" }));
    expect(push).toHaveBeenCalledWith("/m/protocolo/processos/12?tab=documentos");
  });

  it("sem processo conhecido, volta para a lista", async () => {
    busca = "error=conta_diferente";
    render(<MinutaErrorPage />);
    expect(screen.getByText(/iniciada por outro usuário/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Voltar aos processos" }));
    expect(push).toHaveBeenCalledWith("/m/protocolo/processos");
  });
});

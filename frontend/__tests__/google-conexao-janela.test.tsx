/**
 * SI-32 — conectar a conta Google SEM sair da tela. A autorização acontece numa
 * janela à parte; a aba de origem (diálogo "Redigir documento" aberto, com o
 * que já foi digitado) não recarrega. A janela termina em `/google-conectado`,
 * avisa a aba por BroadcastChannel e se fecha.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
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
  };
});

import GoogleConectadoPage from "@/app/google-conectado/page";
import { GoogleConnectDialog } from "@/components/GoogleConnectDialog";
import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";
import { CANAL_GOOGLE } from "@/lib/google-conexao";

function montar(no: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{no}</QueryClientProvider>);
}

/** O que a janela à parte faria ao terminar. */
function janelaAvisa(aviso: { ok: boolean; erro?: string | null }) {
  const canal = new BroadcastChannel(CANAL_GOOGLE);
  canal.postMessage({ tipo: "google-conexao", ...aviso });
  canal.close();
}

const open = vi.fn();
const locationOriginal = window.location;

beforeEach(() => {
  statusGoogle.mockReset();
  toast.success.mockReset();
  open.mockReset();
  vi.spyOn(window, "open").mockImplementation(open);
});

afterEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(window, "location", { configurable: true, value: locationOriginal });
});

describe("Conectar Google Docs — janela à parte", () => {
  it("abre a autorização numa janela, com popup=1, e a aba não navega", async () => {
    open.mockReturnValue({} as Window);
    montar(<GoogleConnectDialog open onClose={() => {}} minutaId={0} processoId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Conectar Conta Google" }));
    expect(open).toHaveBeenCalledTimes(1);
    expect(open.mock.calls[0][0]).toBe("/api/v2/auth/google?minuta_id=0&processo_id=7&popup=1");
    expect(String(open.mock.calls[0][2])).toContain("popup=yes");
    expect(screen.getByRole("button", { name: "Aguardando o Google…" })).toBeDisabled();
  });

  it("janela bloqueada pelo navegador: segue na mesma aba, sem popup=1", async () => {
    open.mockReturnValue(null);
    const loc = { href: "http://localhost/m/protocolo/processos/7" };
    Object.defineProperty(window, "location", { configurable: true, value: loc });
    montar(<GoogleConnectDialog open onClose={() => {}} minutaId={0} processoId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Conectar Conta Google" }));
    expect(loc.href).toBe("/api/v2/auth/google?minuta_id=0&processo_id=7");
  });

  it("o aviso de sucesso da janela chega ao diálogo", async () => {
    open.mockReturnValue({} as Window);
    const onSuccess = vi.fn();
    montar(
      <GoogleConnectDialog open onClose={() => {}} minutaId={0} processoId={7} onSuccess={onSuccess} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Conectar Conta Google" }));
    act(() => janelaAvisa({ ok: true }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
  });

  it("o erro da janela aparece no diálogo, que continua aberto", async () => {
    open.mockReturnValue({} as Window);
    montar(<GoogleConnectDialog open onClose={() => {}} minutaId={0} processoId={7} />);
    await userEvent.click(screen.getByRole("button", { name: "Conectar Conta Google" }));
    act(() => janelaAvisa({ ok: false, erro: "access_denied" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/rejeitou o acesso/);
    expect(screen.getByRole("button", { name: "Conectar Conta Google" })).toBeEnabled();
  });

  it("redigir documento: conectou, o diálogo continua com o que foi digitado e já escolhe o Google Docs", async () => {
    open.mockReturnValue({} as Window);
    statusGoogle.mockResolvedValue({ connected: false, configurado: true });
    montar(<RedigirDocumentoDialog open onClose={() => {}} processoId={3} />);

    const titulo = await screen.findByPlaceholderText(/Despacho de encaminhamento/);
    await userEvent.type(titulo, "Parecer técnico");
    await userEvent.click(await screen.findByRole("button", { name: /Conectar agora/ }));
    await userEvent.click(screen.getByRole("button", { name: "Conectar Conta Google" }));

    statusGoogle.mockResolvedValue({ connected: true, configurado: true });
    act(() => janelaAvisa({ ok: true }));

    await waitFor(() => expect(screen.getByRole("radio", { name: /Google Docs/ })).toBeChecked());
    expect(screen.queryByRole("button", { name: "Conectar Conta Google" })).toBeNull();
    expect(screen.getByPlaceholderText(/Despacho de encaminhamento/)).toHaveValue("Parecer técnico");
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/conectada/));
  });
});

describe("/google-conectado — onde a janela termina", () => {
  function irPara(search: string, close: () => void) {
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...locationOriginal, search },
    });
    vi.spyOn(window, "close").mockImplementation(close);
  }

  it("avisa a aba de origem e se fecha", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const close = vi.fn();
    irPara("", close);
    const recebidos: unknown[] = [];
    const canal = new BroadcastChannel(CANAL_GOOGLE);
    canal.onmessage = (e) => recebidos.push(e.data);

    render(<GoogleConectadoPage />);
    expect(await screen.findByText("Conta Google conectada")).toBeInTheDocument();
    await waitFor(() => expect(recebidos).toEqual([{ tipo: "google-conexao", ok: true, erro: null }]));
    await act(async () => {
      vi.advanceTimersByTime(500);
    });
    expect(close).toHaveBeenCalled();
    canal.close();
    vi.useRealTimers();
  });

  it("repassa o erro e diz o que aconteceu", async () => {
    irPara("?erro=google_nao_configurado", vi.fn());
    const recebidos: unknown[] = [];
    const canal = new BroadcastChannel(CANAL_GOOGLE);
    canal.onmessage = (e) => recebidos.push(e.data);

    render(<GoogleConectadoPage />);
    expect(await screen.findByText("Não foi possível conectar")).toBeInTheDocument();
    expect(screen.getByText(/ainda não foi configurada neste servidor/)).toBeInTheDocument();
    await waitFor(() =>
      expect(recebidos).toEqual([{ tipo: "google-conexao", ok: false, erro: "google_nao_configurado" }]),
    );
    canal.close();
  });
});

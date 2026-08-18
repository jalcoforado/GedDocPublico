/**
 * Os três modais artesanais de processo (desentranhar anexo, apensar processo,
 * volume) eram overlays `fixed inset-0` sem role, sem foco gerenciado e sem
 * ESC. Esta fatia os migrou para o primitivo compartilhado `Dialog`
 * (components/ui/dialog). Estes testes travam o que foi ganho: role="dialog"
 * com nome acessível, foco inicial dentro do modal, fechamento por ESC com
 * restauração de foco no trigger, e as ações principais (submit → API)
 * preservadas.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: () => true }),
}));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
}));

vi.mock("@/components/ui/confirm", () => ({
  useConfirm: () => () => Promise.resolve(false),
}));

const desentranharMock = vi.fn();
const apensarMock = vi.fn();
const volumeCreateMock = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    processos: { list: () => Promise.resolve({ items: [], total: 0 }) },
  },
  desentranhamentoApi: {
    desentranhar: (...args: unknown[]) => desentranharMock(...args),
  },
  termoDesentranhamentoPdfUrl: () => "http://termo.test/desent",
  apensamentoApi: {
    listarApensados: () => Promise.resolve([]),
    listarHistorico: () => Promise.resolve([]),
    apensar: (...args: unknown[]) => apensarMock(...args),
    desapensar: vi.fn(),
  },
  termoApensamentoPdfUrl: () => "http://termo.test/apens",
  volumesApi: {
    list: () => Promise.resolve([]),
    create: (...args: unknown[]) => volumeCreateMock(...args),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import { AnexoDesentranhar } from "@/components/AnexoDesentranhar";
import { ProcessoApensados } from "@/components/ProcessoApensados";
import { ProcessoVolumes } from "@/components/ProcessoVolumes";

// jsdom não implementa scrollIntoView; o Combobox pode chamá-lo ao focar/abrir.
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? vi.fn();

function renderWithQuery(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  toastSuccess.mockReset();
  toastError.mockReset();
  desentranharMock.mockReset();
  apensarMock.mockReset();
  volumeCreateMock.mockReset();
});

describe("AnexoDesentranhar — dialog acessível", () => {
  function abrir() {
    renderWithQuery(
      <AnexoDesentranhar
        processoId={1}
        anexoProcessoId={10}
        descricaoAnexo="Ofício 12/2026"
      />,
    );
    const trigger = screen.getByRole("button", { name: /desentranhar/i });
    trigger.focus(); // o teclado/mouse real foca o trigger antes do clique
    fireEvent.click(trigger);
  }

  it("abre com role dialog e nome acessível", () => {
    abrir();
    const dialog = screen.getByRole("dialog", {
      name: "Desentranhar documento do processo",
    });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    // Texto crítico da confirmação destrutiva preservado
    expect(dialog).toHaveTextContent(/não é destruído/);
    expect(dialog).toHaveTextContent("Ofício 12/2026");
  });

  it("foca dentro do modal ao abrir (campo motivo, via autoFocus)", () => {
    abrir();
    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).toBe(screen.getByLabelText(/motivo/i));
  });

  it("ESC fecha e devolve o foco ao trigger", async () => {
    abrir();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(
      screen.getByRole("button", { name: /desentranhar/i }),
    ).toHaveFocus();
  });

  it("mantém a ação principal: submit chama a API com motivo e autoridade", async () => {
    const user = userEvent.setup();
    desentranharMock.mockResolvedValue({});
    abrir();
    const submit = within(screen.getByRole("dialog")).getByRole("button", {
      name: /^desentranhar$/i,
    });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/motivo/i), "Juntado por engano");
    await user.type(screen.getByLabelText(/autoridade/i), "Diretora, Portaria 1");
    expect(submit).toBeEnabled();
    await user.click(submit);
    await waitFor(() =>
      expect(desentranharMock).toHaveBeenCalledWith(1, 10, {
        motivo: "Juntado por engano",
        autoridade: "Diretora, Portaria 1",
      }),
    );
  });
});

describe("ProcessoApensados — dialog de apensar", () => {
  async function abrir() {
    renderWithQuery(
      <ProcessoApensados
        processoId={5}
        numeroProcesso="PROC-2026/5"
        idProcessoPai={null}
      />,
    );
    const trigger = await screen.findByRole("button", { name: /apensar outro/i });
    trigger.focus();
    fireEvent.click(trigger);
  }

  it("abre com role dialog nomeado pelo número do processo", async () => {
    await abrir();
    expect(
      screen.getByRole("dialog", { name: "Apensar PROC-2026/5" }),
    ).toBeInTheDocument();
  });

  it("foco fica dentro do modal e ESC fecha devolvendo ao trigger", async () => {
    await abrir();
    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: /apensar outro/i }),
    );
  });

  it("mantém as ações principais: Apensar (submit) e Cancelar no rodapé", async () => {
    await abrir();
    const dialog = screen.getByRole("dialog");
    const apensarBtn = screen.getByRole("button", { name: /^apensar$/i });
    expect(dialog.contains(apensarBtn)).toBe(true);
    // Sem processo principal escolhido, submissão fica bloqueada
    expect(apensarBtn).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /cancelar/i }));
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
  });
});

describe("ProcessoVolumes — dialog de volume", () => {
  async function abrir() {
    renderWithQuery(<ProcessoVolumes processoId={7} />);
    const trigger = await screen.findByRole("button", { name: /novo volume/i });
    trigger.focus();
    fireEvent.click(trigger);
  }

  it("abre com role dialog e nome acessível", async () => {
    await abrir();
    const dialog = screen.getByRole("dialog", { name: "Novo volume" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("ESC fecha e devolve o foco ao trigger", async () => {
    await abrir();
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
    );
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: /novo volume/i }),
    );
  });

  it("mantém a ação principal: Criar submete e chama a API", async () => {
    const user = userEvent.setup();
    volumeCreateMock.mockResolvedValue({});
    await abrir();
    await user.click(screen.getByRole("button", { name: /^criar$/i }));
    await waitFor(() =>
      expect(volumeCreateMock).toHaveBeenCalledWith(7, {
        numero: 1,
        pagina_inicial: null,
        pagina_final: null,
        observacao: null,
      }),
    );
  });
});

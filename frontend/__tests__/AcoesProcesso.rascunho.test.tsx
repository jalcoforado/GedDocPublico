/**
 * SI-16 — ações do rascunho, na barra do topo do processo: editar, abrir,
 * encaminhar (que também abre) e excluir. Receber, recusar, cancelar e
 * arquivar não se aplicam a rascunho.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const abrirMock = vi.fn((_id: number) => Promise.resolve({ id: 77, numero_processo: "2026/000077" }));
const excluirMock = vi.fn((_id: number) => Promise.resolve(undefined));
const push = vi.fn();
let permitido = true;

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      processos: {
        ...actual.api.processos,
        abrirRascunho: (id: number) => abrirMock(id),
        excluirRascunho: (id: number) => excluirMock(id),
      },
    },
  };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: () => permitido }) }));
vi.mock("@/components/ArquivarDialog", () => ({ ArquivarDialog: () => null }));

import { AcoesProcesso } from "@/components/AcoesProcesso";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";
import type { ProcessoDetail } from "@/lib/api";

function processo(extra: Partial<ProcessoDetail> = {}): ProcessoDetail {
  return {
    id: 77,
    numero_processo: null,
    situacao: "rascunho",
    ativo: true,
    movimentacoes: [],
    ...extra,
  } as unknown as ProcessoDetail;
}

function montar(p: ProcessoDetail = processo()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <AcoesProcesso processo={p} />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** O botão do diálogo de confirmação, não o da barra, que tem o mesmo nome. */
function confirmarNoDialogo(nome: string) {
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: nome }));
}

beforeEach(() => {
  permitido = true;
  abrirMock.mockClear();
  excluirMock.mockClear();
  push.mockClear();
});
afterEach(cleanup);

describe("ações do rascunho (SI-16)", () => {
  it("oferece editar, abrir, encaminhar e excluir — e nada de tramitação", () => {
    montar();
    expect(screen.getByRole("link", { name: /Editar/ })).toHaveAttribute(
      "href",
      "/m/protocolo/processos/77/editar",
    );
    expect(screen.getByRole("button", { name: /Abrir processo/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Encaminhar/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Excluir rascunho/ })).toBeEnabled();
    for (const nome of ["Receber", "Recusar", "Cancelar encaminhamento", "Arquivar"]) {
      expect(screen.queryByRole("button", { name: nome })).toBeNull();
    }
  });

  it("abrir pede confirmação e chama o servidor", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Abrir processo/ }));
    expect(await screen.findByText(/ganha número agora/)).toBeInTheDocument();
    confirmarNoDialogo("Abrir processo");
    await waitFor(() => expect(abrirMock).toHaveBeenCalledWith(77));
  });

  it("excluir pede confirmação, chama o servidor e volta para os rascunhos", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Excluir rascunho/ }));
    await screen.findByRole("dialog");
    confirmarNoDialogo("Excluir rascunho");
    await waitFor(() => expect(excluirMock).toHaveBeenCalledWith(77));
    await waitFor(() =>
      expect(push).toHaveBeenCalledWith("/m/protocolo/processos?situacao=rascunho"),
    );
  });

  it("encaminhar um rascunho avisa que ele vai ganhar número", async () => {
    montar();
    fireEvent.click(screen.getByRole("button", { name: /Encaminhar/ }));
    expect(await screen.findByText(/Encaminhar abre o processo/)).toBeInTheDocument();
    // O título não diz mais "Encaminhar processo null".
    expect(screen.getByText("Encaminhar rascunho")).toBeInTheDocument();
  });

  it("sem permissão, a barra não oferece os atos", () => {
    permitido = false;
    montar();
    expect(screen.queryByRole("link", { name: /Editar/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Abrir processo/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Excluir rascunho/ })).toBeNull();
  });

  it("processo aberto mostra a tramitação, não as ações de rascunho", () => {
    montar(processo({ situacao: "protocolado", numero_processo: "2026/000077" }));
    expect(screen.getByRole("button", { name: "Encaminhar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Arquivar" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Editar/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Excluir rascunho/ })).toBeNull();
  });
});

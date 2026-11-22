/**
 * SI-62 — despacho sem encaminhar, na tela.
 *
 * - O botão "Registrar despacho" só é oferecido onde o servidor aceita (não
 *   em trânsito, não arquivado). A barreira de verdade é o servidor
 *   (`backend/tests/test_despacho_sem_encaminhar.py`); aqui é UX.
 * - O rascunho é salvo como minuta de finalidade "despacho".
 * - "Concluir e assinar" pede a senha e manda o rascunho com ela; a mensagem
 *   de recusa do servidor aparece no diálogo.
 * - Na aba Documentos, o rascunho de despacho continua pelo diálogo do
 *   despacho, nunca pelo "Finalizar" comum.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const createMock = vi.fn((_p: number, d: { corpo_html?: string | null }) =>
  Promise.resolve({ id: 9, versao: 1, corpo_html: d.corpo_html }),
);
const updateMock = vi.fn((id: number) => Promise.resolve({ id, versao: 2 }));
const concluirMock = vi.fn((_id: number, _senha: string, _arquivos: File[]) =>
  Promise.resolve({ id: 1, id_movimentacao: 2, id_anexo: 3 }),
);
const listMock = vi.fn((_p: number) => Promise.resolve([] as unknown[]));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      minutas: {
        ...actual.api.minutas,
        list: (p: number) => listMock(p),
        get: (id: number) => Promise.resolve({ id, versao: 1, corpo_html: "<p>Rascunho antigo</p>" }),
        create: (p: number, d: { corpo_html?: string | null }) => createMock(p, d),
        update: (id: number) => updateMock(id),
        concluirDespacho: (id: number, senha: string, arquivos: File[]) =>
          concluirMock(id, senha, arquivos),
      },
    },
  };
});
// O tiptap não roda no jsdom; o que se testa aqui é o fluxo, não o editor.
vi.mock("@/components/ui/rich-text-editor", () => ({
  RichTextEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="Texto do despacho (editor)" value={value}
      onChange={(e) => onChange(e.target.value)} />
  ),
}));
vi.mock("@/components/ArquivarDialog", () => ({ ArquivarDialog: () => null }));
vi.mock("@/components/RedigirDocumentoDialog", () => ({ RedigirDocumentoDialog: () => null }));

import { AcoesProcesso } from "@/components/AcoesProcesso";
import { MinutasProcesso } from "@/components/MinutasProcesso";
import { RegistrarDespachoDialog } from "@/components/protocolo/RegistrarDespachoDialog";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";
import type { ProcessoDetail } from "@/lib/api";

function envolver(ui: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>{ui}</ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function processo(movimentacoes: unknown[] = []): ProcessoDetail {
  return {
    id: 77, numero_processo: "2026/000077", situacao: "protocolado", ativo: true,
    movimentacoes,
  } as unknown as ProcessoDetail;
}

const EM_TRANSITO = {
  id: 1, acao_flag: "ENCAMINHAMENTO",
  encaminhamento: { id: 9, unidade_destino: "Procuradoria", recebido: false, cancelado: false },
};
const ARQUIVADO = { id: 2, acao_flag: "ARQUIVAMENTO" };

beforeEach(() => {
  createMock.mockClear();
  updateMock.mockClear();
  concluirMock.mockClear();
  listMock.mockReset();
  listMock.mockResolvedValue([]);
});
afterEach(cleanup);

describe("botão Registrar despacho", () => {
  it("é oferecido com o processo na mesa", () => {
    envolver(<AcoesProcesso processo={processo()} />);
    expect(screen.getByRole("button", { name: "Registrar despacho" })).toBeEnabled();
  });

  it("não é oferecido em trânsito nem arquivado", () => {
    envolver(<AcoesProcesso processo={processo([EM_TRANSITO])} />);
    expect(screen.getByRole("button", { name: "Registrar despacho" })).toBeDisabled();
    cleanup();
    envolver(<AcoesProcesso processo={processo([ARQUIVADO])} />);
    expect(screen.getByRole("button", { name: "Registrar despacho" })).toBeDisabled();
  });
});

describe("diálogo do despacho", () => {
  function escrever(texto: string) {
    fireEvent.change(screen.getByLabelText("Texto do despacho (editor)"), {
      target: { value: texto },
    });
  }

  it("vazio não salva nem conclui", () => {
    envolver(<RegistrarDespachoDialog open onClose={() => {}} processoId={77} />);
    expect(screen.getByRole("button", { name: "Salvar rascunho" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Concluir e assinar/ })).toBeDisabled();
  });

  it("salvar rascunho cria minuta de finalidade despacho", async () => {
    envolver(<RegistrarDespachoDialog open onClose={() => {}} processoId={77} />);
    escrever("<p>Aguardando parecer jurídico.</p>");
    fireEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(createMock.mock.calls[0][0]).toBe(77);
    expect(createMock.mock.calls[0][1]).toMatchObject({
      finalidade: "despacho", corpo_html: "<p>Aguardando parecer jurídico.</p>",
    });
  });

  it("concluir pede a senha e manda o despacho com ela", async () => {
    const onClose = vi.fn();
    envolver(<RegistrarDespachoDialog open onClose={onClose} processoId={77} />);
    escrever("<p>Aguardando parecer jurídico.</p>");
    fireEvent.click(screen.getByRole("button", { name: /Concluir e assinar/ }));
    const senha = await screen.findByLabelText("Sua senha");
    expect(screen.getByRole("button", { name: "Assinar e registrar" })).toBeDisabled();
    fireEvent.change(senha, { target: { value: "minha-senha" } });
    fireEvent.click(screen.getByRole("button", { name: "Assinar e registrar" }));
    await waitFor(() => expect(concluirMock).toHaveBeenCalled());
    expect(concluirMock.mock.calls[0][0]).toBe(9);
    expect(concluirMock.mock.calls[0][1]).toBe("minha-senha");
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("a recusa do servidor aparece no diálogo e a senha é apagada", async () => {
    concluirMock.mockRejectedValueOnce(
      new Error("Só quem é lotado na unidade onde o processo está pode despachar nele."),
    );
    const onClose = vi.fn();
    envolver(<RegistrarDespachoDialog open onClose={onClose} processoId={77} />);
    escrever("<p>Texto</p>");
    fireEvent.click(screen.getByRole("button", { name: /Concluir e assinar/ }));
    const senha = await screen.findByLabelText("Sua senha");
    fireEvent.change(senha, { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Assinar e registrar" }));
    expect(await screen.findByText(/Só quem é lotado na unidade/)).toBeInTheDocument();
    expect(screen.getByLabelText("Sua senha")).toHaveValue("");
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("aba Documentos", () => {
  it("rascunho de despacho continua pelo diálogo do despacho, não pelo Finalizar", async () => {
    listMock.mockResolvedValue([
      { id: 9, id_processo: 77, titulo: "Despacho", origem: "interno", finalidade: "despacho",
        status: "rascunho", versao: 1, id_anexo_final: null, id_usuario_criacao: 1,
        criado_em: "2026-11-22T10:00:00", atualizado_em: null },
      { id: 10, id_processo: 77, titulo: "Ofício", origem: "interno", finalidade: "documento",
        status: "rascunho", versao: 1, id_anexo_final: null, id_usuario_criacao: 1,
        criado_em: "2026-11-22T10:00:00", atualizado_em: null },
    ]);
    envolver(<MinutasProcesso processo={processo()} />);
    expect(await screen.findByRole("button", { name: /Continuar despacho/ })).toBeInTheDocument();
    expect(screen.getByText(/só você vê até assinar/)).toBeInTheDocument();
    // O "Finalizar" comum existe só para o ofício.
    expect(screen.getAllByRole("button", { name: /Finalizar/ })).toHaveLength(1);
  });
});

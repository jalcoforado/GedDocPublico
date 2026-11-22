/**
 * SI-62 — despacho sem encaminhar, na tela.
 *
 * - O botão "Registrar despacho" só é oferecido onde o servidor aceita (não
 *   em trânsito, não arquivado). A barreira de verdade é o servidor
 *   (`backend/tests/test_despacho_sem_encaminhar.py`); aqui é UX.
 * - O despacho é escrito no mesmo "Redigir documento" (modelos e
 *   pré-visualização), em modo despacho: título "Despacho", sem Google Docs,
 *   rascunho com finalidade "despacho".
 * - "Concluir e assinar…" salva e leva ao passo de assinar: senha e arquivos
 *   vão juntos; a recusa do servidor aparece no diálogo.
 * - O "Redigir documento" comum continua igual.
 * - Na aba Documentos, o rascunho de despacho continua pelo fluxo do
 *   despacho, nunca pelo "Finalizar" comum.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const RASCUNHO = { id: 9, titulo: "Despacho", destinatario: null, origem: "interno",
  finalidade: "despacho", status: "rascunho", versao: 1,
  corpo_html: "<p>Aguardando parecer jurídico.</p>" };

const getMock = vi.fn((id: number) => Promise.resolve({ ...RASCUNHO, id }));
const createMock = vi.fn((_p: number, _d: Record<string, unknown>) =>
  Promise.resolve({ ...RASCUNHO, corpo_html: "" }),
);
const updateMock = vi.fn((id: number, _d: Record<string, unknown>) =>
  Promise.resolve({ ...RASCUNHO, id, versao: 2 }),
);
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
      users: {
        ...actual.api.users,
        getGoogleCredential: () => Promise.resolve({ connected: true, configurado: true }),
      },
      templatesDocumento: {
        ...actual.api.templatesDocumento,
        list: () => Promise.resolve([{ id: 4, nome: "Despacho padrão" }]),
      },
      minutas: {
        ...actual.api.minutas,
        list: (p: number) => listMock(p),
        get: (id: number) => getMock(id),
        create: (p: number, d: Record<string, unknown>) => createMock(p, d),
        update: (id: number, d: Record<string, unknown>) => updateMock(id, d),
        concluirDespacho: (id: number, senha: string, arquivos: File[]) =>
          concluirMock(id, senha, arquivos),
      },
    },
  };
});
// O tiptap não roda no jsdom; o que se testa aqui é o fluxo, não o editor.
vi.mock("@/components/ui/rich-text-editor", () => ({
  RichTextEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="Editor do documento" value={value}
      onChange={(e) => onChange(e.target.value)} />
  ),
}));
vi.mock("@/components/PreVisualizacaoDocumento", () => ({
  PreVisualizacaoDocumento: ({ corpoHtml }: { corpoHtml: string }) => (
    <div data-testid="previa">{corpoHtml}</div>
  ),
}));
vi.mock("@/components/GoogleConnectDialog", () => ({ GoogleConnectDialog: () => null }));
vi.mock("@/components/ArquivarDialog", () => ({ ArquivarDialog: () => null }));
// A barra de ações confere permissões (desarquivar, cancelar recebimento).
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: () => true, user: { id: 1 } }) }));

import { AcoesProcesso } from "@/components/AcoesProcesso";
import { MinutasProcesso } from "@/components/MinutasProcesso";
import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";
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

function processo(movimentacoes: unknown[] = [], arquivado = false): ProcessoDetail {
  return {
    id: 77, numero_processo: "2026/000077", situacao: "protocolado", ativo: true,
    movimentacoes, anexos: [], arquivado,
  } as unknown as ProcessoDetail;
}

const EM_TRANSITO = {
  id: 1, acao_flag: "ENCAMINHAMENTO",
  encaminhamento: { id: 9, unidade_destino: "Procuradoria", recebido: false, cancelado: false },
};
const ARQUIVADO = { id: 2, acao_flag: "ARQUIVAMENTO" };

beforeEach(() => {
  for (const m of [getMock, createMock, updateMock, concluirMock]) m.mockClear();
  getMock.mockImplementation((id: number) => Promise.resolve({ ...RASCUNHO, id }));
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
    envolver(<AcoesProcesso processo={processo([ARQUIVADO], true)} />);
    expect(screen.getByRole("button", { name: "Registrar despacho" })).toBeDisabled();
  });
});

describe("escrever o despacho no Redigir documento", () => {
  it("começa com o título Despacho, modelos e sem Google Docs", async () => {
    envolver(<RegistrarDespachoDialog open onClose={() => {}} processoId={77} />);
    expect(screen.getByRole("dialog", { name: /Registrar despacho/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Título do documento/)).toHaveValue("Despacho");
    expect(await screen.findByRole("option", { name: "Despacho padrão" })).toBeInTheDocument();
    expect(screen.queryByText("Google Docs")).toBeNull();
  });

  it("criar o rascunho manda finalidade despacho, no editor do sistema", async () => {
    envolver(<RegistrarDespachoDialog open onClose={() => {}} processoId={77} />);
    fireEvent.click(screen.getByRole("button", { name: "Criar rascunho" }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(createMock.mock.calls[0][0]).toBe(77);
    expect(createMock.mock.calls[0][1]).toMatchObject({
      titulo: "Despacho", finalidade: "despacho", origem: "interno",
    });
  });

  it("despacho vazio não vai para assinatura", async () => {
    getMock.mockImplementation((id: number) => Promise.resolve({ ...RASCUNHO, id, corpo_html: "<p></p>" }));
    envolver(<RegistrarDespachoDialog open onClose={() => {}} processoId={77} minutaId={9} />);
    await screen.findByLabelText("Editor do documento");
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Concluir e assinar/ })).toBeDisabled(),
    );
  });
});

describe("assinar o despacho", () => {
  async function irParaAssinar() {
    envolver(<RegistrarDespachoDialog open onClose={onClose} processoId={77} minutaId={9} />);
    const editor = await screen.findByLabelText("Editor do documento");
    await waitFor(() => expect(editor).toHaveValue("<p>Aguardando parecer jurídico.</p>"));
    fireEvent.click(screen.getByRole("button", { name: /Concluir e assinar/ }));
    return screen.findByLabelText("Sua senha");
  }
  const onClose = vi.fn();
  beforeEach(() => onClose.mockClear());

  it("salva o texto, mostra a prévia e manda senha e arquivos", async () => {
    const senha = await irParaAssinar();
    expect(updateMock).toHaveBeenCalled();
    expect(updateMock.mock.calls[0][1]).toMatchObject({ corpo_html: "<p>Aguardando parecer jurídico.</p>" });
    expect(await screen.findByTestId("previa")).toHaveTextContent("Aguardando parecer jurídico.");
    expect(screen.getByRole("button", { name: "Assinar e registrar" })).toBeDisabled();
    const arquivo = new File(["x"], "vistoria.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/Arquivos que acompanham o despacho/), {
      target: { files: [arquivo] },
    });
    expect(screen.getByRole("list", { name: "Arquivos escolhidos" })).toHaveTextContent("vistoria.txt");
    fireEvent.change(senha, { target: { value: "minha-senha" } });
    fireEvent.click(screen.getByRole("button", { name: "Assinar e registrar" }));
    await waitFor(() => expect(concluirMock).toHaveBeenCalled());
    expect(concluirMock.mock.calls[0][0]).toBe(9);
    expect(concluirMock.mock.calls[0][1]).toBe("minha-senha");
    expect(concluirMock.mock.calls[0][2].map((f) => f.name)).toEqual(["vistoria.txt"]);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it("a recusa do servidor aparece no diálogo e a senha é apagada", async () => {
    concluirMock.mockRejectedValueOnce(
      new Error("Só quem é lotado na unidade onde o processo está pode despachar nele."),
    );
    const senha = await irParaAssinar();
    fireEvent.change(senha, { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Assinar e registrar" }));
    expect(await screen.findByText(/Só quem é lotado na unidade/)).toBeInTheDocument();
    expect(screen.getByLabelText("Sua senha")).toHaveValue("");
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("Redigir documento comum", () => {
  it("continua com Google Docs e sem Concluir e assinar", async () => {
    envolver(<RedigirDocumentoDialog open onClose={() => {}} processoId={77} />);
    expect(screen.getByRole("dialog", { name: /Redigir documento/ })).toBeInTheDocument();
    expect(screen.getByLabelText(/Título do documento/)).toHaveValue("");
    expect(await screen.findByText("Google Docs")).toBeInTheDocument();
  });

  it("editando um documento comum, não há Concluir e assinar", async () => {
    getMock.mockImplementation((id: number) =>
      Promise.resolve({ ...RASCUNHO, id, titulo: "Ofício", finalidade: "documento" }),
    );
    envolver(<RedigirDocumentoDialog open onClose={() => {}} processoId={77} minutaId={10} />);
    await screen.findByLabelText("Editor do documento");
    expect(screen.getByRole("button", { name: /Salvar rascunho/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Concluir e assinar/ })).toBeNull();
  });
});

describe("aba Documentos", () => {
  it("rascunho de despacho continua pelo fluxo do despacho, não pelo Finalizar", async () => {
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

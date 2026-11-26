/**
 * SI-67 — editor com "Modelos de documentos" a qualquer momento, no "Redigir
 * documento" e no despacho.
 *
 * - O botão abre a lista de modelos; escolher um com texto na folha AVISA que
 *   o texto será substituído, e só troca depois de confirmar.
 * - Alteração não salva é gravada antes da troca (o texto substituído fica no
 *   histórico) e a troca usa a versão devolvida por essa gravação.
 * - Documento vazio troca direto, sem aviso.
 * - Fechar com alteração não salva pergunta; sem alteração, fecha direto.
 * - Escape com a lista de modelos aberta fecha só a lista, não o editor.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const RASCUNHO = {
  id: 9, id_processo: 77, id_template_origem: null, titulo: "Ofício 3/2026", destinatario: null,
  origem: "interno", finalidade: "documento", status: "rascunho", versao: 2,
  corpo_html: "<p>Texto antigo</p>", google_doc_id: null, google_doc_url: null,
};

const getMock = vi.fn((id: number) => Promise.resolve({ ...RASCUNHO, id }));
const updateMock = vi.fn((id: number, d: Record<string, unknown>) =>
  Promise.resolve({ ...RASCUNHO, id, corpo_html: d.corpo_html as string, versao: 3 }),
);
const aplicarMock = vi.fn((id: number, d: Record<string, unknown>) =>
  Promise.resolve({
    ...RASCUNHO, id, id_template_origem: d.id_template, corpo_html: "<p>Corpo do modelo</p>",
    versao: ((d.versao as number) ?? 2) + 1,
  }),
);

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      users: {
        ...actual.api.users,
        getGoogleCredential: () => Promise.resolve({ connected: false, configurado: false }),
      },
      templatesDocumento: {
        ...actual.api.templatesDocumento,
        list: () =>
          Promise.resolve([
            { id: 4, nome: "Comunicação interna", descricao: null, padrao: true },
            { id: 5, nome: "Ofício simples", descricao: "Para outros órgãos", padrao: false },
          ]),
        estiloImpressao: () =>
          Promise.resolve({ css: "", css_tela: "", cabecalho_html: "", rodape_html: "" }),
      },
      minutas: {
        ...actual.api.minutas,
        get: (id: number) => getMock(id),
        update: (id: number, d: Record<string, unknown>) => updateMock(id, d),
        aplicarModelo: (id: number, d: Record<string, unknown>) => aplicarMock(id, d),
      },
    },
  };
});
// O tiptap não roda no jsdom; o que se testa aqui é o fluxo, não o editor.
vi.mock("@/components/ui/rich-text-editor", () => ({
  RichTextEditor: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea aria-label="Editor do documento" value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));
vi.mock("@/components/PreVisualizacaoDocumento", () => ({
  PreVisualizacaoDocumento: () => null,
}));
vi.mock("@/components/GoogleConnectDialog", () => ({ GoogleConnectDialog: () => null }));

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";
import { ToastProvider } from "@/components/ui/toast";

const onClose = vi.fn();

function abrir(props: { finalidade?: "documento" | "despacho" } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RedigirDocumentoDialog open onClose={onClose} processoId={77} minutaId={9} {...props} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function editorCarregado(corpo = "<p>Texto antigo</p>") {
  const editor = await screen.findByLabelText("Editor do documento");
  await waitFor(() => expect(editor).toHaveValue(corpo));
  return editor;
}

async function escolherNaLista(nome: string) {
  fireEvent.click(screen.getByRole("button", { name: /Modelos de documentos/ }));
  const lista = await screen.findByRole("dialog", { name: "Modelos de documentos" });
  fireEvent.click(await within(lista).findByRole("button", { name: new RegExp(nome) }));
}

beforeEach(() => {
  for (const m of [getMock, updateMock, aplicarMock, onClose]) m.mockClear();
  getMock.mockImplementation((id: number) => Promise.resolve({ ...RASCUNHO, id }));
});
afterEach(cleanup);

describe("Modelos de documentos no editor", () => {
  it("a lista mostra os modelos, o padrão primeiro, e busca sem acento", async () => {
    abrir();
    await editorCarregado();
    fireEvent.click(screen.getByRole("button", { name: /Modelos de documentos/ }));
    const lista = await screen.findByRole("dialog", { name: "Modelos de documentos" });
    const itens = await within(lista).findAllByRole("button", { name: /Comunicação|Ofício|branco/ });
    expect(itens.map((b) => b.textContent)).toEqual([
      "Documento em branco",
      expect.stringContaining("Comunicação interna"),
      expect.stringContaining("Ofício simples"),
    ]);
    fireEvent.change(within(lista).getByLabelText("Buscar modelo"), { target: { value: "oficio" } });
    expect(within(lista).queryByRole("button", { name: /Comunicação interna/ })).toBeNull();
    expect(within(lista).getByRole("button", { name: /Ofício simples/ })).toBeInTheDocument();
  });

  it("com texto na folha, avisa antes e só troca depois de confirmar", async () => {
    abrir();
    const editor = await editorCarregado();
    await escolherNaLista("Ofício simples");

    const aviso = await screen.findByRole("dialog", { name: "Trocar o modelo?" });
    expect(aviso).toHaveTextContent('O texto atual será substituído pelo modelo "Ofício simples"');
    expect(aplicarMock).not.toHaveBeenCalled();

    fireEvent.click(within(aviso).getByRole("button", { name: "Substituir o texto" }));
    await waitFor(() => expect(aplicarMock).toHaveBeenCalled());
    expect(aplicarMock.mock.calls[0]).toEqual([9, { id_template: 5, destinatario: null, versao: 2 }]);
    expect(updateMock).not.toHaveBeenCalled(); // nada a salvar antes
    await waitFor(() => expect(editor).toHaveValue("<p>Corpo do modelo</p>"));
  });

  it("cancelar o aviso não troca nada", async () => {
    abrir();
    const editor = await editorCarregado();
    await escolherNaLista("Comunicação interna");
    const aviso = await screen.findByRole("dialog", { name: "Trocar o modelo?" });
    fireEvent.click(within(aviso).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Trocar o modelo?" })).toBeNull());
    expect(aplicarMock).not.toHaveBeenCalled();
    expect(editor).toHaveValue("<p>Texto antigo</p>");
  });

  it("alteração não salva é gravada antes da troca, e a troca usa a versão nova", async () => {
    abrir();
    const editor = await editorCarregado();
    fireEvent.change(editor, { target: { value: "<p>Escrevi mais coisa</p>" } });
    await escolherNaLista("Comunicação interna");
    const aviso = await screen.findByRole("dialog", { name: "Trocar o modelo?" });
    expect(aviso).toHaveTextContent("inclusive o que ainda não foi salvo");
    fireEvent.click(within(aviso).getByRole("button", { name: "Substituir o texto" }));

    await waitFor(() => expect(aplicarMock).toHaveBeenCalled());
    expect(updateMock.mock.calls[0][1]).toMatchObject({ corpo_html: "<p>Escrevi mais coisa</p>", versao: 2 });
    expect(aplicarMock.mock.calls[0][1]).toMatchObject({ id_template: 4, versao: 3 });
    await waitFor(() => expect(editor).toHaveValue("<p>Corpo do modelo</p>"));
  });

  it("documento vazio troca direto, sem aviso", async () => {
    getMock.mockImplementation((id: number) => Promise.resolve({ ...RASCUNHO, id, corpo_html: "" }));
    abrir();
    await editorCarregado("");
    await escolherNaLista("Comunicação interna");
    await waitFor(() => expect(aplicarMock).toHaveBeenCalled());
    expect(screen.queryByRole("dialog", { name: "Trocar o modelo?" })).toBeNull();
  });

  it("também no despacho: o mesmo editor, com Modelos de documentos e Concluir e assinar", async () => {
    getMock.mockImplementation((id: number) =>
      Promise.resolve({ ...RASCUNHO, id, titulo: "Despacho", finalidade: "despacho" }),
    );
    abrir({ finalidade: "despacho" });
    await editorCarregado();
    expect(screen.getByRole("button", { name: /Modelos de documentos/ })).toBeEnabled();
    expect(screen.getByRole("button", { name: /Concluir e assinar/ })).toBeEnabled();
    await escolherNaLista("Comunicação interna");
    fireEvent.click(
      within(await screen.findByRole("dialog", { name: "Trocar o modelo?" })).getByRole("button", {
        name: "Substituir o texto",
      }),
    );
    await waitFor(() => expect(aplicarMock).toHaveBeenCalled());
  });

  it("Escape com a lista aberta fecha só a lista, não o editor", async () => {
    abrir();
    await editorCarregado();
    fireEvent.click(screen.getByRole("button", { name: /Modelos de documentos/ }));
    await screen.findByRole("dialog", { name: "Modelos de documentos" });
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() =>
      expect(screen.queryByRole("dialog", { name: "Modelos de documentos" })).toBeNull(),
    );
    expect(screen.getByLabelText("Editor do documento")).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe("fechar o editor", () => {
  it("sem alteração, fecha direto", async () => {
    abrir();
    await editorCarregado();
    fireEvent.click(screen.getAllByRole("button", { name: "Fechar" })[0]);
    expect(onClose).toHaveBeenCalled();
  });

  it("com alteração não salva, pergunta; 'Sair sem salvar' fecha sem gravar", async () => {
    abrir();
    const editor = await editorCarregado();
    fireEvent.change(editor, { target: { value: "<p>Mudei</p>" } });
    expect(screen.getByText("Alterações não salvas")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Fechar" })[0]);
    const pergunta = await screen.findByRole("dialog", { name: "Sair sem salvar?" });
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(within(pergunta).getByRole("button", { name: "Sair sem salvar" }));
    expect(onClose).toHaveBeenCalled();
    expect(updateMock).not.toHaveBeenCalled();
  });

  it("'Salvar e fechar' grava e fecha", async () => {
    abrir();
    const editor = await editorCarregado();
    fireEvent.change(editor, { target: { value: "<p>Mudei</p>" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Fechar" })[0]);
    const pergunta = await screen.findByRole("dialog", { name: "Sair sem salvar?" });
    fireEvent.click(within(pergunta).getByRole("button", { name: "Salvar e fechar" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(updateMock.mock.calls[0][1]).toMatchObject({ corpo_html: "<p>Mudei</p>" });
  });
});

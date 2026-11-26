/**
 * SI-67, segunda rodada (pedido do Heitor ao ver a tela):
 *
 * - Régua: os recuos que se arrastam ficam dentro da largura do texto.
 * - Bloco Imagem no montador de modelos: vira `<img width>` alinhado e volta
 *   a ser o mesmo bloco ao reabrir o modelo.
 * - "Criar novo modelo" dentro de "Modelos de documentos": só para quem pode
 *   criar modelo; abre o formulário de Cadastros ali mesmo e, salvo, o modelo
 *   novo segue para o documento.
 * - Dialog `semCabecalho`: o título continua nomeando o diálogo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { limitarRecuos, LARGURA_TEXTO_CM } from "@/components/ui/extensao-recuo";
import { blocosParaHtml, htmlParaBlocos, novoBloco, type Bloco } from "@/lib/template-blocos";

const IMG = "/api/v2/editor-imagens/" + "a".repeat(32) + ".png";

let podeCriar = true;
vi.mock("@/lib/auth", () => ({ usePermissao: () => podeCriar }));

const createMock = vi.fn((d: Record<string, unknown>) =>
  Promise.resolve({ id: 99, nome: d.nome, ativo: d.ativo, padrao: false, descricao: null, corpo_html: d.corpo_html }),
);
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      templatesDocumento: {
        ...actual.api.templatesDocumento,
        list: () => Promise.resolve([{ id: 4, nome: "Comunicação interna", descricao: null, padrao: true }]),
        placeholders: () => Promise.resolve([]),
        create: (d: Record<string, unknown>) => createMock(d),
      },
      unidades: { ...actual.api.unidades, list: () => Promise.resolve({ items: [] }) },
    },
    protocoloApi: { ...actual.protocoloApi, listEspecies: () => Promise.resolve([]) },
  };
});
// O montador e o tiptap não rodam no jsdom: o conteúdo do modelo vira um textarea.
vi.mock("@/components/protocolo/EditorDeModelo", () => ({
  EditorDeModelo: ({ corpoHtml, onCorpoHtml }: { corpoHtml: string; onCorpoHtml: (h: string) => void }) => (
    <textarea aria-label="Conteúdo do template" value={corpoHtml} onChange={(e) => onCorpoHtml(e.target.value)} />
  ),
}));

import { ModelosDeDocumentoDialog } from "@/components/protocolo/ModelosDeDocumentoDialog";
import { Dialog } from "@/components/ui/dialog";
import { ToastProvider } from "@/components/ui/toast";

beforeEach(() => {
  podeCriar = true;
  createMock.mockClear();
});
afterEach(cleanup);

describe("recuos da régua", () => {
  it("nada de recuo negativo nem maior que o texto", () => {
    expect(limitarRecuos({ recuoEsquerdo: -3, recuoDireito: -1, recuoPrimeiraLinha: 0 })).toEqual({
      recuoEsquerdo: 0, recuoDireito: 0, recuoPrimeiraLinha: 0,
    });
    const r = limitarRecuos({ recuoEsquerdo: 30, recuoDireito: 30, recuoPrimeiraLinha: 30 });
    expect(r.recuoEsquerdo + r.recuoDireito).toBeLessThanOrEqual(LARGURA_TEXTO_CM - 2);
    expect(r.recuoEsquerdo + r.recuoPrimeiraLinha + r.recuoDireito).toBeLessThanOrEqual(LARGURA_TEXTO_CM - 2);
  });

  it("primeira linha pode voltar até a margem (recuo deslocado), não além", () => {
    expect(limitarRecuos({ recuoEsquerdo: 2, recuoDireito: 0, recuoPrimeiraLinha: -5 }).recuoPrimeiraLinha).toBe(-2);
  });

  it("arredonda em 2 casas", () => {
    expect(limitarRecuos({ recuoEsquerdo: 0.1 + 0.2, recuoDireito: 0, recuoPrimeiraLinha: 0 }).recuoEsquerdo).toBe(0.3);
  });
});

describe("bloco Imagem do modelo", () => {
  it("vira img com largura e alinhamento, e volta a ser o mesmo bloco", () => {
    const b = { ...novoBloco("imagem"), src: IMG, largura: 378, alinhamento: "right" } as Bloco;
    const html = blocosParaHtml([b]);
    expect(html).toBe(
      `<div class="bloco bloco-imagem"><p style="text-align: right"><img src="${IMG}" alt="" width="378"></p></div>`,
    );
    const [lido] = htmlParaBlocos(html);
    expect(lido).toMatchObject({ tipo: "imagem", src: IMG, largura: 378, alinhamento: "right" });
  });

  it("sem imagem escolhida, não gera nada", () => {
    expect(blocosParaHtml([novoBloco("imagem")])).toBe("");
  });
});

function abrirLista(onEscolher = vi.fn()) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ModelosDeDocumentoDialog open onClose={() => {}} onEscolher={onEscolher} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return onEscolher;
}

describe("Criar novo modelo, de dentro do editor", () => {
  it("quem não pode criar modelo não vê o botão", async () => {
    podeCriar = false;
    abrirLista();
    await screen.findByRole("button", { name: /Comunicação interna/ });
    expect(screen.queryByRole("button", { name: "Criar novo modelo" })).toBeNull();
  });

  it("abre o formulário de Cadastros ali mesmo e, salvo, o modelo segue para o documento", async () => {
    const onEscolher = abrirLista();
    fireEvent.click(await screen.findByRole("button", { name: "Criar novo modelo" }));
    const form = await screen.findByRole("dialog", { name: "Novo modelo de documento" });
    // A lista continua aberta por baixo: não houve redirecionamento.
    expect(screen.getByRole("dialog", { name: "Modelos de documentos" })).toBeInTheDocument();

    fireEvent.change(within(form).getByLabelText(/Nome/), { target: { value: "Ofício com logotipo" } });
    fireEvent.change(within(form).getByLabelText("Conteúdo do template"), {
      target: { value: `<p><img src="${IMG}" alt="" width="227"></p><p>Texto</p>` },
    });
    fireEvent.click(within(form).getByRole("button", { name: "Criar modelo" }));

    await waitFor(() => expect(createMock).toHaveBeenCalled());
    expect(createMock.mock.calls[0][0]).toMatchObject({ nome: "Ofício com logotipo", ativo: true });
    await waitFor(() => expect(onEscolher).toHaveBeenCalledWith({ id: 99, nome: "Ofício com logotipo" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Novo modelo de documento" })).toBeNull());
  });
});

describe("Dialog sem cabeçalho", () => {
  it("o título continua nomeando o diálogo, sem o X do topo", () => {
    render(
      <Dialog open onClose={() => {}} title="Editar documento" size="tela" semCabecalho>
        <p>conteúdo</p>
      </Dialog>,
    );
    expect(screen.getByRole("dialog", { name: "Editar documento" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Fechar" })).toBeNull();
  });
});

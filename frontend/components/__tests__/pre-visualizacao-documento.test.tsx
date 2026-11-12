/**
 * SI-30 — ver o documento enquanto ele é editado. A prévia monta a folha com o
 * CSS do PDF (vindo do backend), atualiza sem salvar e acusa `{{campo}}` que
 * sobrou (sai literal no PDF).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const CSS = "h1.doc-titulo { color: rgb(30, 58, 95); }";
const estiloImpressao = vi.fn(() => Promise.resolve({ css: CSS, css_tela: ".folha { padding: 1px; }" }));
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return { ...real, api: { ...real.api, templatesDocumento: { estiloImpressao: () => estiloImpressao() } } };
});

import {
  camposPendentes,
  montarFolha,
  PreVisualizacaoDocumento,
} from "@/components/PreVisualizacaoDocumento";

function montar(titulo: string, corpo: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = (t: string, c: string) => (
    <QueryClientProvider client={client}>
      <PreVisualizacaoDocumento titulo={t} corpoHtml={c} />
    </QueryClientProvider>
  );
  const r = render(ui(titulo, corpo));
  return { ...r, trocar: (t: string, c: string) => r.rerender(ui(t, c)) };
}

const folha = () =>
  (screen.getByTitle("Pré-visualização do documento") as HTMLIFrameElement).contentDocument!;

describe("PreVisualizacaoDocumento", () => {
  it("usa o CSS do PDF vindo do backend e mostra título + corpo", async () => {
    montar("Ofício nº 1", "<p>Senhor secretário,</p>");
    await waitFor(() => expect(folha().body.textContent).toContain("Senhor secretário"));
    expect(folha().head.innerHTML).toContain(CSS);
    expect(folha().querySelector("h1.doc-titulo")?.textContent).toBe("Ofício nº 1");
  });

  it("atualiza enquanto edita, sem recarregar a folha", async () => {
    const { trocar } = montar("Despacho", "<p>versão 1</p>");
    await waitFor(() => expect(folha().body.textContent).toContain("versão 1"));
    const antes = folha().querySelector(".folha");
    trocar("Despacho", "<p>versão 2</p>");
    await waitFor(() => expect(folha().body.textContent).toContain("versão 2"));
    // Mesmo nó: só o miolo foi reescrito — a rolagem do usuário fica onde estava.
    expect(folha().querySelector(".folha")).toBe(antes);
  });

  it("acusa campo não preenchido, na folha e no aviso", async () => {
    montar("Ofício", "<p>Processo {{processo.numero}} de {{ requerente.nome }}</p>");
    expect(await screen.findByRole("status")).toHaveTextContent(
      "2 campos não foram preenchidos",
    );
    await waitFor(() => expect(folha().querySelectorAll("mark.campo-pendente")).toHaveLength(2));
  });

  it("título com marcação é texto, não HTML", () => {
    expect(montarFolha("<b>x</b>", "")).toBe('<h1 class="doc-titulo">&#60;b&#62;x&#60;/b&#62;</h1>');
    expect(camposPendentes("{{a}} {{a}} {{b.c}}")).toEqual(["{{a}}", "{{b.c}}"]);
  });
});

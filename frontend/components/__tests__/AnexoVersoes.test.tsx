/**
 * SI-72 (RF-04 V1) — versão nova de documento na lista do processo.
 *
 * A substituída continua no processo com o mesmo número (folha não se
 * renumera), recolhida sob a vigente; nenhuma das duas oferece "Excluir"; só
 * a vigente oferece "Enviar nova versão", e não em processo arquivado.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AnexosProcesso, NovaVersaoDialog, separarVersoes } from "@/components/AnexosProcesso";
import { api, type AnexoNoProcesso, type ProcessoDetail } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    tiposAnexo: { list: vi.fn() },
    processos: { uploadAnexo: vi.fn(), deleteAnexo: vi.fn(), enviarNovaVersao: vi.fn() },
    jobs: { carimbarAnexos: vi.fn() },
  },
  anexoCarimbadoUrl: () => "",
  anexoDownloadUrl: () => "",
  anexoInlineUrl: () => "",
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => vi.fn() }));
vi.mock("@/components/AnexoDesentranhar", () => ({ DesentranharDialog: () => null }));
vi.mock("@/components/RedigirDocumentoDialog", () => ({ RedigirDocumentoDialog: () => null }));
let podeExcluir = true;
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ can: (_c: string, acao?: string) => acao !== "excluir" || podeExcluir }),
}));

const COTA = { usado_bytes: 0, limite_bytes: 200 * 1024 * 1024, nivel_sigilo: "ostensivo" };

function anexo(p: Partial<AnexoNoProcesso> & { id: number }): AnexoNoProcesso {
  return {
    descricao: `Doc ${p.id}`, publico: true, qtd_paginas: 1, e_doc: `${p.id}.txt`,
    tipo_anexo: null, ordem: p.id, documento_numero: p.id, pagina_processo: null,
    versao: 1, id_anexo_anterior: null, id_anexo_substituto: null, motivo_versao: null,
    aceita_nova_versao: true, id_anexo_processo: p.id + 100,
    ...p,
  };
}

// Doc 1 (v1) foi substituído pelo doc 3 (v2); doc 2 é avulso.
const ANEXOS = [
  anexo({ id: 1, descricao: "Requerimento", aceita_nova_versao: false, id_anexo_substituto: 3 }),
  anexo({ id: 2, descricao: "Comprovante" }),
  anexo({ id: 3, descricao: "Requerimento", versao: 2, id_anexo_anterior: 1,
          motivo_versao: "Faltava a assinatura" }),
];

function processo(p: Partial<ProcessoDetail> = {}): ProcessoDetail {
  return {
    id: 7, numero_processo: "P1/2026", situacao: "protocolado", ativo: true, arquivado: false,
    movimentacoes: [{ id: 1 }], anexos: ANEXOS, cota_anexacao: COTA, ...p,
  } as unknown as ProcessoDetail;
}

function montar(p?: Partial<ProcessoDetail>) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <AnexosProcesso processo={processo(p)} />
    </QueryClientProvider>,
  );
}

function linhaDe(texto: RegExp) {
  return screen.getAllByText(texto).map((el) => el.closest("li")!)[0];
}

beforeEach(() => {
  podeExcluir = true;
  vi.mocked(api.processos.enviarNovaVersao).mockReset().mockResolvedValue(
    anexo({ id: 9, versao: 3 }) as never,
  );
});

describe("separarVersoes", () => {
  it("lista principal só com vigentes; anteriores encadeadas da mais nova à mais velha", () => {
    const v3 = anexo({ id: 5, versao: 3, id_anexo_anterior: 3 });
    const v2 = { ...ANEXOS[2], id_anexo_substituto: 5 };
    const { principais, anterioresDe } = separarVersoes([ANEXOS[0], ANEXOS[1], v2, v3]);
    expect(principais.map((a) => a.id)).toEqual([2, 5]);
    expect(anterioresDe(v3).map((a) => a.id)).toEqual([3, 1]);
  });

  it("substituída cuja sucessora saiu da lista (desentranhada) não some", () => {
    const { principais } = separarVersoes([ANEXOS[0], ANEXOS[1]]);
    expect(principais.map((a) => a.id)).toEqual([1, 2]);
  });
});

describe("lista de anexos com versões", () => {
  it("mostra a vigente e recolhe a anterior, que mantém o número", async () => {
    montar();
    expect(screen.getByText(/2 anexos · 1 versão anterior/)).toBeInTheDocument();
    expect(screen.getByText("versão 2")).toBeInTheDocument();
    expect(screen.getByText(/o que mudou: Faltava a assinatura/)).toBeInTheDocument();
    expect(screen.queryByText("substituído")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /Ver versão anterior/ }));
    const anterior = linhaDe(/substituído pela versão 2/);
    expect(within(anterior).getByText(/Doc\. nº 1/)).toBeInTheDocument();
    expect(within(anterior).getByText(/\(Doc\. nº 3\)/)).toBeInTheDocument();
  });

  /** Rótulos das ações da linha: os botões à vista e, se houver, os do ⋯. */
  async function acoes(li: HTMLElement): Promise<string> {
    const vistos = within(li).queryAllByRole("button").map((b) => b.textContent ?? "");
    const mais = within(li).queryByRole("button", { name: "Mais ações" });
    if (!mais) return vistos.join(" | ");
    await userEvent.click(mais);
    const menu = screen.queryAllByRole("menuitem").map((b) => b.textContent ?? "");
    await userEvent.keyboard("{Escape}");
    return [...vistos, ...menu].join(" | ");
  }

  it("a substituída não se exclui; a vigente (enviada por engano) sim", async () => {
    montar();
    expect(await acoes(linhaDe(/^Comprovante$/))).toMatch(/Excluir/);
    const vigente = screen.getByText("versão 2").closest("li")!;
    const daVigente = await acoes(vigente);
    expect(daVigente).toMatch(/Excluir/);
    expect(daVigente).toMatch(/Enviar nova versão/);

    await userEvent.click(screen.getByRole("button", { name: /Ver versão anterior/ }));
    const daAnterior = await acoes(linhaDe(/substituído pela versão 2/));
    expect(daAnterior).not.toMatch(/Excluir/);
    expect(daAnterior).not.toMatch(/Enviar nova versão/);
  });

  it("toda linha tem a mesma forma: Abrir · Enviar nova versão à vista, o resto no ⋯", async () => {
    const pdf = { ...ANEXOS[2], e_doc: "3.pdf" };
    montar({ anexos: [ANEXOS[0], ANEXOS[1], pdf] } as Partial<ProcessoDetail>);
    const aVista = (li: HTMLElement) => {
      const mais = within(li).queryByRole("button", { name: "Mais ações" });
      return within(li).getAllByRole("button")
        .filter((b) => b !== mais && !/versão anterior/.test(b.textContent ?? ""))
        .map((b) => b.textContent?.trim() ?? "");
    };
    async function doMenu(li: HTMLElement) {
      await userEvent.click(within(li).getByRole("button", { name: "Mais ações" }));
      const itens = screen.getAllByRole("menuitem").map((m) => m.textContent?.trim() ?? "");
      await userEvent.keyboard("{Escape}");
      return itens;
    }
    const linhaPdf = screen.getByText("versão 2").closest("li")!;
    const linhaTxt = linhaDe(/^Comprovante$/);
    expect(aVista(linhaPdf)).toEqual(["Abrir", "Enviar nova versão"]);
    expect(aVista(linhaTxt)).toEqual(["Abrir", "Enviar nova versão"]);
    // Graves por último; Carimbar só no PDF.
    expect(await doMenu(linhaPdf)).toEqual(["Carimbar", "Baixar", "Desentranhar", "Excluir"]);
    expect(await doMenu(linhaTxt)).toEqual(["Baixar", "Desentranhar", "Excluir"]);
  });

  it("sem permissão de excluir processo, não há Desentranhar", async () => {
    podeExcluir = false;
    montar();
    expect(await acoes(linhaDe(/^Comprovante$/))).not.toMatch(/Desentranhar/);
  });

  it("processo arquivado não oferece nova versão", () => {
    montar({ arquivado: true } as Partial<ProcessoDetail>);
    expect(screen.queryByRole("button", { name: /Enviar nova versão/ })).not.toBeInTheDocument();
  });
});

describe("NovaVersaoDialog", () => {
  it("envia o arquivo e o motivo para a versão vigente", async () => {
    const onDone = vi.fn();
    const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    render(
      <QueryClientProvider client={qc}>
        <NovaVersaoDialog anexo={ANEXOS[2]} onClose={vi.fn()} processoId={7} cota={COTA}
                          onDone={onDone} />
      </QueryClientProvider>,
    );
    const area = (document.getElementById("file") as HTMLInputElement).parentElement!;
    const f = new File(["x"], "corrigido.pdf", { type: "application/pdf" });
    fireEvent.drop(area, { dataTransfer: { files: [f] } });
    await userEvent.type(screen.getByLabelText(/O que mudou/), "Assinatura incluída");
    await userEvent.click(screen.getByRole("button", { name: "Enviar versão 3" }));

    expect(api.processos.enviarNovaVersao).toHaveBeenCalledWith(7, 3, {
      file: f, motivo: "Assinatura incluída",
    });
    expect(onDone).toHaveBeenCalled();
  });

  it("sem arquivo não envia", async () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <NovaVersaoDialog anexo={ANEXOS[2]} onClose={vi.fn()} processoId={7} cota={COTA}
                          onDone={vi.fn()} />
      </QueryClientProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Enviar versão 3" }));
    expect(screen.getByText("Escolha o arquivo corrigido.")).toBeInTheDocument();
    expect(api.processos.enviarNovaVersao).not.toHaveBeenCalled();
  });
});

describe("NovaVersaoDialog — redigir no sistema", () => {
  function abrirDialogo(anexo: AnexoNoProcesso, onRedigir = vi.fn()) {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <NovaVersaoDialog anexo={anexo} onClose={vi.fn()} processoId={7} cota={COTA}
                          onDone={vi.fn()} onRedigir={onRedigir} />
      </QueryClientProvider>,
    );
    return onRedigir;
  }

  it("arquivo enviado abre em 'Enviar arquivo'; trocar para redigir abre o editor com o motivo", async () => {
    const onRedigir = abrirDialogo(ANEXOS[2]);
    expect(document.getElementById("file")).not.toBeNull();
    await userEvent.click(screen.getByRole("radio", { name: /Redigir no sistema/ }));
    expect(document.getElementById("file")).toBeNull(); // sem arquivo nesse modo
    await userEvent.type(screen.getByLabelText(/O que mudou/), "Corrigido o valor");
    await userEvent.click(screen.getByRole("button", { name: "Abrir o editor" }));
    expect(onRedigir).toHaveBeenCalledWith(ANEXOS[2], "Corrigido o valor");
    expect(api.processos.enviarNovaVersao).not.toHaveBeenCalled();
  });

  it("documento redigido já abre em 'Redigir no sistema'", () => {
    abrirDialogo({ ...ANEXOS[1], redigido: true });
    expect(screen.getByRole("radio", { name: /Redigir no sistema/ })).toBeChecked();
    expect(screen.getByText(/com o texto da versão atual/)).toBeInTheDocument();
  });
});

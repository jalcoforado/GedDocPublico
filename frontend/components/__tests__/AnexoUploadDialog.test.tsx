import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UploadDialog, arquivoAceito, tamanhoLegivel } from "@/components/AnexosProcesso";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    tiposAnexo: { list: vi.fn() },
    processos: { uploadAnexo: vi.fn() },
  },
  anexoCarimbadoUrl: () => "",
  anexoDownloadUrl: () => "",
  anexoInlineUrl: () => "",
}));

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const MB = 1024 * 1024;

function arquivo(nome: string, bytes: number) {
  const f = new File(["x"], nome, { type: "application/pdf" });
  Object.defineProperty(f, "size", { value: bytes });
  return f;
}

function abrir(cota = { usado_bytes: 10 * MB, limite_bytes: 200 * MB, nivel_sigilo: "ostensivo" }) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <UploadDialog
        open
        onClose={vi.fn()}
        processoId={7}
        numeroProcesso="P000123/2026"
        cota={cota}
        onDone={vi.fn()}
      />
    </QueryClientProvider>,
  );
}

/** Solta o arquivo na área de escolha (a que envolve o input). */
function soltar(f: File) {
  const area = (document.getElementById("file") as HTMLInputElement).parentElement!;
  fireEvent.drop(area, { dataTransfer: { files: [f] } });
}

beforeEach(() => {
  vi.mocked(api.tiposAnexo.list).mockResolvedValue([{ id: 3, tipo_anexo: "Ofício" }] as never);
  vi.mocked(api.processos.uploadAnexo).mockReset().mockResolvedValue({} as never);
});

describe("formatos do diálogo de anexo", () => {
  it("tamanho no formato brasileiro", () => {
    expect(tamanhoLegivel(512)).toBe("0,5 KB");
    expect(tamanhoLegivel(300 * 1024)).toBe("300 KB");
    expect(tamanhoLegivel(1.25 * MB)).toBe("1,3 MB");
  });

  it("aceita só os tipos do seletor, sem diferenciar maiúscula", () => {
    expect(arquivoAceito("RG.PDF")).toBe(true);
    expect(arquivoAceito("planilha.xlsx")).toBe(true);
    expect(arquivoAceito("script.exe")).toBe(false);
    expect(arquivoAceito("sem-extensao")).toBe(false);
  });
});

describe("Adicionar anexo", () => {
  it("diz em que processo o arquivo entra", () => {
    abrir();
    expect(screen.getByRole("dialog")).toHaveAccessibleDescription(
      "O arquivo entra no processo P000123/2026.",
    );
  });

  it("arquivo solto vira o cartão dele e preenche a descrição", () => {
    abrir();
    soltar(arquivo("RG do requerente.pdf", 2 * MB));
    expect(screen.getByText("RG do requerente.pdf")).toBeInTheDocument();
    expect(screen.getByText("2,0 MB · PDF")).toBeInTheDocument();
    expect(screen.getByLabelText(/^descrição/i)).toHaveValue("RG do requerente");
    expect(screen.getByText(/este arquivo ocupa 2,0 MB; sobram 188,0 MB/i)).toBeInTheDocument();
  });

  it("tipo não aceito é recusado com o motivo, sem virar o arquivo escolhido", () => {
    abrir();
    soltar(arquivo("virus.exe", 1000));
    expect(screen.getByRole("alert")).toHaveTextContent("“virus.exe” não é um tipo aceito");
    expect(screen.queryByText("virus.exe")).toBeNull();
  });

  it("arquivo maior que o espaço livre bloqueia o envio e diz quanto falta", () => {
    abrir();
    soltar(arquivo("grande.pdf", 195 * MB));
    expect(screen.getByText(/passa do espaço do processo — faltam 5,0 MB/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enviar anexo" })).toBeDisabled();
  });

  it("enviar sem arquivo acusa o campo", async () => {
    const u = userEvent.setup();
    abrir();
    await u.click(screen.getByRole("button", { name: "Enviar anexo" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Escolha o arquivo a anexar.");
    expect(api.processos.uploadAnexo).not.toHaveBeenCalled();
  });

  it("sigiloso sai como publico=false, com a descrição escrita pela pessoa", async () => {
    const u = userEvent.setup();
    abrir();
    soltar(arquivo("laudo.pdf", MB));
    const desc = screen.getByLabelText(/^descrição/i);
    await u.clear(desc);
    await u.type(desc, "Laudo médico");
    await u.click(screen.getByRole("radio", { name: "Sigiloso" }));
    await u.click(screen.getByRole("button", { name: "Enviar anexo" }));
    expect(api.processos.uploadAnexo).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ descricao: "Laudo médico", publico: false }),
    );
  });

  it("trocar o arquivo troca a descrição que ninguém escreveu", () => {
    abrir();
    soltar(arquivo("primeiro.pdf", MB));
    soltar(arquivo("segundo.pdf", MB));
    expect(screen.getByLabelText(/^descrição/i)).toHaveValue("segundo");
  });
});

/**
 * Guarda o limite de upload anunciado ao cidadão.
 *
 * O portal anunciava 25 MB enquanto o backend recusa acima de 20
 * (`max_upload_size_mb` em `backend/app/config.py`, validado em
 * `services/anexos.py`). O efeito era o pior possível: um arquivo de 22 MB
 * passava na validação do navegador, subia inteiro e só então o servidor
 * respondia "Arquivo excede 20 MB".
 *
 * Este teste trava o número exibido e o ponto de corte. Ao mudar o limite no
 * backend, ele quebra — que é exatamente o lembrete de mudar os dois juntos.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AbrirProcessoPage from "@/app/cidadao/abrir/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    cidadao: {
      assuntos: vi.fn(),
      especies: vi.fn(),
      abrirProcesso: vi.fn(),
      uploadAnexo: vi.fn(),
    },
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/cidadao-auth", () => ({
  useRequireCidadao: () => ({ cidadao: { id: 1, nome: "Maria" }, loading: false }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const assuntosMock = api.cidadao.assuntos as ReturnType<typeof vi.fn>;
const especiesMock = api.cidadao.especies as ReturnType<typeof vi.fn>;

/** Limite aceito pelo backend. Mantidos em espelho de propósito. */
const LIMITE_MB = 20;

function arquivoDe(mb: number, nome = "documento.pdf"): File {
  const f = new File(["x"], nome, { type: "application/pdf" });
  // `File` não deixa definir `size` pelo construtor sem alocar o buffer todo.
  Object.defineProperty(f, "size", { value: Math.round(mb * 1024 * 1024) });
  return f;
}

async function irParaOPassoDoAnexo() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={qc}>
      <AbrirProcessoPage />
    </QueryClientProvider>,
  );
  fireEvent.change(await screen.findByLabelText(/Assunto/i), {
    target: { value: "1" },
  });
  fireEvent.change(screen.getByLabelText(/Descreva sua solicitação/i), {
    target: { value: "Preciso de uma certidão para fins de matrícula." },
  });
  fireEvent.click(screen.getByRole("button", { name: /Avançar/i }));
  return await screen.findByLabelText(/Documento \(opcional\)/i).catch(() => null);
}

beforeEach(() => {
  vi.clearAllMocks();
  assuntosMock.mockResolvedValue([
    { id: 1, assunto: "Certidão", tipo_processo: "Administrativo" },
  ]);
  especiesMock.mockResolvedValue([]);
});

describe("Limite de upload do portal do cidadão", () => {
  it("anuncia o mesmo limite que o backend aceita", async () => {
    await irParaOPassoDoAnexo();
    expect(
      await screen.findByText(new RegExp(`até ${LIMITE_MB} MB`, "i")),
    ).toBeInTheDocument();
  });

  it("recusa no navegador o arquivo acima do limite, antes de subir", async () => {
    await irParaOPassoDoAnexo();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    expect(input).not.toBeNull();

    fireEvent.change(input!, { target: { files: [arquivoDe(LIMITE_MB + 2)] } });

    expect(
      await screen.findByText(new RegExp(`excede ${LIMITE_MB} MB`, "i")),
    ).toBeInTheDocument();
  });

  it("aceita arquivo logo abaixo do limite", async () => {
    await irParaOPassoDoAnexo();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');

    fireEvent.change(input!, {
      target: { files: [arquivoDe(LIMITE_MB - 1, "peticao.pdf")] },
    });

    expect(screen.queryByText(/excede/i)).not.toBeInTheDocument();
    expect(await screen.findByText("peticao.pdf")).toBeInTheDocument();
  });
});

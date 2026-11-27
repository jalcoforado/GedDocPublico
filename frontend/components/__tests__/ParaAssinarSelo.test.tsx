import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ParaAssinarPage from "@/app/(app)/para-assinar/page";
import { api } from "@/lib/api";
import { abrirPdf } from "@/lib/pdf-render";
import { fracaoDoSelo, posicaoInicial } from "@/lib/selo-assinatura";

// O jsdom não desenha PDF: o pdf.js fica atrás de `lib/pdf-render`, trocado
// aqui por um documento falso de duas páginas A4.
vi.mock("@/lib/pdf-render", () => ({ abrirPdf: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    assinaturas: {
      minhasPendentes: vi.fn(),
      assinar: vi.fn(),
      recusar: vi.fn(),
    },
  },
  anexoInlineUrl: (id: number) => `/inline/${id}`,
  anexoDownloadUrl: (id: number) => `/dl/${id}`,
  anexoCarimbadoUrl: (id: number) => `/carimbado/${id}`,
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const A4 = { larguraPt: 595, alturaPt: 842 };

const base = {
  id_assinatura_anexo: 11,
  id_anexo: 5,
  anexo_descricao: "Ofício 12",
  id_solicitacao: 3,
  id_processo: 9,
  numero_processo: "P000001/2026",
  nome_solicitante: "Fulano",
  dt_inicio: new Date().toISOString(),
};

const desenhar = vi.fn().mockResolvedValue(undefined);
function docFalso(numPaginas = 2) {
  return {
    numPaginas,
    pagina: vi.fn(async () => ({ ...A4, desenhar })),
    fechar: vi.fn(),
  };
}

const mAssinar = api.assinaturas.assinar as ReturnType<typeof vi.fn>;
const mPendentes = api.assinaturas.minhasPendentes as ReturnType<typeof vi.fn>;
const mAbrir = abrirPdf as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ParaAssinarPage />
    </QueryClientProvider>,
  );
}

async function abrir(u: ReturnType<typeof userEvent.setup>) {
  await screen.findByText("Ofício 12");
  await u.click(screen.getByRole("button", { name: /^assinar$/i }));
}

async function confirmar(u: ReturnType<typeof userEvent.setup>) {
  await u.type(screen.getByLabelText(/^senha/i), "minha-senha");
  await u.click(screen.getByRole("button", { name: /confirmar assinatura/i }));
}

describe("Para assinar — posicionar o selo (SI-68)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mAssinar.mockResolvedValue({});
  });

  it("PDF: mostra o documento carimbado, abre na última página e envia a posição", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: true }]);
    mAbrir.mockResolvedValue(docFalso(2));
    const u = userEvent.setup();
    renderPage();
    await abrir(u);

    expect(await screen.findByText("Página 2 de 2")).toBeInTheDocument();
    expect(mAbrir).toHaveBeenCalledWith("/carimbado/5");
    expect(
      await screen.findByRole("button", { name: /posição da assinatura na página 2/i }),
    ).toBeInTheDocument();

    await confirmar(u);
    const inicial = posicaoInicial(A4);
    await waitFor(() => expect(mAssinar).toHaveBeenCalledTimes(1));
    const [id, senha, posicao] = mAssinar.mock.calls[0];
    expect(id).toBe(11);
    expect(senha).toBe("minha-senha");
    expect(posicao.pagina).toBe(2);
    expect(posicao.x).toBeCloseTo(inicial.x, 3);
    expect(posicao.y).toBeCloseTo(inicial.y, 3);
  });

  it("trocar de página e mover com as setas muda o que vai ao backend", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: true }]);
    mAbrir.mockResolvedValue(docFalso(2));
    const u = userEvent.setup();
    renderPage();
    await abrir(u);
    await screen.findByText("Página 2 de 2");

    await u.click(screen.getByRole("button", { name: /página anterior/i }));
    const selo = await screen.findByRole("button", { name: /posição da assinatura na página 1/i });
    fireEvent.keyDown(selo, { key: "ArrowLeft", shiftKey: true });
    fireEvent.keyDown(selo, { key: "ArrowUp" });

    await confirmar(u);
    await waitFor(() => expect(mAssinar).toHaveBeenCalledTimes(1));
    const posicao = mAssinar.mock.calls[0][2];
    const inicial = posicaoInicial(A4);
    expect(posicao.pagina).toBe(1);
    expect(posicao.x).toBeCloseTo(inicial.x - 0.05, 3);
    expect(posicao.y).toBeCloseTo(inicial.y - 0.01, 3);
  });

  it("clicar na página leva o quadrado até o ponto clicado", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: true }]);
    mAbrir.mockResolvedValue(docFalso(1));
    const u = userEvent.setup();
    renderPage();
    await abrir(u);
    await screen.findByText("Página 1 de 1");

    const area = screen.getByTestId("area-pagina");
    area.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 595, height: 842, right: 595, bottom: 842 }) as DOMRect;
    // O PointerEvent do jsdom descarta clientX/Y; um MouseEvent com o tipo
    // "pointerdown" chega ao React com as coordenadas.
    fireEvent(
      area,
      new MouseEvent("pointerdown", { bubbles: true, clientX: 297.5, clientY: 421 }),
    );
    fireEvent(area, new MouseEvent("pointerup", { bubbles: true }));

    await confirmar(u);
    await waitFor(() => expect(mAssinar).toHaveBeenCalledTimes(1));
    const posicao = mAssinar.mock.calls[0][2];
    const f = fracaoDoSelo(A4);
    // O ponto clicado vira o CENTRO do quadrado.
    expect(posicao.x).toBeCloseTo(0.5 - f.largura / 2, 3);
    expect(posicao.y).toBeCloseTo(0.5 - f.altura / 2, 3);
  });

  it("se o carimbado não abre, tenta o original", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: true }]);
    mAbrir.mockRejectedValueOnce(new Error("400")).mockResolvedValueOnce(docFalso(1));
    const u = userEvent.setup();
    renderPage();
    await abrir(u);
    expect(await screen.findByText("Página 1 de 1")).toBeInTheDocument();
    expect(mAbrir).toHaveBeenNthCalledWith(2, "/inline/5");
  });

  it("se nenhum PDF abre, avisa e assina sem selo", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: true }]);
    mAbrir.mockRejectedValue(new Error("falhou"));
    const u = userEvent.setup();
    renderPage();
    await abrir(u);
    expect(await screen.findByRole("status")).toHaveTextContent(/sem o selo na página/i);
    await confirmar(u);
    await waitFor(() => expect(mAssinar).toHaveBeenCalledWith(11, "minha-senha", undefined));
  });

  it("anexo que não é PDF: diálogo de sempre, sem pré-visualização nem posição", async () => {
    mPendentes.mockResolvedValue([{ ...base, anexo_pdf: false }]);
    const u = userEvent.setup();
    renderPage();
    await abrir(u);
    expect(screen.queryByText(/página \d+ de \d+/i)).not.toBeInTheDocument();
    expect(mAbrir).not.toHaveBeenCalled();
    await confirmar(u);
    await waitFor(() => expect(mAssinar).toHaveBeenCalledWith(11, "minha-senha", undefined));
  });
});

/**
 * Nova denúncia (portal) — padrão de formulário (2026-11-10).
 * Data do fato já vem com hoje; erros só depois da tentativa; o botão nunca
 * fica desabilitado por validação; o corpo enviado é o mesmo de antes.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NovaDenunciaPage from "@/app/cidadao/denuncias/nova/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: { cidadaoDenuncias: { tipos: vi.fn(), create: vi.fn() } },
}));
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock("@/lib/cidadao-auth", () => ({
  useRequireCidadao: () => ({ cidadao: { id: 1, nome: "Maria" }, loading: false }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const tiposMock = api.cidadaoDenuncias.tipos as ReturnType<typeof vi.fn>;
const createMock = api.cidadaoDenuncias.create as ReturnType<typeof vi.fn>;

function hoje(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <NovaDenunciaPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  tiposMock.mockResolvedValue([
    { id: 3, nome: "Cobrança abusiva", ativo: true },
    { id: 4, nome: "Tipo desativado", ativo: false },
  ]);
});

describe("Nova denúncia", () => {
  it("abre sem erro e com a data de hoje já preenchida (e dizendo que dá para mudar)", async () => {
    renderPage();
    await screen.findByRole("option", { name: "Cobrança abusiva" });
    expect(screen.queryByRole("option", { name: "Tipo desativado" })).toBeNull();
    expect((screen.getByLabelText(/Quando aconteceu/i) as HTMLInputElement).value).toBe(hoje());
    expect(screen.getByText(/Já vem com a data de hoje/i)).toBeInTheDocument();
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull();
  });

  it("enviar sem tipo e sem descrição: resumo, erro em cada campo, nada enviado", async () => {
    renderPage();
    await screen.findByRole("option", { name: "Cobrança abusiva" });
    const enviar = screen.getByRole("button", { name: /Enviar denúncia/i });
    expect(enviar).not.toBeDisabled();
    fireEvent.click(enviar);
    expect(await screen.findByText(/Falta acertar 2 campos/i)).toBeInTheDocument();
    expect(screen.getByText(/Escolha o que aconteceu/i)).toBeInTheDocument();
    expect(screen.getByText(/Conte o que você viu/i)).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(/O que aconteceu/i)));
    expect(createMock).not.toHaveBeenCalled();
  });

  it("envia o mesmo corpo de antes e volta à lista", async () => {
    createMock.mockResolvedValue({ id: 1 });
    renderPage();
    await screen.findByRole("option", { name: "Cobrança abusiva" });
    fireEvent.change(screen.getByLabelText(/O que aconteceu/i), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText(/Quando aconteceu/i), { target: { value: "2026-05-01" } });
    fireEvent.change(screen.getByLabelText(/Conte como foi/i), {
      target: { value: "  O taxista cobrou acima do taxímetro.  " },
    });
    fireEvent.change(screen.getByLabelText(/Placa, ponto ou linha/i), { target: { value: " ABC1D23 " } });
    fireEvent.click(screen.getByRole("button", { name: /Enviar denúncia/i }));

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    expect(createMock.mock.calls[0][0]).toEqual({
      id_tipo: 3,
      data_fato: "2026-05-01",
      descricao: "O taxista cobrou acima do taxímetro.",
      referencia_alvo: "ABC1D23",
    });
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/cidadao/denuncias"));
    expect(sessionStorage.getItem("aprimora:cidadao:denuncia-registrada")).toBe("1");
  });
});

/**
 * Abrir processo (portal) — padrão de formulário (2026-11-10).
 *
 * Trava: nenhum erro ao abrir; "Continuar" nunca desabilitado — clicar com
 * falta mostra o erro embaixo de cada campo e foca o primeiro; o envio manda
 * o mesmo corpo de sempre e deixa o recado para a tela do processo mostrar
 * o número do protocolo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock("@/lib/cidadao-auth", () => ({
  useRequireCidadao: () => ({ cidadao: { id: 1, nome: "Maria" }, loading: false }),
}));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const assuntosMock = api.cidadao.assuntos as ReturnType<typeof vi.fn>;
const especiesMock = api.cidadao.especies as ReturnType<typeof vi.fn>;
const abrirMock = api.cidadao.abrirProcesso as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <AbrirProcessoPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  sessionStorage.clear();
  assuntosMock.mockResolvedValue([{ id: 1, assunto: "Iluminação pública", tipo_processo: null }]);
  especiesMock.mockResolvedValue([
    { id: 7, codigo: "REQUERIMENTO", nome: "Requerimento" },
    { id: 8, codigo: "PETICAO", nome: "Petição" },
  ]);
});

describe("Abrir processo — validação depois da tentativa", () => {
  it("abre sem erro; Continuar vazio acusa os dois campos e foca o primeiro", async () => {
    renderPage();
    const assunto = await screen.findByLabelText(/Sobre o que é o seu pedido/i);
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull();

    const continuar = screen.getByRole("button", { name: /^Continuar/i });
    expect(continuar).not.toBeDisabled();
    fireEvent.click(continuar);

    expect(await screen.findByText(/Escolha o tema do pedido/i)).toBeInTheDocument();
    expect(screen.getByText(/^Conte o que você precisa\.$/i)).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(assunto));
    // Continua na etapa 1.
    expect(screen.queryByText(/Quer anexar um documento/i)).toBeNull();
  });

  it("descrição curta diz quantas letras faltam", async () => {
    renderPage();
    await screen.findByLabelText(/Sobre o que é o seu pedido/i);
    const corpo = screen.getByLabelText(/Conte o que você precisa/i);
    fireEvent.change(corpo, { target: { value: "poste" } });
    fireEvent.blur(corpo);
    expect(screen.getByText(/faltam 5 letras/i)).toBeInTheDocument();
  });

  it("tipo de pedido com poucas opções é escolha à vista, com 'Não sei' marcado e explicado", async () => {
    renderPage();
    const naoSei = await screen.findByRole("radio", { name: /Não sei/i });
    expect(naoSei).toBeChecked();
    expect(screen.getByText(/a prefeitura classifica o pedido para você/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Requerimento/i }));
    expect(screen.getByText(/Para pedir algo à prefeitura/i)).toBeInTheDocument();
  });
});

describe("Abrir processo — envio", () => {
  it("manda o mesmo corpo de sempre, marca o protocolo para a tela seguinte e vai ao processo", async () => {
    abrirMock.mockResolvedValue({ id: 42, nup: null, numero_processo: "P000042/2026" });
    renderPage();
    await screen.findByRole("option", { name: /Iluminação pública/i });
    fireEvent.change(screen.getByLabelText(/Sobre o que é o seu pedido/i), { target: { value: "1" } });
    fireEvent.click(await screen.findByRole("radio", { name: /Requerimento/i }));
    fireEvent.change(screen.getByLabelText(/Conte o que você precisa/i), {
      target: { value: "Lâmpada apagada na Rua das Flores, 120." },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Continuar/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Continuar sem anexo/i }));

    // Conferir: cada bloco tem "Alterar" que volta à etapa certa.
    expect(await screen.findByText(/Confira antes de enviar/i)).toBeInTheDocument();
    expect(screen.getByText("Nenhum arquivo anexado")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^Abrir processo$/i }));

    await waitFor(() => expect(abrirMock).toHaveBeenCalledTimes(1));
    expect(abrirMock.mock.calls[0][0]).toEqual({
      id_assunto: 1,
      corpo: "Lâmpada apagada na Rua das Flores, 120.",
      observacao: undefined,
      id_especie_documental: 7,
    });
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/cidadao/processos/42"));
    expect(sessionStorage.getItem("aprimora:cidadao:protocolo-recebido")).toBe("42");
  });

  it("'Alterar' na conferência volta à etapa do pedido sem perder o texto", async () => {
    renderPage();
    await screen.findByRole("option", { name: /Iluminação pública/i });
    fireEvent.change(screen.getByLabelText(/Sobre o que é o seu pedido/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/Conte o que você precisa/i), {
      target: { value: "Texto com mais de dez letras" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Continuar/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Continuar sem anexo/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Alterar: O que você precisa/i }));
    const corpo = (await screen.findByLabelText(/Conte o que você precisa/i)) as HTMLTextAreaElement;
    expect(corpo.value).toBe("Texto com mais de dez letras");
  });
});

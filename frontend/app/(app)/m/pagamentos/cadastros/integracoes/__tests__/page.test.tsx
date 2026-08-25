/**
 * Gestão de chaves M2M (Onda C2, C2.3) — tela de sistemas integrados.
 *
 * Cobre:
 *  C1. lista os sistemas com nome, prefixo, escopos e estado (ativo/revogado);
 *  C2. criar chave chama o POST com nome + escopos escolhidos;
 *  C3. a chave completa só aparece UMA vez, no modal de sucesso da criação,
 *      com aviso de que não será mostrada de novo;
 *  C4. revogar pede confirmação antes de chamar a API.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IntegracoesPage from "@/app/(app)/m/pagamentos/cadastros/integracoes/page";

const listarMock = vi.fn();
const criarMock = vi.fn();
const revogarMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual: any = await vi.importActual("@/lib/api");
  return {
    ...actual,
    api: {
      pagamentos: {
        sistemasIntegrados: {
          listar: () => listarMock(),
          criar: (data: unknown) => criarMock(data),
          revogar: (id: number) => revogarMock(id),
        },
      },
    },
  };
});

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn() }),
}));

const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));

const SISTEMA_ATIVO = {
  id: 1,
  nome: "ERP Financeiro",
  prefixo: "aprm_ab12cd34",
  escopo_leitura: true,
  escopo_escrita: false,
  ativo: true,
  criado_em: "2026-08-10T10:00:00",
  revogado_em: null,
  id_usuario_criador: 5,
};

const SISTEMA_REVOGADO = {
  ...SISTEMA_ATIVO,
  id: 2,
  nome: "Sistema Antigo",
  prefixo: "aprm_zz99yy88",
  ativo: false,
  revogado_em: "2026-08-15T09:00:00",
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <IntegracoesPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  confirmMock.mockResolvedValue(true);
  listarMock.mockResolvedValue([SISTEMA_ATIVO, SISTEMA_REVOGADO]);
});

describe("Sistemas integrados — gestão de chaves M2M", () => {
  it("lista os sistemas com nome, prefixo, escopos e estado", async () => {
    renderPage();

    const linhaAtiva = (await screen.findByText("ERP Financeiro")).closest("tr");
    expect(linhaAtiva).not.toBeNull();
    expect(within(linhaAtiva!).getByText(/aprm_ab12cd34/)).toBeInTheDocument();
    expect(within(linhaAtiva!).getByText(/ativa/i)).toBeInTheDocument();

    const linhaRevogada = screen.getByText("Sistema Antigo").closest("tr");
    expect(within(linhaRevogada!).getByText(/revogada/i)).toBeInTheDocument();
  });

  it("mostra estado vazio quando não há sistemas cadastrados", async () => {
    listarMock.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByText(/nenhum sistema integrado/i)).toBeInTheDocument();
  });

  it('"Nova chave" chama o POST com nome e escopos escolhidos', async () => {
    criarMock.mockResolvedValue({
      ...SISTEMA_ATIVO,
      id: 3,
      nome: "Novo Sistema",
      chave: "aprm_novo123.segredo-longo-xyz",
    });
    renderPage();
    await screen.findByText("ERP Financeiro");

    fireEvent.click(screen.getByRole("button", { name: /nova chave/i }));

    const dialog = (await screen.findByText("Nova chave de integração")).closest(
      "[role=dialog]",
    ) as HTMLElement;
    fireEvent.change(within(dialog).getByLabelText(/nome/i), {
      target: { value: "Novo Sistema" },
    });
    fireEvent.click(within(dialog).getByLabelText(/leitura/i));
    fireEvent.click(within(dialog).getByRole("button", { name: /criar/i }));

    await waitFor(() =>
      expect(criarMock).toHaveBeenCalledWith(
        expect.objectContaining({ nome: "Novo Sistema", escopo_leitura: true }),
      ),
    );
  });

  it("mostra a chave completa UMA vez, com aviso de que não volta a aparecer", async () => {
    criarMock.mockResolvedValue({
      ...SISTEMA_ATIVO,
      id: 3,
      nome: "Novo Sistema",
      chave: "aprm_novo123.segredo-longo-xyz",
    });
    renderPage();
    await screen.findByText("ERP Financeiro");

    fireEvent.click(screen.getByRole("button", { name: /nova chave/i }));
    const dialogCriar = (await screen.findByText("Nova chave de integração")).closest(
      "[role=dialog]",
    ) as HTMLElement;
    fireEvent.change(within(dialogCriar).getByLabelText(/nome/i), {
      target: { value: "Novo Sistema" },
    });
    fireEvent.click(within(dialogCriar).getByRole("button", { name: /criar/i }));

    // Modal de sucesso: chave completa aparece, com aviso forte.
    const chaveEl = await screen.findByText("aprm_novo123.segredo-longo-xyz");
    expect(chaveEl).toBeInTheDocument();
    expect(screen.getByText(/copie agora/i)).toBeInTheDocument();
    expect(screen.getByText(/não será mostrada de novo/i)).toBeInTheDocument();

    // Fechando o modal de sucesso, a chave não fica em lugar nenhum da tela —
    // é o comportamento que a garantia de "uma vez só" promete.
    fireEvent.click(screen.getByRole("button", { name: /entendi/i }));
    await waitFor(() =>
      expect(screen.queryByText("aprm_novo123.segredo-longo-xyz")).not.toBeInTheDocument(),
    );
  });

  it("revogar pede confirmação antes de chamar a API", async () => {
    revogarMock.mockResolvedValue({ ...SISTEMA_ATIVO, ativo: false });
    renderPage();
    const linhaAtiva = (await screen.findByText("ERP Financeiro")).closest("tr") as HTMLElement;

    fireEvent.click(within(linhaAtiva).getByRole("button", { name: /revogar/i }));

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    await waitFor(() => expect(revogarMock).toHaveBeenCalledWith(1));
  });

  it("se a confirmação for cancelada, não chama a API de revogar", async () => {
    confirmMock.mockResolvedValueOnce(false);
    renderPage();
    const linhaAtiva = (await screen.findByText("ERP Financeiro")).closest("tr") as HTMLElement;

    fireEvent.click(within(linhaAtiva).getByRole("button", { name: /revogar/i }));

    await waitFor(() => expect(confirmMock).toHaveBeenCalled());
    expect(revogarMock).not.toHaveBeenCalled();
  });
});

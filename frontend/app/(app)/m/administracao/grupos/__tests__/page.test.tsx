/**
 * Grupos & Permissões — formulário de novo grupo e matriz de permissões
 * (padrão de formulário, 2026-11-10).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GruposPage from "@/app/(app)/m/administracao/grupos/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    grupos: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      transacoes: vi.fn(),
      setTransacoes: vi.fn(),
    },
    niveis: vi.fn(),
    sistemas: vi.fn(),
    transacoes: vi.fn(),
  },
}));

vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const GRUPO = { id: 3, grupo: "Atendimento", id_nivel: 2, id_sistema: 1 };

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <GruposPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (api.grupos.list as ReturnType<typeof vi.fn>).mockResolvedValue([GRUPO]);
  (api.niveis as ReturnType<typeof vi.fn>).mockResolvedValue([
    { id: 1, nivel: "Administrador geral", valor: 0 },
    { id: 2, nivel: "Operador", valor: 10 },
  ]);
  (api.sistemas as ReturnType<typeof vi.fn>).mockResolvedValue([
    { id: 1, sistema: "Aprimora", app: null },
  ]);
  (api.transacoes as ReturnType<typeof vi.fn>).mockResolvedValue([
    { id: 10, transacao: "Processos", codigo: "processo" },
    { id: 11, transacao: "Veículos", codigo: "frota" },
    { id: 12, transacao: "Usuários", codigo: "usuario" },
  ]);
  (api.grupos.setTransacoes as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (api.grupos.create as ReturnType<typeof vi.fn>).mockResolvedValue({ ...GRUPO, id: 4 });
});

describe("GruposPage — matriz de permissões", () => {
  it("grupo sem nenhuma permissão abre a matriz (sem laço de render) agrupada por módulo", async () => {
    (api.grupos.transacoes as ReturnType<typeof vi.fn>).mockResolvedValue([]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Permissões/i }));
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText("Protocolo")).toBeInTheDocument();
    expect(within(dialog).getByText("Frota")).toBeInTheDocument();
    expect(within(dialog).getByText("Administração")).toBeInTheDocument();
    expect(within(dialog).getByText("Acesso a 0 de 3 áreas")).toBeInTheDocument();
  });

  it("marcar uma ação envia só as áreas com alguma ação ligada", async () => {
    (api.grupos.transacoes as ReturnType<typeof vi.fn>).mockResolvedValue([
      { id_transacao: 12, inserir: true, atualizar: false, excluir: false },
    ]);
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Permissões/i }));
    const dialog = await screen.findByRole("dialog");
    const alterarProcessos = await within(dialog).findByLabelText("Alterar em Processos");
    expect(alterarProcessos).not.toBeChecked();
    fireEvent.click(alterarProcessos);
    expect(within(dialog).getByText("Acesso a 2 de 3 áreas")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Salvar permissões" }));
    await waitFor(() => expect(api.grupos.setTransacoes).toHaveBeenCalled());
    const [id, lista] = (api.grupos.setTransacoes as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(id).toBe(3);
    expect(lista).toEqual([
      { id_transacao: 10, inserir: false, atualizar: true, excluir: false },
      { id_transacao: 12, inserir: true, atualizar: false, excluir: false },
    ]);
  });
});

describe("GruposPage — novo grupo", () => {
  it("criar sem preencher mostra o que falta e não chama a API", async () => {
    renderPage();
    await screen.findByText("Atendimento");
    fireEvent.click(screen.getByRole("button", { name: /Novo grupo/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByText("Dê um nome ao grupo.")).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Criar grupo" }));
    expect(await within(dialog).findByText("Dê um nome ao grupo.")).toBeInTheDocument();
    expect(within(dialog).getByText("Escolha o nível.")).toBeInTheDocument();
    expect(api.grupos.create).not.toHaveBeenCalled();
  });

  it("com um sistema só ele vem escolhido; nível de super-usuário avisa a consequência", async () => {
    renderPage();
    await screen.findByText("Atendimento");
    fireEvent.click(screen.getByRole("button", { name: /Novo grupo/i }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText(/^Sistema/)).toHaveValue("1");
    fireEvent.change(within(dialog).getByLabelText(/^Nome do grupo/), { target: { value: "Gestão" } });
    fireEvent.change(within(dialog).getByLabelText(/^Nível/), { target: { value: "1" } });
    expect(within(dialog).getByText(/passa por cima de todas as permissões/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Criar grupo" }));
    await waitFor(() =>
      expect(api.grupos.create).toHaveBeenCalledWith({ grupo: "Gestão", id_nivel: 1, id_sistema: 1 }),
    );
  });
});

/**
 * Formulário de unidade (Organograma e lista de Unidades usam o mesmo):
 * erro só depois da tentativa, título que diz o que se faz e a consequência
 * da unidade superior escolhida.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { UnidadeEditDrawer, type DrawerMode } from "@/components/organograma/UnidadeEditDrawer";
import { api, type OrganogramaNo } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    tiposUnidade: vi.fn(),
    unidades: { create: vi.fn(), update: vi.fn(), remove: vi.fn() },
  },
}));
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => vi.fn().mockResolvedValue(true) }));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));

const NOS = [
  { id: 1, unidade_trabalho: "Prefeitura", sigla: "PREF", id_unidade_pai: null },
  { id: 2, unidade_trabalho: "Secretaria de Saúde", sigla: "SMS", id_unidade_pai: 1 },
] as unknown as OrganogramaNo[];

function renderDrawer(mode: DrawerMode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <UnidadeEditDrawer open mode={mode} allNos={NOS} onClose={vi.fn()} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (api.tiposUnidade as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (api.unidades.create as ReturnType<typeof vi.fn>).mockResolvedValue({ id: 3 });
});

describe("UnidadeEditDrawer", () => {
  it("subunidade: título e consequência do pai já escolhido", async () => {
    renderDrawer({ kind: "create", parentId: 2 });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Nova subunidade")).toBeInTheDocument();
    expect(within(dialog).getByText(/Fica dentro de PREF › SMS\./)).toBeInTheDocument();
  });

  it("salvar sem nome mostra o erro só depois da tentativa e não chama a API", async () => {
    renderDrawer({ kind: "create", parentId: null });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).queryByText("Informe o nome da unidade.")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/fica no topo do organograma/)).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cadastrar unidade" }));
    expect(await within(dialog).findByText("Informe o nome da unidade.")).toBeInTheDocument();
    expect(within(dialog).getByLabelText(/^Nome da unidade/)).toHaveAttribute("aria-invalid", "true");
    expect(api.unidades.create).not.toHaveBeenCalled();
  });

  it("cadastra com o mesmo payload de antes", async () => {
    renderDrawer({ kind: "create", parentId: 1 });
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText(/^Nome da unidade/), {
      target: { value: "  Secretaria de Educação " },
    });
    fireEvent.change(within(dialog).getByLabelText(/^Sigla/), { target: { value: "seduc" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cadastrar unidade" }));
    await waitFor(() =>
      expect(api.unidades.create).toHaveBeenCalledWith({
        unidade_trabalho: "Secretaria de Educação",
        sigla: "SEDUC",
        id_unidade_pai: 1,
        id_tipo_unidade_trabalho: null,
      }),
    );
  });
});

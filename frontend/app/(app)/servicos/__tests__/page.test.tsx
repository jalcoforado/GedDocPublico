import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ServicosPage from "@/app/(app)/servicos/page";
import { api, protocoloApi, servicosApi } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  servicosApi: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    ativar: vi.fn(),
    desativar: vi.fn(),
  },
  api: {
    unidades: { list: vi.fn() },
    tiposProcesso: { list: vi.fn() },
    assuntos: { listAll: vi.fn() },
  },
  protocoloApi: { listEspecies: vi.fn() },
}));

const canMock = vi.fn();
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: canMock }) }));
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), info: vi.fn() }),
}));
const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));

const listMock = servicosApi.list as ReturnType<typeof vi.fn>;
const createMock = servicosApi.create as ReturnType<typeof vi.fn>;
const updateMock = servicosApi.update as ReturnType<typeof vi.fn>;
const desativarMock = servicosApi.desativar as ReturnType<typeof vi.fn>;

const SERVICO = {
  id: 1, nome: "Certidão de IPTU", slug: "certidao-iptu", descricao_curta: "Emissão",
  descricao_detalhada: null, publico_alvo: null, instrucoes_cidadao: null,
  documentos_exigidos: null, prazo_estimado_dias: 5, id_unidade_responsavel: null,
  id_tipo_processo_padrao: null, id_assunto_padrao: null, id_especie_documental_padrao: null,
  nivel_sigilo_padrao: "ostensivo", canal_entrada_permitido: "portal", ativo: true,
  destaque: false, ordem_exibicao: 0, categoria: "Tributos", texto_confirmacao: null,
  criado_em: "2026-05-29T00:00:00", atualizado_em: null,
};

function renderPage() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <ServicosPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  canMock.mockReturnValue(true);
  confirmMock.mockResolvedValue(true);
  listMock.mockResolvedValue([SERVICO]);
  (api.unidades.list as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
  (api.tiposProcesso.list as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (api.assuntos.listAll as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  (protocoloApi.listEspecies as ReturnType<typeof vi.fn>).mockResolvedValue([]);
});

describe("ServicosPage — PR 4a", () => {
  it("lista serviços", async () => {
    renderPage();
    expect(await screen.findByText("Certidão de IPTU")).toBeInTheDocument();
    expect(screen.getByText("certidao-iptu")).toBeInTheDocument();
  });

  it("cria serviço (envia nome + slug)", async () => {
    createMock.mockResolvedValue({ ...SERVICO, id: 2, nome: "Novo", slug: "novo" });
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Novo serviço/i }));
    fireEvent.change(await screen.findByLabelText(/^Nome/i), { target: { value: "Poda de Árvore" } });
    fireEvent.click(screen.getByRole("button", { name: /^Salvar$/i }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    const payload = createMock.mock.calls[0][0];
    expect(payload.nome).toBe("Poda de Árvore");
    expect(payload.slug).toBe("poda-de-arvore"); // auto-slug
  });

  it("edita serviço", async () => {
    updateMock.mockResolvedValue({ ...SERVICO, nome: "IPTU editado" });
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Editar/i }));
    const nome = (await screen.findByLabelText(/^Nome/i)) as HTMLInputElement;
    fireEvent.change(nome, { target: { value: "IPTU editado" } });
    fireEvent.click(screen.getByRole("button", { name: /^Salvar$/i }));
    await waitFor(() => expect(updateMock).toHaveBeenCalled());
    expect(updateMock.mock.calls[0][0]).toBe(1);
    expect(updateMock.mock.calls[0][1].nome).toBe("IPTU editado");
  });

  it("desativa serviço após confirmar", async () => {
    desativarMock.mockResolvedValue({ ...SERVICO, ativo: false });
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Desativar/i }));
    await waitFor(() => expect(desativarMock).toHaveBeenCalledWith(1));
  });

  it("modo leitura sem permissão (sem botões de ação)", async () => {
    canMock.mockReturnValue(false);
    renderPage();
    await screen.findByText("Certidão de IPTU");
    expect(screen.queryByRole("button", { name: /Novo serviço/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Editar/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /Desativar/i })).toBeNull();
  });
});

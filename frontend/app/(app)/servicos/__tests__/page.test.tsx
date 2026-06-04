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

// =============================================================================
// Fase F (UX-1) — agrupamento visual, microcopy, estados
// =============================================================================

describe("ServicosPage — Fase F (UX-1 catálogo)", () => {
  it("dialog renderiza as 3 seções (Identificação, Configuração operacional, Orientações)", async () => {
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /^Editar$/i }));
    expect(
      await screen.findByRole("heading", { name: /Identificação do serviço/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Configuração operacional/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Orientações ao cidadão/i }),
    ).toBeInTheDocument();
  });

  it("todos os campos do formulário continuam presentes após o agrupamento", async () => {
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /^Editar$/i }));
    await screen.findByRole("heading", { name: /Identificação do serviço/i });
    // Identificação
    expect(screen.getByLabelText(/^Nome\*?$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Slug\*?$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Categoria$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Descrição curta$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Descrição detalhada$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Público-alvo$/i)).toBeInTheDocument();
    // Configuração operacional
    expect(screen.getByLabelText(/^Unidade responsável$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Tipo de processo padrão$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Assunto padrão$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Espécie documental padrão$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Nível de sigilo padrão$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Prazo estimado/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Ordem de exibição$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Destaque no portal$/i)).toBeInTheDocument();
    // Orientações
    expect(screen.getByLabelText(/^Instruções ao cidadão$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Texto de confirmação$/i)).toBeInTheDocument();
  });

  it("payload de criação preserva todas as chaves esperadas pelo backend", async () => {
    createMock.mockResolvedValue({ ...SERVICO, id: 99, nome: "Teste F", slug: "teste-f" });
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Novo serviço/i }));
    fireEvent.change(await screen.findByLabelText(/^Nome\*?$/i), { target: { value: "Teste F" } });
    fireEvent.click(screen.getByRole("button", { name: /^Salvar$/i }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    const payload = createMock.mock.calls[0][0];
    // Defaults preservados.
    expect(payload).toMatchObject({
      nome: "Teste F",
      slug: "teste-f",
      nivel_sigilo_padrao: "ostensivo",
      canal_entrada_permitido: "portal",
      destaque: false,
      ordem_exibicao: 0,
    });
    // Chaves obrigatórias do contrato com backend.
    [
      "descricao_curta",
      "descricao_detalhada",
      "publico_alvo",
      "instrucoes_cidadao",
      "documentos_exigidos",
      "prazo_estimado_dias",
      "id_unidade_responsavel",
      "id_tipo_processo_padrao",
      "id_assunto_padrao",
      "id_especie_documental_padrao",
      "categoria",
      "texto_confirmacao",
    ].forEach((k) => expect(payload).toHaveProperty(k));
  });

  it("documentos exigidos preservam formato {nome, obrigatorio, descricao} no payload", async () => {
    createMock.mockResolvedValue({ ...SERVICO, id: 100 });
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Novo serviço/i }));
    fireEvent.change(await screen.findByLabelText(/^Nome\*?$/i), { target: { value: "Com doc" } });

    fireEvent.click(screen.getByRole("button", { name: /^Adicionar$/i }));
    const docNome = await screen.findByLabelText(/Documento 1 — nome/i);
    fireEvent.change(docNome, { target: { value: "RG" } });
    const docDesc = screen.getByLabelText(/Documento 1 — descrição/i);
    fireEvent.change(docDesc, { target: { value: "Frente e verso" } });
    const obrigCheckbox = screen.getByLabelText(/^Obrigatório$/i) as HTMLInputElement;
    fireEvent.click(obrigCheckbox);

    fireEvent.click(screen.getByRole("button", { name: /^Salvar$/i }));
    await waitFor(() => expect(createMock).toHaveBeenCalled());
    const payload = createMock.mock.calls[0][0];
    expect(payload.documentos_exigidos).toEqual([
      { nome: "RG", obrigatorio: true, descricao: "Frente e verso" },
    ]);
  });

  it("EmptyState aparece quando a lista de serviços está vazia", async () => {
    listMock.mockResolvedValue([]);
    renderPage();
    expect(
      await screen.findByText(/Nenhum serviço cadastrado/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Cadastre o primeiro serviço/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Cadastrar serviço/i }),
    ).toBeInTheDocument();
  });

  it("loading state aparece enquanto a lista carrega", async () => {
    listMock.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(await screen.findByText(/Carregando serviços/i)).toBeInTheDocument();
  });

  it("contexto admin mantém 'Inativo' (não troca por 'Encerrado')", async () => {
    listMock.mockResolvedValue([{ ...SERVICO, ativo: false }]);
    renderPage();
    expect(await screen.findByText(/^Inativo$/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Encerrado$/i)).toBeNull();
  });

  it("prazo estimado tem microcopy de previsão (sem promessa/garantia)", async () => {
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /^Editar$/i }));
    await screen.findByLabelText(/Prazo estimado/i);
    expect(screen.getByText(/previsão/i)).toBeInTheDocument();
    // Termo vetado no portal cidadão também não pode aparecer aqui.
    expect(screen.queryByText(/\bgarantia\b/i)).toBeNull();
    expect(screen.queryByText(/garantid[oa]/i)).toBeNull();
  });

  it("área de documentos vazia explica como adicionar", async () => {
    renderPage();
    await screen.findByText("Certidão de IPTU");
    fireEvent.click(screen.getByRole("button", { name: /Novo serviço/i }));
    await screen.findByLabelText(/^Nome\*?$/i);
    expect(screen.getByText(/Nenhum documento exigido/i)).toBeInTheDocument();
    expect(screen.getByText(/Clique em/i)).toBeInTheDocument();
  });
});

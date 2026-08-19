import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { CrudPage } from "@/components/CrudPage";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

interface Item {
  id: number;
  nome: string;
}

/**
 * Dataset paginado de referência: 5 registros, page_size 2 → 3 páginas.
 * O mock devolve a página PEDIDA em `params.page` — se o CrudPage ignorar o
 * parâmetro (o bug original), toda chamada devolve a página 1 e os itens das
 * páginas seguintes nunca aparecem: é a prova por inversão dos testes abaixo.
 */
const PAGINAS: Item[][] = [
  [
    { id: 1, nome: "Alfa" },
    { id: 2, nome: "Bravo" },
  ],
  [
    { id: 3, nome: "Charlie" },
    { id: 4, nome: "Delta" },
  ],
  [{ id: 5, nome: "Echo" }],
];

function fetchPaginado() {
  return vi.fn(async (params?: { page: number }) => {
    const page = params?.page ?? 1;
    return {
      items: PAGINAS[page - 1] ?? [],
      total: 5,
      page,
      page_size: 2,
    };
  });
}

function renderCrud(
  fetchList: (params: { page: number }) => Promise<{ items: Item[]; total?: number } | Item[]>,
  extra: Partial<React.ComponentProps<typeof CrudPage<Item>>> = {},
) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const utils = render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ConfirmProvider>
          <CrudPage<Item>
            title="Itens"
            queryKey={["itens"]}
            fetchList={fetchList}
            createFn={vi.fn(async (d) => ({ id: 99, nome: d?.nome ?? "" }))}
            updateFn={vi.fn(async (id, d) => ({ id, nome: d?.nome ?? "" }))}
            deleteFn={vi.fn(async () => {})}
            columns={[{ header: "Nome", render: (r) => r.nome }]}
            fields={[{ name: "nome", label: "Nome", type: "text" }]}
            emptyForm={{ nome: "" }}
            {...extra}
          />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { ...utils, qc };
}

const btnProxima = () => screen.getByRole("button", { name: "Próxima" });
const btnAnterior = () => screen.getByRole("button", { name: "Anterior" });

describe("CrudPage — paginação", () => {
  it("solicita a página 1, renderiza suas linhas e mostra o total real", async () => {
    const fetchList = fetchPaginado();
    renderCrud(fetchList);

    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("Bravo")).toBeInTheDocument();
    // total do servidor (5) visível mesmo com só 2 linhas na tela
    expect(screen.getByText(/5 registros/)).toBeInTheDocument();
    expect(screen.getByText(/página 1/)).toBeInTheDocument();
    expect(fetchList).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
  });

  it("Próxima solicita e renderiza a página seguinte (registros antes inacessíveis)", async () => {
    const fetchList = fetchPaginado();
    renderCrud(fetchList);
    await screen.findByText("Alfa");

    fireEvent.click(btnProxima());

    // "Charlie" só existe na página 2: se fetchList for chamado sem page, ou se
    // a queryKey não diferenciar páginas (cache colidindo), isto falha.
    expect(await screen.findByText("Charlie")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();
    expect(fetchList).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
    expect(screen.getByText(/página 2/)).toBeInTheDocument();
  });

  it("Próxima fica desabilitada na última página", async () => {
    renderCrud(fetchPaginado());
    await screen.findByText("Alfa");

    fireEvent.click(btnProxima());
    await screen.findByText("Charlie");
    fireEvent.click(btnProxima());
    await screen.findByText("Echo");

    expect(btnProxima()).toBeDisabled();
    expect(btnAnterior()).not.toBeDisabled();
  });

  it("Anterior volta à página anterior e é desabilitado na página 1", async () => {
    renderCrud(fetchPaginado());
    await screen.findByText("Alfa");
    expect(btnAnterior()).toBeDisabled();

    fireEvent.click(btnProxima());
    await screen.findByText("Charlie");

    fireEvent.click(btnAnterior());
    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(btnAnterior()).toBeDisabled();
  });

  it("mudar a busca volta para a página 1", async () => {
    const fetchList = fetchPaginado();
    const onSearchChange = vi.fn();
    renderCrud(fetchList, { searchable: true, onSearchChange });
    await screen.findByText("Alfa");

    fireEvent.click(btnProxima());
    await screen.findByText("Charlie");

    fireEvent.change(screen.getByPlaceholderText("Buscar..."), {
      target: { value: "alf" },
    });

    await waitFor(() => expect(screen.getByText(/página 1/)).toBeInTheDocument());
    expect(onSearchChange).toHaveBeenCalledWith("alf");
    const ultimaChamada = fetchList.mock.calls.at(-1)?.[0];
    expect(ultimaChamada).toEqual(expect.objectContaining({ page: 1 }));
  });

  it("resposta em array simples continua funcionando, sem controles de paginação", async () => {
    const fetchList = vi.fn(async () => [
      { id: 1, nome: "Alfa" },
      { id: 2, nome: "Bravo" },
    ]);
    renderCrud(fetchList);

    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Próxima" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Anterior" })).not.toBeInTheDocument();
    expect(screen.queryByText(/registros — página/)).not.toBeInTheDocument();
  });

  it("criar registro invalida a família da listagem (refetch da página atual)", async () => {
    const fetchList = fetchPaginado();
    renderCrud(fetchList);
    await screen.findByText("Alfa");
    const chamadasAntes = fetchList.mock.calls.length;

    fireEvent.click(screen.getByRole("button", { name: "Novo" }));
    fireEvent.click(await screen.findByRole("button", { name: "Salvar" }));

    // A queryKey ganhou o segmento de página; a invalidação por prefixo das
    // mutations precisa continuar alcançando-a.
    await waitFor(() =>
      expect(fetchList.mock.calls.length).toBeGreaterThan(chamadasAntes),
    );
  });

  it("página que ficou além do fim (ex.: exclusão do último item) volta para a última válida", async () => {
    // Página 1 anuncia 2 páginas; a página 2 chega vazia com total encolhido —
    // simula o refetch pós-exclusão do único item da última página.
    const fetchList = vi.fn(async (params?: { page: number }) => {
      const page = params?.page ?? 1;
      if (page === 1) {
        return {
          items: [
            { id: 1, nome: "Alfa" },
            { id: 2, nome: "Bravo" },
          ],
          total: 3,
          page: 1,
          page_size: 2,
        };
      }
      return { items: [], total: 2, page, page_size: 2 };
    });
    renderCrud(fetchList);
    await screen.findByText("Alfa");

    fireEvent.click(btnProxima());

    // clamp: volta sozinho para a página 1 em vez de exibir vazio falso
    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText(/página 1/)).toBeInTheDocument();
  });
});

/**
 * Harness que reproduz o call-site real da busca: o caller guarda o termo em
 * estado próprio via `onSearchChange` e o injeta na queryKey e no fetch. É
 * assim que teclas viram fetches em produção — e é isso que o debounce gata.
 */
const TODOS: Item[] = [
  { id: 1, nome: "Alfa" },
  { id: 2, nome: "Bravo" },
  { id: 3, nome: "Charlie" },
  { id: 4, nome: "Delta" },
  { id: 5, nome: "Echo" },
];

function fetchComBusca() {
  return vi.fn(async (params: { page: number; q: string }) => {
    const filtrados = params.q
      ? TODOS.filter((i) => i.nome.toLowerCase().includes(params.q.toLowerCase()))
      : TODOS;
    const inicio = (params.page - 1) * 2;
    return {
      items: filtrados.slice(inicio, inicio + 2),
      total: filtrados.length,
      page: params.page,
      page_size: 2,
    };
  });
}

function CrudComBusca({
  fetchList,
}: {
  fetchList: (params: { page: number; q: string }) => Promise<any>;
}) {
  const [busca, setBusca] = useState("");
  return (
    <CrudPage<Item>
      title="Itens"
      queryKey={["itens", busca]}
      fetchList={(p) => fetchList({ ...p, q: busca })}
      createFn={vi.fn(async (d) => ({ id: 99, nome: d?.nome ?? "" }))}
      updateFn={vi.fn(async (id, d) => ({ id, nome: d?.nome ?? "" }))}
      deleteFn={vi.fn(async () => {})}
      columns={[{ header: "Nome", render: (r) => r.nome }]}
      fields={[{ name: "nome", label: "Nome", type: "text" }]}
      emptyForm={{ nome: "" }}
      searchable
      onSearchChange={setBusca}
    />
  );
}

function renderComBusca(fetchList: ReturnType<typeof fetchComBusca>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ConfirmProvider>
          <CrudComBusca fetchList={fetchList} />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * Timers REAIS de propósito: `vi.useFakeTimers()` patcheia os timers globais
 * do ambiente e, com os arquivos rodando sequencialmente
 * (`fileParallelism: false`), qualquer interação mal restaurada contamina a
 * coleta dos arquivos seguintes ("Vitest failed to find the current suite").
 * A prova do debounce sai de asserções de coalescência (nenhum fetch por
 * tecla, termos intermediários nunca buscados) e de tempo mínimo decorrido.
 */
describe("CrudPage — debounce da busca", () => {
  const input = () => screen.getByPlaceholderText("Buscar...");

  it("teclas rápidas coalescem em UM fetch com o termo final, só após o atraso", async () => {
    const fetchList = fetchComBusca();
    renderComBusca(fetchList);
    await screen.findByText("Alfa");
    const chamadasAntes = fetchList.mock.calls.length;

    const inicioDigitacao = Date.now();
    fireEvent.change(input(), { target: { value: "a" } });
    fireEvent.change(input(), { target: { value: "al" } });
    fireEvent.change(input(), { target: { value: "alf" } });

    // input responsivo imediatamente, sem esperar o debounce...
    expect(input()).toHaveValue("alf");
    // ...e nenhuma tecla disparou fetch imediato
    expect(fetchList.mock.calls.length).toBe(chamadasAntes);

    await waitFor(() =>
      expect(fetchList).toHaveBeenCalledWith(
        expect.objectContaining({ page: 1, q: "alf" }),
      ),
    );
    // se o fetch tivesse ocorrido antes do atraso de 300ms, o waitFor (poll de
    // ~50ms) teria resolvido bem antes deste piso
    expect(Date.now() - inicioDigitacao).toBeGreaterThanOrEqual(250);
    // coalescência real: os termos intermediários nunca viraram fetch
    const termosBuscados = fetchList.mock.calls
      .slice(chamadasAntes)
      .map((c) => c[0].q);
    expect(termosBuscados).toEqual(["alf"]);

    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    expect(screen.queryByText("Bravo")).not.toBeInTheDocument();
  });

  it("limpar a busca também efetiva após o debounce e restaura a lista", async () => {
    const fetchList = fetchComBusca();
    renderComBusca(fetchList);
    await screen.findByText("Alfa");

    fireEvent.change(input(), { target: { value: "echo" } });
    expect(await screen.findByText("Echo")).toBeInTheDocument();
    expect(screen.queryByText("Alfa")).not.toBeInTheDocument();

    fireEvent.change(input(), { target: { value: "" } });
    // antes do atraso vencer, a lista filtrada permanece
    expect(screen.getByText("Echo")).toBeInTheDocument();

    expect(await screen.findByText("Alfa")).toBeInTheDocument();
    await waitFor(() =>
      expect(fetchList.mock.calls.at(-1)?.[0]).toEqual(
        expect.objectContaining({ page: 1, q: "" }),
      ),
    );
  });

  it("busca efetivada em outra página volta para a página 1 (após o debounce)", async () => {
    const fetchList = fetchComBusca();
    renderComBusca(fetchList);
    await screen.findByText("Alfa");
    expect(screen.getByText(/página 1/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Próxima" }));
    await screen.findByText("Charlie");
    expect(screen.getByText(/página 2/)).toBeInTheDocument();

    fireEvent.change(input(), { target: { value: "delta" } });
    // antes do debounce a página não muda — teclar não navega
    expect(screen.getByText(/página 2/)).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText(/página 1/)).toBeInTheDocument());
    expect(screen.getByText("Delta")).toBeInTheDocument();
    expect(screen.queryByText("Charlie")).not.toBeInTheDocument();
    expect(fetchList.mock.calls.at(-1)?.[0]).toEqual(
      expect.objectContaining({ page: 1, q: "delta" }),
    );
  });
});

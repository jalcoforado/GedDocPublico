/**
 * Formulários do transporte regulado: erro só depois da tentativa (ao sair
 * do campo ou ao enviar), dito sob o campo e com o conserto; foco no
 * primeiro inválido; botão com o verbo do formulário.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { idsDoVinculo, errosDoVinculo, modoDoVinculo } from "@/components/transporte/campo-vinculo";
import {
  dicaVigencia,
  duracaoLegivel,
  erroValidade,
  somarMeses,
} from "@/components/transporte/formulario";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: [],
    loading: false,
    can: () => true,
  }),
}));

const createMock = vi.fn((_d: Record<string, unknown>) => Promise.resolve({ id: 1 }));
const registrarMock = vi.fn((_d: Record<string, unknown>) => Promise.resolve({ id: 1 }));
const vazio = () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 });

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      permissionarios: {
        ...actual.api.permissionarios,
        list: () => Promise.resolve({ items: [], total: 0, page: 1, page_size: 50 }),
        create: (d: Record<string, unknown>) => createMock(d),
      },
      empresas: { ...actual.api.empresas, list: () => vazio() },
      veiculosRegulados: { ...actual.api.veiculosRegulados, list: () => vazio() },
      ocorrenciasTransporte: {
        ...actual.api.ocorrenciasTransporte,
        list: () => vazio(),
        tipos: {
          ...actual.api.ocorrenciasTransporte.tipos,
          list: () =>
            Promise.resolve([
              { id: 4, nome: "Sem alvará", descricao: "Operando sem alvará válido", ativo: true, criado_em: "", atualizado_em: null },
            ]),
        },
        registrar: (d: Record<string, unknown>) => registrarMock(d),
      },
      recadastramento: {
        ...actual.api.recadastramento,
        ciclos: { ...actual.api.recadastramento.ciclos, list: () => vazio() },
      },
    },
  };
});

vi.setConfig({ testTimeout: 20_000 });

async function abrirPermissionarios() {
  const { default: Pagina } = await import("@/app/(app)/m/transporte/permissionarios/page");
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <Pagina />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getAllByRole("button", { name: /Novo permissionário/ })[0]);
  return screen.getByRole("dialog", { name: "Novo permissionário" });
}

beforeEach(() => {
  createMock.mockClear();
  registrarMock.mockClear();
});
afterEach(cleanup);

describe("formulário do permissionário", () => {
  it("não mostra erro ao abrir; ao enviar vazio mostra cada erro no campo e foca o primeiro", async () => {
    const dialogo = await abrirPermissionarios();
    expect(within(dialogo).queryByText("Informe o nome completo.")).toBeNull();

    fireEvent.click(within(dialogo).getByRole("button", { name: "Cadastrar permissionário" }));

    expect(await within(dialogo).findByText("Informe o nome completo.")).toBeInTheDocument();
    expect(within(dialogo).getByText("Informe o CPF.")).toBeInTheDocument();
    const nome = within(dialogo).getByLabelText(/Nome completo/);
    expect(nome).toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(nome).toHaveFocus());
    expect(createMock).not.toHaveBeenCalled();
  });

  it("erro aparece ao sair do campo, não enquanto digita", async () => {
    const dialogo = await abrirPermissionarios();
    const cpf = within(dialogo).getByLabelText(/^CPF/);
    fireEvent.change(cpf, { target: { value: "123456" } });
    // Máscara aplicada enquanto digita.
    expect(cpf).toHaveValue("123.456");
    expect(within(dialogo).queryByText(/CPF incompleto/)).toBeNull();
    fireEvent.blur(cpf);
    expect(await within(dialogo).findByText("CPF incompleto: use o formato 000.000.000-00.")).toBeInTheDocument();
    // Outro campo não tocado continua quieto.
    expect(within(dialogo).queryByText("Informe o nome completo.")).toBeNull();
  });

  it("CNH informada exige a validade, como o backend", async () => {
    const dialogo = await abrirPermissionarios();
    fireEvent.change(within(dialogo).getByLabelText(/Nome completo/), { target: { value: "Maria" } });
    fireEvent.change(within(dialogo).getByLabelText(/^CPF/), { target: { value: "52998224725" } });
    fireEvent.change(within(dialogo).getByLabelText(/Número da CNH/), { target: { value: "0123456789-0" } });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Cadastrar permissionário" }));
    expect(
      await within(dialogo).findByText("Informe a validade: é obrigatória quando há CNH."),
    ).toBeInTheDocument();
    expect(createMock).not.toHaveBeenCalled();

    fireEvent.change(within(dialogo).getByLabelText(/Validade da CNH/), { target: { value: "2030-01-31" } });
    fireEvent.click(within(dialogo).getByRole("button", { name: "Cadastrar permissionário" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1));
    // O que vai ao servidor não mudou de forma: o backend normaliza CPF/CNH.
    expect(createMock.mock.calls[0][0]).toMatchObject({
      nome: "Maria",
      cpf: "529.982.247-25",
      cnh_numero: "01234567890",
      cnh_validade: "2030-01-31",
      situacao: "pendente",
    });
  });
});

describe("vínculo (permissionário × empresa × os dois)", () => {
  it("o modo vem do registro e decide o que vai ao servidor", () => {
    expect(modoDoVinculo("3", "")).toBe("permissionario");
    expect(modoDoVinculo("", "7")).toBe("empresa");
    expect(modoDoVinculo("3", "7")).toBe("ambos");
    expect(idsDoVinculo("permissionario", "3", "7")).toEqual({ id_permissionario: 3, id_empresa: null });
    expect(idsDoVinculo("ambos", "3", "7")).toEqual({ id_permissionario: 3, id_empresa: 7 });
    expect(errosDoVinculo("empresa", "3", "")).toEqual({
      id_permissionario: undefined,
      id_empresa: "Escolha a empresa na lista.",
    });
  });
});

describe("datas da vigência", () => {
  it("soma meses sem pular para o mês seguinte", () => {
    expect(somarMeses("2026-01-31", 1)).toBe("2026-02-28");
    expect(somarMeses("2026-11-10", 24)).toBe("2028-11-10");
  });

  it("descreve a duração e o prazo", () => {
    expect(duracaoLegivel("2026-11-10", "2028-05-10")).toBe("1 ano e 6 meses");
    expect(duracaoLegivel("2026-11-10", "2026-11-25")).toBe("15 dias");
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 10, 12));
    expect(dicaVigencia("2026-11-10", "2027-11-10", "x")).toBe("Vigência de 1 ano — vence em 365 dias.");
    expect(dicaVigencia("", "2026-11-07", "x")).toBe("Venceu há 3 dias.");
    expect(dicaVigencia("", "", "padrão")).toBe("padrão");
    vi.useRealTimers();
  });

  it("validade antes do início é erro", () => {
    expect(erroValidade("2026-11-10", "2026-11-09")).toMatch(/não pode ser antes do início/);
    expect(erroValidade("2026-11-10", "")).toBeUndefined();
  });
});

async function renderizar(caminho: () => Promise<{ default: React.ComponentType }>) {
  const { default: Pagina } = await caminho();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ConfirmProvider>
          <Pagina />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("registrar ocorrência", () => {
  it("sem alvo, o erro é do grupo; a data do fato já vem com hoje", async () => {
    await renderizar(() => import("@/app/(app)/m/transporte/ocorrencias/page"));
    fireEvent.click(screen.getAllByRole("button", { name: /Registrar ocorrência/ })[0]);
    const dialogo = screen.getByRole("dialog", { name: "Registrar ocorrência" });

    expect(within(dialogo).getByLabelText(/Data do fato/)).not.toHaveValue("");
    fireEvent.click(within(dialogo).getByRole("button", { name: "Registrar ocorrência" }));

    const grupo = within(dialogo).getByRole("group", { name: "Alvo da ocorrência" });
    expect(grupo).toHaveAttribute("aria-invalid", "true");
    expect(
      within(dialogo).getByText("Escolha ao menos um alvo: permissionário, empresa ou veículo."),
    ).toBeInTheDocument();
    expect(within(dialogo).getByText("Escolha o tipo da ocorrência.")).toBeInTheDocument();
    expect(within(dialogo).getByText("Descreva o que aconteceu.")).toBeInTheDocument();
    // Foco no primeiro inválido: o grupo de alvos, que vem antes no formulário.
    await waitFor(() => expect(grupo).toHaveFocus());
    expect(registrarMock).not.toHaveBeenCalled();
  });
});

describe("ciclo de recadastramento", () => {
  it("mostra o prazo de cada final de documento antes de criar", async () => {
    await renderizar(() => import("@/app/(app)/m/transporte/recadastramento/page"));
    fireEvent.click(screen.getAllByRole("button", { name: /Novo ciclo/ })[0]);
    const dialogo = screen.getByRole("dialog", { name: "Novo ciclo de recadastramento" });
    expect(within(dialogo).queryByText("Prazo por final do documento")).toBeNull();

    fireEvent.change(within(dialogo).getByLabelText(/^Início/), { target: { value: "2026-01-01" } });
    fireEvent.change(within(dialogo).getByLabelText(/^Fim/), { target: { value: "2026-01-31" } });

    expect(within(dialogo).getByText("Prazo por final do documento")).toBeInTheDocument();
    // 30 dias em 10 faixas: final 0 até o dia 4, final 9 no último dia.
    const final0 = within(dialogo).getByText("Final 0").parentElement!;
    expect(final0).toHaveTextContent("04/01");
    expect(within(dialogo).getByText("Final 9").parentElement!).toHaveTextContent("31/01");
    expect(within(dialogo).getByText("Janela de 30 dias.")).toBeInTheDocument();

    // "Todos no fim" não escalona: a prévia some.
    fireEvent.click(within(dialogo).getByRole("radio", { name: "Todos no fim" }));
    expect(within(dialogo).queryByText("Prazo por final do documento")).toBeNull();
  });
});

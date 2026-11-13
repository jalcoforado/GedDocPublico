/**
 * Formulários da Frota: o erro aparece sob o campo (e não numa caixa
 * vermelha no fim), só depois de sair do campo ou de tentar enviar; o envio
 * com erro leva o foco ao primeiro campo a consertar e não chama a API; o
 * botão principal diz o que faz ("Cadastrar veículo", não "Salvar").
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: ["frota"],
    loading: false,
    can: () => true,
  }),
}));

const VEICULOS = [
  {
    id: 10,
    placa: "ABC1D23",
    marca: "Fiat",
    modelo: "Strada",
    situacao: "disponivel",
    quilometragem_atual: 12000,
    tipo_combustivel: "diesel",
    id_unidade_responsavel: null,
    forma_posse: "proprio",
  },
];

const criarVeiculo = vi.fn((_d: unknown) => Promise.resolve({}));
const criarMotorista = vi.fn((_d: unknown) => Promise.resolve({}));
const criarAbastecimento = vi.fn((_d: unknown) => Promise.resolve({}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      unidades: { ...actual.api.unidades, list: () => Promise.resolve({ items: [] }) },
      frota: {
        ...actual.api.frota,
        listAll: () => Promise.resolve(VEICULOS),
        create: (d: unknown) => criarVeiculo(d),
      },
      motoristas: {
        ...actual.api.motoristas,
        listAll: () => Promise.resolve([]),
        create: (d: unknown) => criarMotorista(d),
      },
      abastecimentos: {
        ...actual.api.abastecimentos,
        list: () => Promise.resolve([]),
        resumo: () =>
          Promise.resolve({
            total_abastecimentos: 0,
            total_litros: 0,
            total_valor: 0,
            media_valor_litro: null,
            ultimo_abastecimento: null,
          }),
        create: (d: unknown) => criarAbastecimento(d),
      },
    },
  };
});

async function abrirPagina(caminho: "veiculos" | "motoristas" | "abastecimentos") {
  const mod =
    caminho === "veiculos"
      ? await import("@/app/(app)/m/frota/veiculos/page")
      : caminho === "motoristas"
        ? await import("@/app/(app)/m/frota/motoristas/page")
        : await import("@/app/(app)/m/frota/abastecimentos/page");
  const Pagina = mod.default;
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

/** Clica no botão de criar do cabeçalho e devolve o diálogo aberto. */
async function abrirDialogo(botao: string, titulo: string) {
  const [primeiro] = await screen.findAllByRole("button", { name: botao });
  fireEvent.click(primeiro);
  return within(await screen.findByRole("dialog", { name: titulo }));
}

vi.setConfig({ testTimeout: 20_000 });

beforeEach(() => {
  criarVeiculo.mockClear();
  criarMotorista.mockClear();
  criarAbastecimento.mockClear();
});
afterEach(cleanup);

describe("veículo", () => {
  it("nada em vermelho ao abrir; o botão diz o que faz", async () => {
    await abrirPagina("veiculos");
    const d = await abrirDialogo("Novo veículo", "Novo veículo");
    expect(d.queryByText("Informe a placa.")).toBeNull();
    expect(d.getByRole("button", { name: "Cadastrar veículo" })).toBeEnabled();
    expect(d.queryByRole("button", { name: "Salvar" })).toBeNull();
  });

  it("sem placa: erro sob o campo, foco nele, API não chamada", async () => {
    await abrirPagina("veiculos");
    const d = await abrirDialogo("Novo veículo", "Novo veículo");
    fireEvent.click(d.getByRole("button", { name: "Cadastrar veículo" }));
    const placa = d.getByLabelText(/^Placa/);
    expect(await d.findByText("Informe a placa.")).toBeInTheDocument();
    expect(placa).toHaveAttribute("aria-invalid", "true");
    expect(placa).toHaveFocus();
    expect(criarVeiculo).not.toHaveBeenCalled();
  });

  it("placa fora do formato: o erro diz o formato, já ao sair do campo", async () => {
    await abrirPagina("veiculos");
    const d = await abrirDialogo("Novo veículo", "Novo veículo");
    const placa = d.getByLabelText(/^Placa/);
    fireEvent.change(placa, { target: { value: "AB12" } });
    fireEvent.blur(placa);
    expect(await d.findByText("Use o formato ABC1234 ou ABC1D23 (Mercosul).")).toBeInTheDocument();
  });

  it("placa válida: envia como antes", async () => {
    await abrirPagina("veiculos");
    const d = await abrirDialogo("Novo veículo", "Novo veículo");
    fireEvent.change(d.getByLabelText(/^Placa/), { target: { value: "abc1d23" } });
    fireEvent.click(d.getByRole("button", { name: "Cadastrar veículo" }));
    await waitFor(() => expect(criarVeiculo).toHaveBeenCalledTimes(1));
    expect(criarVeiculo.mock.calls[0][0]).toMatchObject({
      placa: "ABC1D23",
      forma_posse: "proprio",
      situacao: "disponivel",
    });
  });
});

describe("motorista", () => {
  it("CPF com máscara na tela e só dígitos no envio", async () => {
    await abrirPagina("motoristas");
    const d = await abrirDialogo("Novo motorista", "Novo motorista");
    const cpf = d.getByLabelText(/^CPF/);
    fireEvent.change(cpf, { target: { value: "12345678901" } });
    expect(cpf).toHaveValue("123.456.789-01");

    fireEvent.change(d.getByLabelText(/^Nome completo/), { target: { value: "Ana" } });
    fireEvent.change(d.getByLabelText(/^Número da CNH/), { target: { value: "01234567890" } });
    fireEvent.change(d.getByLabelText(/^Validade/), { target: { value: "2030-01-01" } });
    fireEvent.click(d.getByRole("button", { name: "Cadastrar motorista" }));
    await waitFor(() => expect(criarMotorista).toHaveBeenCalledTimes(1));
    expect(criarMotorista.mock.calls[0][0]).toMatchObject({ cpf: "12345678901", nome: "Ana" });
  });

  it("CPF incompleto: o erro diz quantos dígitos", async () => {
    await abrirPagina("motoristas");
    const d = await abrirDialogo("Novo motorista", "Novo motorista");
    const cpf = d.getByLabelText(/^CPF/);
    fireEvent.change(cpf, { target: { value: "1234" } });
    fireEvent.blur(cpf);
    expect(await d.findByText("O CPF tem 11 dígitos: 000.000.000-00.")).toBeInTheDocument();
  });
});

describe("abastecimento", () => {
  it("cada erro sob o seu campo; o foco vai ao primeiro (o veículo)", async () => {
    await abrirPagina("abastecimentos");
    const d = await abrirDialogo("Novo abastecimento", "Novo abastecimento");
    fireEvent.click(d.getByRole("button", { name: "Registrar abastecimento" }));
    expect(await d.findByText("Escolha o veículo.")).toBeInTheDocument();
    expect(d.getByText("Informe a quilometragem do painel.")).toBeInTheDocument();
    expect(d.getByText("Informe quantos litros foram abastecidos.")).toBeInTheDocument();
    expect(d.getByText("Informe o valor pago.")).toBeInTheDocument();
    expect(d.getByLabelText(/^Veículo/)).toHaveFocus();
    expect(criarAbastecimento).not.toHaveBeenCalled();
  });

  it("mostra o preço por litro enquanto se digita e traz o combustível do veículo", async () => {
    await abrirPagina("abastecimentos");
    const d = await abrirDialogo("Novo abastecimento", "Novo abastecimento");
    // Espera a lista de veículos chegar ao select.
    await d.findByRole("option", { name: "ABC1D23 — Fiat Strada" });
    fireEvent.change(d.getByLabelText(/^Veículo/), { target: { value: "10" } });
    expect(d.getByLabelText(/^Combustível/)).toHaveValue("diesel");

    fireEvent.change(d.getByLabelText(/^Litros/), { target: { value: "40" } });
    fireEvent.change(d.getByLabelText(/^Valor total/), { target: { value: "250" } });
    expect(d.getByText(/6,25 por litro/)).toBeInTheDocument();

    fireEvent.change(d.getByLabelText(/^Quilometragem/), { target: { value: "12100" } });
    fireEvent.click(d.getByRole("button", { name: "Registrar abastecimento" }));
    await waitFor(() => expect(criarAbastecimento).toHaveBeenCalledTimes(1));
    expect(criarAbastecimento.mock.calls[0][0]).toMatchObject({
      id_veiculo: 10,
      km_atual: 12100,
      litros: 40,
      valor_total: 250,
      tipo_combustivel: "diesel",
    });
  });
});

/**
 * Cadastro do cidadão — padrão de formulário (2026-11-10).
 *
 * O que trava: máscara de CPF/CNPJ na digitação, erro só depois de sair do
 * campo ou de tentar enviar, foco no primeiro campo com problema, e o
 * contrato com o backend — o documento vai SÓ com números (o cadastro aceita
 * no máximo 14 caracteres; o CNPJ pontuado tem 18).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CidadaoCadastrarPage from "@/app/cidadao/cadastrar/page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    cidadao: {
      cadastrar: vi.fn(),
      login: vi.fn(),
      reenviarConfirmacao: vi.fn(),
    },
  },
}));
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

const cadastrarMock = api.cidadao.cadastrar as ReturnType<typeof vi.fn>;

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CidadaoCadastrarPage />
    </QueryClientProvider>,
  );
}

const doc = () => screen.getByLabelText(/CPF ou CNPJ/i) as HTMLInputElement;

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Cadastro do cidadão — máscara do documento", () => {
  it("pontua o CPF enquanto digita e vira CNPJ a partir do 12º número", () => {
    renderPage();
    fireEvent.change(doc(), { target: { value: "12345678909" } });
    expect(doc().value).toBe("123.456.789-09");
    fireEvent.change(doc(), { target: { value: "11222333000181" } });
    expect(doc().value).toBe("11.222.333/0001-81");
  });

  it("aceita o número já pontuado (colado)", () => {
    renderPage();
    fireEvent.change(doc(), { target: { value: "123.456.789-09" } });
    expect(doc().value).toBe("123.456.789-09");
  });
});

describe("Cadastro do cidadão — validação", () => {
  it("não mostra erro nenhum ao abrir", () => {
    renderPage();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull();
  });

  it("CPF incompleto só acusa depois de sair do campo, dizendo quanto falta", () => {
    renderPage();
    fireEvent.change(doc(), { target: { value: "1234567" } });
    expect(screen.queryByText(/Faltam 4 números do CPF/i)).toBeNull();
    fireEvent.blur(doc());
    expect(screen.getByText(/Faltam 4 números do CPF/i)).toBeInTheDocument();
    expect(doc()).toHaveAttribute("aria-invalid", "true");
  });

  it("CPF com dígito errado é recusado antes de criar conta com o documento de outra pessoa", () => {
    renderPage();
    fireEvent.change(doc(), { target: { value: "12345678900" } });
    fireEvent.blur(doc());
    expect(screen.getByText(/Esse CPF não existe/i)).toBeInTheDocument();
  });

  it("enviar vazio: resumo no topo, erro em cada campo, foco no primeiro e nada vai à API", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Criar conta/i }));
    expect(await screen.findByText(/Falta acertar 4 campos/i)).toBeInTheDocument();
    expect(screen.getByText(/Digite o seu nome completo/i)).toBeInTheDocument();
    expect(screen.getByText(/Digite o seu CPF/i)).toBeInTheDocument();
    expect(screen.getByText(/Digite o seu e-mail/i)).toBeInTheDocument();
    expect(screen.getByText(/A senha precisa ter pelo menos 8/i)).toBeInTheDocument();
    // Telefone é opcional: vazio não é erro.
    expect(screen.getByLabelText(/Telefone/i)).not.toHaveAttribute("aria-invalid", "true");
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(/Nome completo/i)));
    expect(cadastrarMock).not.toHaveBeenCalled();
  });

  it("e-mail sem domínio explica o formato", () => {
    renderPage();
    const email = screen.getByLabelText(/^E-mail/i);
    fireEvent.change(email, { target: { value: "maria@gmail" } });
    fireEvent.blur(email);
    expect(screen.getByText(/maria@gmail\.com/i)).toBeInTheDocument();
  });

  it("a regra da senha fica à vista e marca quando é cumprida", () => {
    renderPage();
    const regra = screen.getByText(/Pelo menos 8 caracteres/i);
    expect(regra.className).not.toMatch(/success/);
    fireEvent.change(screen.getByLabelText(/Crie uma senha/i), { target: { value: "segredo123" } });
    expect(screen.getByText(/Pelo menos 8 caracteres/i).className).toMatch(/success/);
  });
});

describe("Cadastro do cidadão — contrato com o backend", () => {
  it("manda o documento só com números e o telefone formatado", async () => {
    cadastrarMock.mockResolvedValue({ email_verificado_em: null });
    renderPage();
    fireEvent.change(screen.getByLabelText(/Nome completo/i), { target: { value: "Maria da Silva" } });
    fireEvent.change(doc(), { target: { value: "123.456.789-09" } });
    fireEvent.change(screen.getByLabelText(/^E-mail/i), { target: { value: "maria@gmail.com" } });
    fireEvent.change(screen.getByLabelText(/Telefone/i), { target: { value: "85999998888" } });
    fireEvent.change(screen.getByLabelText(/Crie uma senha/i), { target: { value: "segredo123" } });
    fireEvent.click(screen.getByRole("button", { name: /Criar conta/i }));

    await waitFor(() => expect(cadastrarMock).toHaveBeenCalledTimes(1));
    expect(cadastrarMock.mock.calls[0][0]).toEqual({
      cpf_cnpj: "12345678909",
      nome: "Maria da Silva",
      email: "maria@gmail.com",
      senha: "segredo123",
      telefone: "(85) 99999-8888",
      telefone_whatsapp: false,
    });
    // Conta por e-mail ligada: tela de "confirme o e-mail".
    expect(await screen.findByText(/Falta só confirmar o seu e-mail/i)).toBeInTheDocument();
  });
});

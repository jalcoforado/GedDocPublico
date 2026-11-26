import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CrudPage, type CrudField } from "@/components/CrudPage";
import { ConfirmProvider } from "@/components/ui/confirm";
import { ToastProvider } from "@/components/ui/toast";

interface Pessoa {
  id: number;
  tipo: string;
  nome: string;
  doc: string | null;
  fone: string | null;
  email: string | null;
  ativo: boolean;
}

const CAMPOS: CrudField<Pessoa>[] = [
  {
    name: "tipo",
    label: "Tipo",
    type: "select",
    required: true,
    options: [
      { value: "F", label: "Física" },
      { value: "J", label: "Jurídica" },
    ],
  },
  { name: "ativo", label: "Situação", type: "checkbox", textoAoLado: "Ativo" },
  { name: "nome", label: "Nome", type: "text", required: true },
  {
    name: "doc",
    label: (f) => (f.tipo === "J" ? "CNPJ" : "CPF"),
    type: "text",
    required: true,
    mascara: (f) => (f.tipo === "J" ? "cnpj" : "cpf"),
  },
  { name: "fone", label: "Residencial", type: "text", mascara: "telefone" },
  { name: "email", label: "E-mail", type: "email", required: true },
];

function renderizar() {
  const createFn = vi.fn(async (d: any) => ({ id: 1, ...d }));
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <ToastProvider>
        <ConfirmProvider>
          <CrudPage<Pessoa>
            title="Pessoas"
            queryKey={["pessoas"]}
            fetchList={async () => []}
            createFn={createFn}
            updateFn={vi.fn()}
            deleteFn={vi.fn()}
            columns={[{ header: "Nome", render: (r) => r.nome }]}
            fields={CAMPOS}
            emptyForm={{ tipo: "F", nome: "", doc: "", fone: "", email: "", ativo: true }}
          />
        </ConfirmProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
  fireEvent.click(screen.getByRole("button", { name: "Novo" }));
  return { createFn };
}

// Rótulo de obrigatório termina em "*" (o asterisco é aria-hidden, mas entra no texto).
const rotulo = (nome: string) => new RegExp(`^${nome}\\*?$`);
const salvar = () => fireEvent.click(screen.getByRole("button", { name: /^(Cadastrar|Salvar alterações)/ }));
const digitar = (label: string | RegExp, value: string) =>
  fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe("CrudPage — validação antes de enviar", () => {
  it("obrigatório vazio não chega ao servidor e o campo é marcado", async () => {
    const { createFn } = renderizar();
    salvar();

    expect(await screen.findAllByText("Campo obrigatório.")).toHaveLength(3);
    expect(screen.getByLabelText(rotulo("Nome"))).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText(rotulo("Nome"))).toHaveAccessibleDescription("Campo obrigatório.");
    expect(createFn).not.toHaveBeenCalled();
  });

  it("documento incompleto e e-mail inválido têm mensagem própria", async () => {
    const { createFn } = renderizar();
    digitar(rotulo("Nome"), "Maria");
    digitar(rotulo("CPF"), "1234");
    digitar(rotulo("E-mail"), "maria@semponto");
    salvar();

    expect(await screen.findByText("Preencha no formato ___.___.___-__.")).toBeInTheDocument();
    expect(screen.getByText("E-mail inválido.")).toBeInTheDocument();
    expect(createFn).not.toHaveBeenCalled();
  });

  it("CPF completo com dígito verificador errado é recusado", async () => {
    const { createFn } = renderizar();
    digitar(rotulo("Nome"), "Maria");
    digitar(rotulo("CPF"), "12345678900");
    digitar(rotulo("E-mail"), "maria@exemplo.com.br");
    salvar();

    expect(await screen.findByText("CPF inválido: confira os dígitos.")).toBeInTheDocument();
    expect(createFn).not.toHaveBeenCalled();
  });

  it("CNPJ alfanumérico com dígito errado é recusado, e o certo passa", async () => {
    const { createFn } = renderizar();
    digitar(rotulo("Nome"), "Empresa");
    fireEvent.change(screen.getByLabelText(rotulo("Tipo")), { target: { value: "J" } });
    digitar(rotulo("CNPJ"), "12ABC34501DE36");
    digitar(rotulo("E-mail"), "contato@empresa.com.br");
    salvar();
    expect(await screen.findByText("CNPJ inválido: confira os dígitos.")).toBeInTheDocument();
    expect(createFn).not.toHaveBeenCalled();

    digitar(rotulo("CNPJ"), "12ABC34501DE35");
    salvar();
    await waitFor(() => expect(createFn).toHaveBeenCalled());
    expect(createFn.mock.calls[0][0]).toMatchObject({ doc: "12.ABC.345/01DE-35" });
  });

  it("corrigir o campo apaga o erro dele", async () => {
    renderizar();
    salvar();
    await screen.findAllByText("Campo obrigatório.");

    digitar(rotulo("Nome"), "Maria");
    expect(screen.getByLabelText(rotulo("Nome"))).not.toHaveAttribute("aria-invalid");
    expect(screen.getAllByText("Campo obrigatório.")).toHaveLength(2);
  });

  it("envia o valor formatado e opcional vazio como null", async () => {
    const { createFn } = renderizar();
    digitar(rotulo("Nome"), "Maria");
    digitar(rotulo("CPF"), "12345678909");
    digitar(rotulo("E-mail"), "maria@exemplo.com.br");
    salvar();

    await waitFor(() => expect(createFn).toHaveBeenCalled());
    expect(createFn.mock.calls[0][0]).toMatchObject({
      doc: "123.456.789-09",
      fone: null,
      email: "maria@exemplo.com.br",
      ativo: true,
    });
  });
});

describe("CrudPage — máscara e guia no fundo", () => {
  it("formata enquanto digita e a guia mostra o que falta", () => {
    renderizar();
    digitar(rotulo("CPF"), "1234");

    expect(screen.getByLabelText(rotulo("CPF"))).toHaveValue("123.4");
    expect(screen.getByTestId("guia-doc")).toHaveTextContent("123.4__.___-__");
  });

  it("rótulo e máscara seguem o tipo escolhido", () => {
    renderizar();
    digitar(rotulo("CPF"), "12345678000190");
    fireEvent.change(screen.getByLabelText(rotulo("Tipo")), { target: { value: "J" } });

    // os mesmos dígitos, agora como CNPJ (o CPF tinha cortado em 11)
    expect(screen.getByLabelText(rotulo("CNPJ"))).toHaveValue("12.345.678/000");
    digitar(rotulo("CNPJ"), "12345678000190");
    expect(screen.getByLabelText(rotulo("CNPJ"))).toHaveValue("12.345.678/0001-90");
  });

  it("telefone passa de fixo para celular no 11º dígito", () => {
    renderizar();
    digitar("Residencial", "8533334444");
    expect(screen.getByLabelText("Residencial")).toHaveValue("(85) 3333-4444");
    digitar("Residencial", "85333344445");
    expect(screen.getByLabelText("Residencial")).toHaveValue("(85) 33334-4445");
  });

  it("checkbox com texto ao lado responde pelo texto", () => {
    renderizar();
    const ativo = screen.getByLabelText(/Ativo/);
    expect(ativo).toBeChecked();
    fireEvent.click(screen.getByText("Ativo"));
    expect(ativo).not.toBeChecked();
  });
});

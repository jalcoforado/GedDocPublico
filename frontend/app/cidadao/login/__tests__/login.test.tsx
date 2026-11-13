/**
 * Login do cidadão — máscara, erro depois da tentativa e contrato.
 * (O gov.br tem o seu próprio teste em `__tests__/cidadao-login-govbr.test.tsx`.)
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const login = vi.fn();
const esqueciSenha = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      cidadao: {
        ...real.api.cidadao,
        govbrDisponivel: () => Promise.resolve({ disponivel: false }),
        login: (...a: unknown[]) => login(...a),
        esqueciSenha: (...a: unknown[]) => esqueciSenha(...a),
      },
    },
  };
});
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));
vi.mock("@/lib/branding", () => ({ useBranding: () => ({ conta_por_email: true }) }));

import CidadaoLoginPage from "@/app/cidadao/login/page";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <CidadaoLoginPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.history.replaceState({}, "", "/cidadao/login");
});

describe("login do cidadão — formulário", () => {
  it("pontua o CPF e manda só os números ao backend", async () => {
    login.mockResolvedValue({});
    renderPage();
    const cpf = screen.getByLabelText(/CPF ou CNPJ/i) as HTMLInputElement;
    fireEvent.change(cpf, { target: { value: "12345678909" } });
    expect(cpf.value).toBe("123.456.789-09");
    fireEvent.change(screen.getByLabelText(/^Senha/i), { target: { value: "segredo123" } });
    fireEvent.click(screen.getByRole("button", { name: /^Entrar$/i }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("12345678909", "segredo123"));
    await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/cidadao/processos"));
  });

  it("sem erro ao abrir; enviar vazio diz o que falta embaixo de cada campo e não chama a API", async () => {
    renderPage();
    expect(document.querySelector('[aria-invalid="true"]')).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Entrar$/i }));
    expect(await screen.findByText(/Digite o seu CPF/i)).toBeInTheDocument();
    expect(screen.getByText(/Digite a sua senha/i)).toBeInTheDocument();
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText(/CPF ou CNPJ/i)));
    expect(login).not.toHaveBeenCalled();
  });

  it("'Enviar link' de nova senha não fica desabilitado: clicar mostra o que falta", async () => {
    esqueciSenha.mockResolvedValue({ detail: "Se houver cadastro, enviamos o link." });
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Esqueci minha senha/i }));
    const enviar = await screen.findByRole("button", { name: /Enviar link/i });
    expect(enviar).not.toBeDisabled();
    fireEvent.click(enviar);
    expect(await screen.findByText(/Digite o seu CPF/i)).toBeInTheDocument();
    expect(esqueciSenha).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/CPF ou CNPJ/i), { target: { value: "123.456.789-09" } });
    fireEvent.click(enviar);
    await waitFor(() => expect(esqueciSenha).toHaveBeenCalledWith("12345678909"));
    expect(await screen.findByText(/O link vale por 1 hora/i)).toBeInTheDocument();
  });
});

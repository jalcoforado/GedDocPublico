/**
 * /validar — o código chega de todo jeito: digitado, copiado do PDF (com
 * espaço ou quebra de linha no meio) ou como o link inteiro do QR code.
 * O formulário aceita os três e manda só o código para a tela de resultado.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { normalizarCodigoValidacao } from "@/components/cidadao/codigo-validacao";

const pushMock = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: pushMock }) }));

import ValidarFormPage from "@/app/validar/page";

beforeEach(() => pushMock.mockReset());

describe("normalizarCodigoValidacao", () => {
  it.each([
    ["aB3dE-fG7h_iJ9kLmN0pQr", "aB3dE-fG7h_iJ9kLmN0pQr"],
    ["  aB3dE-fG7h_iJ9kLmN0pQr  ", "aB3dE-fG7h_iJ9kLmN0pQr"],
    ["aB3dE-fG7h\n_iJ9k LmN0pQr", "aB3dE-fG7h_iJ9kLmN0pQr"],
    ["https://itaitinga.aprimora.app/validar/aB3dE-fG7h_iJ9kLmN0pQr", "aB3dE-fG7h_iJ9kLmN0pQr"],
    ["https://x.app/validar/aB3dE-fG7h_iJ9kLmN0pQr?utm=qr#topo", "aB3dE-fG7h_iJ9kLmN0pQr"],
    ["“aB3dE-fG7h_iJ9kLmN0pQr”.", "aB3dE-fG7h_iJ9kLmN0pQr"],
  ])("%j → %j", (entrada, esperado) => {
    expect(normalizarCodigoValidacao(entrada)).toBe(esperado);
  });

  it("preserva maiúsculas/minúsculas, hífen e sublinhado (fazem parte do código)", () => {
    expect(normalizarCodigoValidacao("Ab-_Cd")).toBe("Ab-_Cd");
  });
});

describe("/validar — formulário", () => {
  it("cola o link do QR e vai para o resultado só com o código", () => {
    render(<ValidarFormPage />);
    fireEvent.change(screen.getByLabelText(/Código de validação/i), {
      target: { value: "https://x.app/validar/aB3dE-fG7h_iJ9kLmN0pQr" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Validar$/i }));
    expect(pushMock).toHaveBeenCalledWith("/validar/aB3dE-fG7h_iJ9kLmN0pQr");
  });

  it("botão nunca desabilitado: vazio mostra o que fazer e não navega", () => {
    render(<ValidarFormPage />);
    const botao = screen.getByRole("button", { name: /^Validar$/i });
    expect(botao).not.toBeDisabled();
    fireEvent.click(botao);
    expect(screen.getByText(/Digite ou cole o código/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Código de validação/i)).toHaveAttribute("aria-invalid", "true");
    expect(pushMock).not.toHaveBeenCalled();
  });
});

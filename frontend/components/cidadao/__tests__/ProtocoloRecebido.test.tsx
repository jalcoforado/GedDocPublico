/**
 * Confirmação do pedido enviado: aparece uma vez, na tela do processo que
 * acabou de ser aberto, com o número em destaque e o que acontece agora.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { marcarProtocoloRecebido, ProtocoloRecebido } from "@/components/cidadao/ProtocoloRecebido";

beforeEach(() => sessionStorage.clear());

describe("ProtocoloRecebido", () => {
  it("sem recado, não aparece (visita comum à tela do processo)", () => {
    render(<ProtocoloRecebido idProcesso={42} numero="P000042/2026" />);
    expect(screen.queryByText(/Pedido enviado/i)).toBeNull();
  });

  it("logo depois do envio: número grande, próximos passos, e só na primeira vez", () => {
    marcarProtocoloRecebido(42);
    const { unmount } = render(<ProtocoloRecebido idProcesso={42} numero="P000042/2026" />);
    expect(screen.getByRole("heading", { name: /Pedido enviado/i })).toBeInTheDocument();
    expect(screen.getByText("P000042/2026")).toBeInTheDocument();
    expect(screen.getByText(/E agora\?/i)).toBeInTheDocument();
    expect(screen.getByText(/Meus processos/i)).toBeInTheDocument();
    unmount();

    render(<ProtocoloRecebido idProcesso={42} numero="P000042/2026" />);
    expect(screen.queryByText(/Pedido enviado/i)).toBeNull();
  });

  it("recado de outro processo não aparece aqui", () => {
    marcarProtocoloRecebido(7);
    render(<ProtocoloRecebido idProcesso={42} numero="P000042/2026" />);
    expect(screen.queryByText(/Pedido enviado/i)).toBeNull();
  });

  it("'Entendi' fecha", () => {
    marcarProtocoloRecebido(42);
    render(<ProtocoloRecebido idProcesso={42} numero="P000042/2026" />);
    fireEvent.click(screen.getByRole("button", { name: /Entendi/i }));
    expect(screen.queryByText(/Pedido enviado/i)).toBeNull();
  });
});

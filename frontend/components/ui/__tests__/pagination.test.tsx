/**
 * UX-02 fatia 2.5 — Pagination com page-size. Contrato alinhado ao
 * Paginated<T> do backend (page, page_size, total).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Pagination } from "@/components/ui/pagination";

describe("Pagination", () => {
  it("mostra o intervalo e o total; anterior desabilitado na primeira página", () => {
    render(
      <Pagination page={1} pageSize={20} total={45} onPageChange={() => {}} />,
    );
    expect(screen.getByText(/1[–-]20 de 45/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /anterior/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /próxima/i })).toBeEnabled();
  });

  it("próxima chama onPageChange com page+1; na última, desabilita", async () => {
    const onPageChange = vi.fn();
    const { rerender } = render(
      <Pagination page={2} pageSize={20} total={45} onPageChange={onPageChange} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /próxima/i }));
    expect(onPageChange).toHaveBeenCalledWith(3);

    rerender(
      <Pagination page={3} pageSize={20} total={45} onPageChange={onPageChange} />,
    );
    expect(screen.getByRole("button", { name: /próxima/i })).toBeDisabled();
  });

  it("com onPageSizeChange, expõe o seletor de itens por página e volta à página 1 ao trocar", async () => {
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();
    render(
      <Pagination
        page={3}
        pageSize={20}
        total={100}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />,
    );
    const seletor = screen.getByLabelText(/por página/i);
    await userEvent.selectOptions(seletor, "50");
    expect(onPageSizeChange).toHaveBeenCalledWith(50);
    expect(onPageChange).toHaveBeenCalledWith(1);
  });

  it("sem onPageSizeChange, o seletor não aparece", () => {
    render(<Pagination page={1} pageSize={20} total={45} onPageChange={() => {}} />);
    expect(screen.queryByLabelText(/por página/i)).toBeNull();
  });

  it("total zero: 0 de 0, ambos os botões desabilitados", () => {
    render(<Pagination page={1} pageSize={20} total={0} onPageChange={() => {}} />);
    expect(screen.getByText(/0 de 0/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /anterior/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /próxima/i })).toBeDisabled();
  });
});

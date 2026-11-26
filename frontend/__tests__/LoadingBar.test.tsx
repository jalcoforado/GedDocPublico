/**
 * A barra do topo começa no CLIQUE (não depois que a tela nova já carregou) e
 * fecha quando a URL nova é publicada no history. Busca em segundo plano não
 * a acende — antes o sino e os contadores faziam a barra piscar sozinha.
 */
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/home" }));

import { LoadingBar } from "@/components/LoadingBar";

function BuscaDeFundo() {
  useQuery({ queryKey: ["fundo"], queryFn: () => new Promise(() => {}) });
  return null;
}

function montar(extra?: React.ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <LoadingBar />
      <a href="/m/frota">Frota</a>
      <a href="/home">Aqui mesmo</a>
      <a href="/m/frota" target="_blank">Nova aba</a>
      {extra}
    </QueryClientProvider>,
  );
}

// O jsdom não navega; o clique só precisa chegar ao listener de captura.
const clicar = (texto: string) => {
  const a = screen.getByText(texto);
  a.addEventListener("click", (e) => e.preventDefault(), { once: true });
  fireEvent.click(a);
};

beforeEach(() => {
  window.history.replaceState({}, "", "/home");
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

describe("barra de progresso do topo", () => {
  it("acende no clique de um link interno e fecha quando a URL nova chega", () => {
    montar();
    expect(screen.queryByRole("progressbar")).toBeNull();
    clicar("Frota");
    expect(screen.getByRole("progressbar")).toBeInTheDocument();

    act(() => window.history.pushState({}, "", "/m/frota"));
    act(() => vi.advanceTimersByTime(600));
    expect(screen.queryByRole("progressbar")).toBeNull();
    window.history.replaceState({}, "", "/home");
  });

  it("não acende para a própria tela nem para link em nova aba", () => {
    montar();
    clicar("Aqui mesmo");
    clicar("Nova aba");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("busca em segundo plano não acende a barra", () => {
    montar(<BuscaDeFundo />);
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("navegação que nunca conclui não deixa a barra presa", () => {
    montar();
    clicar("Frota");
    act(() => vi.advanceTimersByTime(10_600));
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

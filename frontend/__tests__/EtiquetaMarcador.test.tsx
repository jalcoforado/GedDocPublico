/**
 * Marcadores numa linha de listagem: no máximo três etiquetas, "+N" para o
 * resto, e a lista inteira para o leitor de tela.
 *
 * A cor do marcador vem do cadastro e pode ser qualquer uma — por isso ela vai
 * só na bolinha, e há teste de que o NOME não é pintado com ela.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { EtiquetaMarcador, MarcadoresDaLinha } from "@/components/EtiquetaMarcador";
import { MarcadoresProcesso } from "@/components/MarcadoresProcesso";
import { ToastProvider } from "@/components/ui/toast";
import type { MarcadorMini, ProcessoDetail } from "@/lib/api";

const COR = "rgb(250, 220, 0)";
const mk = (id: number, nome: string): MarcadorMini => ({ id, nome, cor: COR });

describe("EtiquetaMarcador", () => {
  it("mostra o nome, com a cor do cadastro só na bolinha", () => {
    const { container } = render(<EtiquetaMarcador marcador={mk(1, "Aguardando parecer")} />);
    const etiqueta = screen.getByTitle("Aguardando parecer");
    expect(etiqueta.textContent).toBe("Aguardando parecer");
    expect(etiqueta.style.color).toBe("");
    expect(etiqueta.style.backgroundColor).toBe("");
    const bolinha = container.querySelector('[aria-hidden="true"]') as HTMLElement;
    expect(bolinha.style.backgroundColor).toBe(COR);
  });
});

describe("MarcadoresDaLinha", () => {
  it("sem marcadores não desenha nada", () => {
    const { container } = render(<MarcadoresDaLinha marcadores={[]} />);
    expect(container.innerHTML).toBe("");
    const { container: c2 } = render(<MarcadoresDaLinha marcadores={undefined} />);
    expect(c2.innerHTML).toBe("");
  });

  it("até três, mostra todos e não mostra +N", () => {
    render(<MarcadoresDaLinha marcadores={[mk(1, "A"), mk(2, "B"), mk(3, "C")]} />);
    expect(screen.getByTitle("A")).toBeTruthy();
    expect(screen.getByTitle("B")).toBeTruthy();
    expect(screen.getByTitle("C")).toBeTruthy();
    expect(screen.queryByText(/^\+\d+$/)).toBeNull();
  });

  it("mais de três vira +N, com os nomes escondidos no title", () => {
    render(
      <MarcadoresDaLinha
        marcadores={[mk(1, "A"), mk(2, "B"), mk(3, "C"), mk(4, "D"), mk(5, "E")]}
      />,
    );
    expect(screen.queryByTitle("D")).toBeNull();
    const mais = screen.getByText("+2");
    expect(mais.getAttribute("title")).toBe("D, E");
  });

  it("leitor de tela recebe a lista inteira num texto só", () => {
    render(<MarcadoresDaLinha marcadores={[mk(1, "A"), mk(2, "B"), mk(3, "C"), mk(4, "D")]} />);
    const sr = screen.getByText("Marcadores: A, B, C, D");
    expect(sr.className).toContain("sr-only");
    // As etiquetas visíveis ficam fora da árvore de acessibilidade, para não
    // serem lidas duas vezes.
    expect(screen.getByTitle("A").closest('[aria-hidden="true"]')).not.toBeNull();
  });
});

describe("corte do nome: só na listagem", () => {
  const LONGO = "Aguardando parecer da Procuradoria";

  it("na listagem o nome é cortado e o inteiro fica no title", () => {
    render(<EtiquetaMarcador marcador={mk(1, LONGO)} />);
    expect(screen.getByTitle(LONGO).className).toContain("max-w-[10rem]");
    expect(screen.getByText(LONGO).className).toContain("truncate");
  });

  it("no detalhe do processo o nome aparece inteiro, sem truncate", () => {
    // O detalhe é para onde a lista manda quem quer ler o nome: lá não pode
    // haver corte, porque o title não aparece no toque nem no teclado.
    const processo = { marcadores: [mk(1, LONGO)] } as unknown as ProcessoDetail;
    render(
      <QueryClientProvider client={new QueryClient()}>
        <ToastProvider>
          <MarcadoresProcesso processo={processo} podeEditar={false} />
        </ToastProvider>
      </QueryClientProvider>,
    );
    const nome = screen.getByText(LONGO);
    expect(nome.className).not.toContain("truncate");
    expect(nome.parentElement!.className).not.toContain("max-w-[10rem]");
  });
});

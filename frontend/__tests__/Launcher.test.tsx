/**
 * O launcher. O modo de falha que importa é a TELA EM BRANCO: já custou um PR
 * neste projeto, e o F1 teve um Critical exatamente porque o teste do endpoint
 * passava com lista vazia. Aqui, lista vazia tem de aparecer como mensagem
 * explícita, não como página muda.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push }) }));

const modulos = vi.fn();
vi.mock("@/lib/api", () => ({ api: { modulos: () => modulos() } }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { nome: "Teste" }, loading: false }) }));

import Launcher from "@/app/(launcher)/modulos/page";

const TRES = {
  itens: [
    { slug: "protocolo", nome: "Protocolo", icone: "FileText", ordem: 1 },
    { slug: "frota", nome: "Frota", icone: "Truck", ordem: 3 },
    { slug: "pagamentos", nome: "Pagamentos", icone: "Wallet", ordem: 2 },
  ],
};

describe("launcher", () => {
  it("mostra um card por módulo, na ordem do catálogo", async () => {
    modulos.mockResolvedValue(TRES);
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText("Protocolo")).toBeTruthy());
    const nomes = screen.getAllByRole("link").map((a) => a.textContent);
    expect(nomes[0]).toContain("Protocolo");
    expect(nomes[1]).toContain("Pagamentos"); // ordem 2 antes de ordem 3
    expect(nomes[2]).toContain("Frota");
  });

  it("cada card aponta para a raiz do módulo", async () => {
    modulos.mockResolvedValue(TRES);
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText("Frota")).toBeTruthy());
    const frota = screen.getAllByRole("link").find((a) => a.textContent?.includes("Frota"));
    expect(frota?.getAttribute("href")).toBe("/frotas");
  });

  it("com um módulo só, entra direto — o launcher é porta, não pedágio", async () => {
    modulos.mockResolvedValue({ itens: [TRES.itens[1]] });
    render(<Launcher />);
    await waitFor(() => expect(push).toHaveBeenCalledWith("/frotas"));
  });

  it("lista vazia mostra mensagem explícita, não tela muda", async () => {
    modulos.mockResolvedValue({ itens: [] });
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText(/nenhum módulo/i)).toBeTruthy());
  });

  it("erro de API mostra mensagem, não tela muda", async () => {
    modulos.mockRejectedValue(new Error("falhou"));
    render(<Launcher />);
    await waitFor(() => expect(screen.getByText(/não foi possível/i)).toBeTruthy());
  });
});

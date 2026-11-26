/**
 * `/modulos` depois do menu único (2026-11-05): o launcher saiu, a rota leva
 * ao Início. O modo de falha que importa continua sendo a tela muda — quem
 * tem um favorito antigo para `/modulos` tem de chegar a algum lugar.
 */
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace }) }));

import ModulosRetirado from "@/app/(launcher)/modulos/page";

describe("/modulos (launcher retirado)", () => {
  it("leva ao Início com replace — sem deixar /modulos no histórico", () => {
    render(<ModulosRetirado />);
    expect(replace).toHaveBeenCalledWith("/home");
  });
});

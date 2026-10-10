/**
 * Atalhos "Sem precisar entrar" das telas de login.
 *
 * O que não pode acontecer: um atalho público apontar para rota que o guard do
 * frontend manda para o login. Seria um link que promete acesso sem entrar e
 * devolve a própria tela de onde a pessoa saiu — e foi exatamente o estado de
 * `/validar` até o guard listá-la como pública.
 */
import { render, screen, within } from "@testing-library/react";
import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { AtalhosPublicos } from "@/components/login/comum";

import { middleware } from "../middleware";

describe("atalhos públicos do login", () => {
  it("oferece validar documento e a carta de serviços", () => {
    render(<AtalhosPublicos />);
    const nav = screen.getByRole("navigation", { name: "Acesso sem login" });
    const links = within(nav)
      .getAllByRole("link")
      .map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/validar", "/cidadao/servicos"]);
  });

  it("todo atalho abre SEM sessão — o guard do frontend não o manda para o login", () => {
    render(<AtalhosPublicos />);
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href") ?? "");
    expect(hrefs.length).toBeGreaterThan(0);
    for (const href of hrefs) {
      const res = middleware(new NextRequest(`http://sobral.aprimora.local${href}`));
      expect(res.headers.get("location"), href).toBeNull();
    }
  });
});

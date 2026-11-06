/**
 * A chave de tema é UMA chave (claro ↔ escuro), no cabeçalho. O botão
 * "seguir o sistema" saiu; sem preferência gravada o tema ainda segue o
 * sistema, mas não há mais um botão para isso.
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { ThemeToggle } from "@/components/ThemeToggle";
import { ThemeProvider } from "@/lib/theme";

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
});

describe("chave de tema", () => {
  it("é um switch só, sem a opção de seguir o sistema", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    expect(screen.getByRole("switch", { name: "Tema escuro" })).toHaveAttribute("aria-checked", "false");
    expect(screen.queryByRole("button", { name: /sistema/i })).toBeNull();
  });

  it("alterna claro ↔ escuro e grava a escolha", () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const chave = screen.getByRole("switch", { name: "Tema escuro" });
    act(() => fireEvent.click(chave));
    expect(chave).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(window.localStorage.getItem("aprimora.theme")).toBe("dark");

    act(() => fireEvent.click(chave));
    expect(chave).toHaveAttribute("aria-checked", "false");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(window.localStorage.getItem("aprimora.theme")).toBe("light");
  });
});

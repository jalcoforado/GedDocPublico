/**
 * UX-03 fatia 3.4 — Header: busca presente no mobile (ícone abre o palette;
 * antes a busca simplesmente sumia abaixo de md) e alturas unificadas em
 * h-10 nos controles do cluster.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const openSpy = vi.fn();
vi.mock("@/components/CommandPalette", () => ({
  useCommandPalette: () => ({ open: openSpy }),
}));
vi.mock("@/components/ModuloSwitcher", () => ({
  ModuloSwitcher: () => <div data-testid="switcher" />,
}));
vi.mock("@/components/NotificacoesBell", () => ({
  NotificacoesBell: () => <div data-testid="bell" />,
}));
vi.mock("@/components/AvatarDropdown", () => ({
  AvatarDropdown: () => <div data-testid="avatar" />,
}));
vi.mock("@/lib/branding", () => ({ useBranding: () => null }));

import { Header } from "@/components/Header";

describe("Header — busca no mobile (UX-03 fatia 3.4)", () => {
  it("existe um botão de busca só-ícone (visível abaixo de md) que abre o palette", () => {
    render(<Header onOpenSidebar={() => {}} />);
    const botao = screen.getByRole("button", { name: /^buscar$/i });
    expect(botao.className).toContain("md:hidden");
    fireEvent.click(botao);
    expect(openSpy).toHaveBeenCalled();
  });

  it("a busca completa continua presente a partir de md", () => {
    render(<Header onOpenSidebar={() => {}} />);
    // o wrapper da BuscaGlobal é hidden md:block
    expect(document.querySelector(".md\\:block")).not.toBeNull();
  });
});

describe("Header — alturas unificadas", () => {
  it("hambúrguer e botão de busca mobile são h-10", () => {
    render(<Header onOpenSidebar={() => {}} />);
    expect(screen.getByRole("button", { name: /abrir menu/i }).className).toContain("h-10");
    expect(screen.getByRole("button", { name: /^buscar$/i }).className).toContain("h-10");
  });
});

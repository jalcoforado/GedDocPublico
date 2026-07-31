/**
 * Layout do launcher (`/modulos`). Achado IMPORTANT do review final: a tela
 * "Nenhum módulo disponível" (e o estado de erro) não montam Header nem
 * Sidebar — sem uma saída própria no layout, um usuário sem nenhum grupo
 * fica preso sem conseguir sair, e um platform admin sem transação no
 * tenant perde o link "Plataforma" que via em /home antes desta fatia.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const logout = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({ user: { nome: "Teste" }, loading: false, logout }),
}));

const adminMe = vi.fn();
vi.mock("@/lib/api", () => ({ api: { admin: { me: () => adminMe() } } }));

import LauncherLayout from "@/app/(launcher)/layout";

beforeEach(() => {
  logout.mockClear();
  adminMe.mockReset();
  adminMe.mockResolvedValue({ is_platform_admin: false });
});

describe("layout do launcher", () => {
  it("sempre mostra 'Sair', mesmo sem nenhum módulo ou erro de rede na tela filha", async () => {
    render(
      <LauncherLayout>
        <p>Nenhum módulo disponível para o seu usuário.</p>
      </LauncherLayout>,
    );
    expect(screen.getByRole("button", { name: /sair/i })).toBeTruthy();
  });

  it("aciona logout ao clicar em 'Sair'", async () => {
    render(
      <LauncherLayout>
        <p>conteúdo</p>
      </LauncherLayout>,
    );
    screen.getByRole("button", { name: /sair/i }).click();
    expect(logout).toHaveBeenCalled();
  });

  it("platform admin vê link para /admin/tenants", async () => {
    adminMe.mockResolvedValue({ is_platform_admin: true });
    render(
      <LauncherLayout>
        <p>conteúdo</p>
      </LauncherLayout>,
    );
    const link = await waitFor(() => screen.getByRole("link", { name: /plataforma/i }));
    expect(link.getAttribute("href")).toBe("/admin/tenants");
  });

  it("usuário comum (não platform admin) não vê o link Plataforma", async () => {
    adminMe.mockResolvedValue({ is_platform_admin: false });
    render(
      <LauncherLayout>
        <p>conteúdo</p>
      </LauncherLayout>,
    );
    await waitFor(() => expect(adminMe).toHaveBeenCalled());
    expect(screen.queryByRole("link", { name: /plataforma/i })).toBeNull();
  });
});

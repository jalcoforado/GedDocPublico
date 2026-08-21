/**
 * UX-03 fatia 3.7 — AvatarDropdown: links corretos (auditoria apontava para
 * a rota legada /auditoria e vivia do 308; notificações apontavam para
 * /perfil genérico) e tema/densidade como radiogroup de verdade
 * (menuitemradio fora de um menu válido não é anunciado como opção).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { id: 1, nome: "Ana Souza", email: "ana@x.test" },
    perms: { is_super_usuario: true, permissoes: [] },
    loading: false,
    logout: vi.fn(),
  }),
}));
vi.mock("@/lib/branding", () => ({ useBranding: () => null }));

import { AvatarDropdown } from "@/components/AvatarDropdown";
import { ThemeProvider } from "@/lib/theme";

function renderAvatar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AvatarDropdown />
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /conta de ana/i }));
}

describe("AvatarDropdown — links (fatia 3.7)", () => {
  it("notificações levam a /perfil/notificacoes e auditoria à rota canônica /m/administracao/auditoria", () => {
    renderAvatar();
    abrir();
    expect(
      screen.getByRole("link", { name: /preferências de notificação/i }),
    ).toHaveAttribute("href", "/perfil/notificacoes");
    expect(screen.getByRole("link", { name: /auditoria/i })).toHaveAttribute(
      "href",
      "/m/administracao/auditoria",
    );
  });
});

describe("AvatarDropdown — tema e densidade como radiogroup (fatia 3.7)", () => {
  it("tema é um radiogroup com 3 radios e o ativo marcado", () => {
    renderAvatar();
    abrir();
    const grupo = screen.getByRole("radiogroup", { name: /tema/i });
    const radios = within(grupo).getAllByRole("radio");
    expect(radios.length).toBe(3);
    expect(radios.filter((r) => r.getAttribute("aria-checked") === "true").length).toBe(1);
  });

  it("densidade é um radiogroup com 2 radios; escolher marca a opção", () => {
    renderAvatar();
    abrir();
    const grupo = screen.getByRole("radiogroup", { name: /densidade/i });
    const compacto = within(grupo).getByRole("radio", { name: /compacto/i });
    fireEvent.click(compacto);
    expect(compacto).toHaveAttribute("aria-checked", "true");
  });
});

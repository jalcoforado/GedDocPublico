/**
 * UX-03 fatia 3.7 — AvatarDropdown: links corretos (auditoria apontava para
 * a rota legada /auditoria e vivia do 308; notificações apontavam para
 * /perfil genérico) e tema/densidade como radiogroup de verdade
 * (menuitemradio fora de um menu válido não é anunciado como opção).
 *
 * E1 (benchmark SUiTE) — "alterar setor": seletor de lotação ativa, só
 * visível com 2+ lotações (com uma só não há troca possível).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const trocarLotacaoMock = vi.fn().mockResolvedValue(undefined);
let mockUser: Record<string, unknown> = {
  id: 1,
  nome: "Ana Souza",
  email: "ana@x.test",
  id_unidade_trabalho: null,
  unidade_contexto_id: null,
  lotacoes: [],
};

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: mockUser,
    perms: { is_super_usuario: true, permissoes: [] },
    loading: false,
    logout: vi.fn(),
    trocarLotacao: trocarLotacaoMock,
  }),
}));
vi.mock("@/lib/branding", () => ({ useBranding: () => null }));

import { AvatarDropdown } from "@/components/AvatarDropdown";
import { ToastProvider } from "@/components/ui/toast";
import { ThemeProvider } from "@/lib/theme";

function renderAvatar() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <ThemeProvider>
          <AvatarDropdown />
        </ThemeProvider>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function abrir() {
  fireEvent.click(screen.getByRole("button", { name: /conta de ana/i }));
}

afterEach(() => {
  mockUser = {
    id: 1,
    nome: "Ana Souza",
    email: "ana@x.test",
    id_unidade_trabalho: null,
    unidade_contexto_id: null,
    lotacoes: [],
  };
  trocarLotacaoMock.mockClear();
});

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

describe("AvatarDropdown — lotação ativa / alterar setor (E1, benchmark SUiTE)", () => {
  it("some quando o usuário só tem uma lotação (ou nenhuma)", () => {
    mockUser.lotacoes = [{ id: 10, nome: "Setor Único", principal: true }];
    mockUser.id_unidade_trabalho = 10;
    mockUser.unidade_contexto_id = 10;
    renderAvatar();
    abrir();
    expect(screen.queryByRole("radiogroup", { name: /lotação ativa/i })).toBeNull();
  });

  it("lista as lotações e marca a ativa quando há 2 ou mais", () => {
    mockUser.lotacoes = [
      { id: 10, nome: "SEAS/ASCOI", principal: true },
      { id: 20, nome: "SEAS/CSIN", principal: false },
    ];
    mockUser.id_unidade_trabalho = 10;
    mockUser.unidade_contexto_id = 10;
    renderAvatar();
    abrir();
    const grupo = screen.getByRole("radiogroup", { name: /lotação ativa/i });
    const radios = within(grupo).getAllByRole("radio");
    expect(radios.length).toBe(2);
    expect(within(grupo).getByRole("radio", { name: /SEAS\/ASCOI/i })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(within(grupo).getByRole("radio", { name: /SEAS\/CSIN/i })).toHaveAttribute(
      "aria-checked",
      "false",
    );
  });

  it("clicar numa lotação secundária chama trocarLotacao com o id certo", async () => {
    mockUser.lotacoes = [
      { id: 10, nome: "SEAS/ASCOI", principal: true },
      { id: 20, nome: "SEAS/CSIN", principal: false },
    ];
    mockUser.id_unidade_trabalho = 10;
    mockUser.unidade_contexto_id = 10;
    renderAvatar();
    abrir();
    const grupo = screen.getByRole("radiogroup", { name: /lotação ativa/i });
    fireEvent.click(within(grupo).getByRole("radio", { name: /SEAS\/CSIN/i }));
    await waitFor(() => expect(trocarLotacaoMock).toHaveBeenCalledWith(20));
  });
});

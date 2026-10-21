/**
 * A tela inicial (painel de controle) mostra o menu do protocolo ao lado,
 * como o SEI, para quem opera processos. As demais telas gerais seguem sem
 * menu lateral, como no protótipo.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const estado: { caminho: string; perms: string[] } = { caminho: "/home", perms: [] };

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => estado.caminho,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock("@/lib/auth", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useAuth: () => ({
    user: { nome: "Teste", is_super_usuario: false },
    perms: [],
    loading: false,
    can: (codigo: string) => estado.perms.includes(codigo),
    logout: vi.fn(),
  }),
}));
vi.mock("@/lib/api", () => ({
  api: {
    admin: { me: () => Promise.resolve({ is_platform_admin: false }) },
    modulos: () => Promise.resolve({ itens: [] }),
    branding: () => Promise.resolve(null),
    processos: {
      caixas: () => Promise.resolve({
        entrada: 0, saida: 0, analise: 12, externos: 0, aguardando_assinatura: 0,
        enviado_para_assinatura: 0, arquivados: 0, recusados: 0,
      }),
    },
  },
  notificacoesApi: {
    listarMinhas: () => Promise.resolve({ nao_lidas: 0, itens: [] }),
  },
}));

import AppLayout from "@/app/(app)/layout";
import { ThemeProvider } from "@/lib/theme";

function abrir(caminho: string, perms: string[]) {
  estado.caminho = caminho;
  estado.perms = perms;
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <AppLayout>
          <p>conteúdo</p>
        </AppLayout>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("menu lateral na tela inicial", () => {
  it("quem opera processos vê o menu do protocolo, com as caixas", () => {
    abrir("/home", ["processo"]);
    expect(screen.getAllByRole("link", { name: /Caixa de entrada/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /Análise/ }).length).toBeGreaterThan(0);
  });

  it("quem não opera processos segue sem menu lateral", () => {
    abrir("/home", []);
    expect(screen.queryByRole("link", { name: /Caixa de entrada/ })).toBeNull();
  });

  it("as outras telas gerais seguem sem menu lateral", () => {
    abrir("/perfil", ["processo"]);
    expect(screen.queryByRole("link", { name: /Caixa de entrada/ })).toBeNull();
  });
});

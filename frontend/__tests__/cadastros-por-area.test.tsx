/**
 * `/cadastros` (menu por área, 2026-11-14): cadastros e configuração de
 * todos os módulos numa tela, agrupados por área. Gerada do menu — só módulos
 * contratados, só telas que a pessoa pode ver.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const onde = { pathname: "/m/pagamentos", pode: (_p: string) => true };
vi.mock("next/navigation", () => ({
  usePathname: () => onde.pathname,
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { nome: "T" }, perms: [], loading: false, can: (p: string) => onde.pode(p), logout: vi.fn() }),
}));
const modulosMock = vi.fn();
vi.mock("@/lib/api", () => ({ api: { modulos: () => modulosMock() } }));

import { CadastrosPorArea } from "@/components/CadastrosPorArea";
import { NavVisaoFinanceiro } from "@/components/pagamentos/NavVisaoFinanceiro";

const m = (slug: string, ordem: number) => ({ slug, nome: slug, icone: null, ordem });

function montar(no: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{no}</QueryClientProvider>);
}

beforeEach(() => {
  onde.pode = () => true;
  onde.pathname = "/m/pagamentos";
  modulosMock.mockReset();
});

describe("/cadastros — por área", () => {
  it("uma seção por área contratada; em Mobilidade, cada módulo com o seu nome", async () => {
    modulosMock.mockResolvedValue({ itens: [m("protocolo", 1), m("pagamentos", 2), m("frota", 3), m("transporte", 4)] });
    montar(<CadastrosPorArea />);
    const atendimento = await screen.findByRole("region", { name: "Atendimento" });
    expect(within(atendimento).getByRole("link", { name: /Manifestantes/ })).toHaveAttribute("href", "/m/protocolo/manifestantes");
    const financeiro = screen.getByRole("region", { name: "Financeiro" });
    expect(within(financeiro).getByRole("link", { name: /Fornecedores/ })).toBeInTheDocument();
    const mobilidade = screen.getByRole("region", { name: "Mobilidade" });
    expect(within(mobilidade).getByRole("heading", { name: "Frota" })).toBeInTheDocument();
    expect(within(mobilidade).getByRole("link", { name: /Motoristas/ })).toBeInTheDocument();
  });

  it("módulo não contratado não aparece", async () => {
    modulosMock.mockResolvedValue({ itens: [m("pagamentos", 1)] });
    montar(<CadastrosPorArea />);
    await screen.findByRole("region", { name: "Financeiro" });
    expect(screen.queryByRole("region", { name: "Atendimento" })).toBeNull();
    expect(screen.queryByRole("link", { name: /Manifestantes/ })).toBeNull();
  });

  it("nada a mostrar (só Administração contratada): explica em vez de mostrar a tela vazia", async () => {
    modulosMock.mockResolvedValue({ itens: [m("administracao", 1)] });
    montar(<CadastrosPorArea />);
    expect(await screen.findByText(/Nenhuma destas telas está liberada/)).toBeInTheDocument();
  });
});

describe("Financeiro — Visão geral × Indicadores", () => {
  it("dois links, o atual marcado como página", () => {
    onde.pathname = "/m/pagamentos/dashboard";
    montar(<NavVisaoFinanceiro />);
    const nav = screen.getByRole("navigation", { name: "Visão do financeiro" });
    expect(within(nav).getByRole("link", { name: "Indicadores" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Visão geral" })).not.toHaveAttribute("aria-current");
  });

  it("quem não pode ver Indicadores não vê a barra (uma aba só não é escolha)", () => {
    onde.pode = () => false;
    montar(<NavVisaoFinanceiro />);
    expect(screen.queryByRole("navigation", { name: "Visão do financeiro" })).toBeNull();
  });
});

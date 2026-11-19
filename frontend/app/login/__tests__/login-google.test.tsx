/**
 * SI-32 — "Entrar com o Google" na tela de login do servidor.
 *
 * O botão só existe com o Google configurado no servidor (`branding.login_google`);
 * o clique é navegação de topo para o backend levando o `next` da URL; a volta
 * sem sessão (`?google=<motivo>`) vira mensagem — só para rótulos conhecidos.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: { login: vi.fn() },
  googleLoginUrl: (next: string) => `/api/v2/auth/google-login/inicio?next=${encodeURIComponent(next)}`,
}));

const branding: { nome: string; cor_primaria: null; logo_url: null; login_google?: boolean } = {
  nome: "Aprimora Test",
  cor_primaria: null,
  logo_url: null,
};
vi.mock("@/lib/branding", () => ({
  useBranding: () => branding,
}));

const assign = vi.fn();
const locationOriginal = window.location;

function irPara(search: string) {
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...locationOriginal, search, assign },
  });
}

beforeEach(() => {
  assign.mockReset();
  branding.login_google = true;
  irPara("");
});

afterEach(() => {
  Object.defineProperty(window, "location", { configurable: true, value: locationOriginal });
});

describe("Entrar com o Google (SI-32)", () => {
  it("sem o Google configurado no servidor, o botão não aparece", () => {
    branding.login_google = false;
    render(<LoginPage />);
    expect(screen.queryByRole("button", { name: /google/i })).toBeNull();
  });

  it("configurado, o clique vai ao backend levando o next da URL", async () => {
    irPara("?next=%2Fm%2Fprotocolo%2Fprocessos");
    render(<LoginPage />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Entrar com o Google" }));
    expect(assign).toHaveBeenCalledWith(
      "/api/v2/auth/google-login/inicio?next=%2Fm%2Fprotocolo%2Fprocessos",
    );
  });

  it("next externo na URL não viaja: vai o destino padrão", async () => {
    irPara("?next=%2F%2Fevil.example");
    render(<LoginPage />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Entrar com o Google" }));
    expect(assign).toHaveBeenCalledWith("/api/v2/auth/google-login/inicio?next=%2Fhome");
  });

  it("volta sem conta cadastrada mostra o motivo", async () => {
    irPara("?google=sem_conta");
    render(<LoginPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /não é de um usuário desta prefeitura/,
    );
  });

  it("rótulo desconhecido na URL não vira texto", () => {
    irPara("?google=%3Cscript%3E");
    render(<LoginPage />);
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

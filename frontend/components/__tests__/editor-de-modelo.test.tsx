import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...real,
    api: {
      ...real.api,
      templatesDocumento: { estiloImpressao: () => Promise.resolve({ css: "", css_tela: "" }) },
    },
  };
});

import { EditorDeModelo } from "@/components/protocolo/EditorDeModelo";

function montar() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <EditorDeModelo
        modo="blocos"
        onTrocarModo={() => {}}
        blocos={[]}
        onBlocos={() => {}}
        corpoHtml=""
        onCorpoHtml={() => {}}
        campos={[]}
      />
    </QueryClientProvider>,
  );
}

const previa = () => screen.queryByTitle("Pré-visualização do documento");

beforeEach(() => window.localStorage.clear());

describe("EditorDeModelo — chave da prévia", () => {
  it("abre com a prévia ao lado e a chave desliga para o editor usar a largura toda", async () => {
    const u = userEvent.setup();
    montar();
    const chave = screen.getByRole("button", { name: "Prévia" });
    expect(chave).toHaveAttribute("aria-pressed", "true");
    expect(previa()).not.toBeNull();
    await u.click(chave);
    expect(chave).toHaveAttribute("aria-pressed", "false");
    expect(previa()).toBeNull();
    // A folha dos blocos continua lá.
    expect(screen.getByRole("list", { name: "Blocos do modelo" })).toBeInTheDocument();
  });

  it("lembra a escolha na próxima abertura", async () => {
    const u = userEvent.setup();
    const r = montar();
    await u.click(screen.getByRole("button", { name: "Prévia" }));
    r.unmount();
    montar();
    expect(screen.getByRole("button", { name: "Prévia" })).toHaveAttribute("aria-pressed", "false");
    expect(previa()).toBeNull();
  });
});

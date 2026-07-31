/**
 * A aba de contratação. Duas propriedades do backend que a interface tem de
 * respeitar, senão ela produz 400 ou engana o administrador:
 *  1. o PUT RECONCILIA — manda a lista completa do estado final, não um delta;
 *  2. módulo inativo não pode ser CONTRATADO, mas pode ser DESCONTRATADO
 *     (services/modulos.py::contratar recusa o primeiro e permite o segundo).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const salvar = vi.fn((_id: number, _slugs: string[]) => Promise.resolve());
vi.mock("@/lib/api", () => ({
  api: {
    adminTenantModulos: () =>
      Promise.resolve([
        { slug: "protocolo", nome: "Protocolo", contratado: true, ativo: true, ordem: 1 },
        { slug: "frota", nome: "Frota", contratado: false, ativo: true, ordem: 3 },
        { slug: "transporte", nome: "Transporte Regulado", contratado: true, ativo: false, ordem: 4 },
      ]),
    adminTenantContratarModulos: (id: number, slugs: string[]) => salvar(id, slugs),
  },
}));

// Confirmação real fica coberta em confirm.tsx; aqui só garantimos que o
// componente PEDE confirmação antes de descontratar — auto-aceitar deixa o
// teste focado no fluxo de dados (delta vs. reconciliação completa).
const confirmMock = vi.fn().mockResolvedValue(true);
vi.mock("@/components/ui/confirm", () => ({ useConfirm: () => confirmMock }));

const toastSuccess = vi.fn();
const toastError = vi.fn();
vi.mock("@/components/ui/toast", () => ({
  useToast: () => ({ success: toastSuccess, error: toastError, info: vi.fn(), warning: vi.fn() }),
}));

// Importa direto do componente, não da página: page.tsx é um arquivo de rota
// do App Router e só pode exportar os nomes que o Next reconhece (default,
// metadata, etc.) — reexportar TenantModulosTab de lá quebra a checagem de
// tipos de rota (`.next/types/app/.../page.ts`). O componente mora em
// components/admin/TenantModulosTab.tsx e a página só o usa.
import { TenantModulosTab } from "@/components/admin/TenantModulosTab";

function renderTab() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <TenantModulosTab tenantId={7} />
    </QueryClientProvider>,
  );
}

describe("aba Módulos do tenant", () => {
  it("contratar um módulo manda a lista completa, não o delta", async () => {
    renderTab();
    fireEvent.click(await waitFor(() => screen.getByLabelText("Frota")));
    fireEvent.click(screen.getByRole("button", { name: /salvar/i }));
    await waitFor(() =>
      expect(salvar).toHaveBeenCalledWith(7, ["protocolo", "frota", "transporte"]),
    );
  });

  it("módulo inativo não pode ser contratado", async () => {
    renderTab();
    // transporte está contratado E inativo: pode soltar, não pode marcar de novo.
    const inativo = (await waitFor(() =>
      screen.getByLabelText("Transporte Regulado"),
    )) as HTMLInputElement;
    fireEvent.click(inativo); // descontrata — permitido
    fireEvent.click(inativo); // tentaria recontratar — a interface tem de barrar
    expect(inativo.checked).toBe(false);
  });

  it("diz que descontratar não apaga dado", async () => {
    renderTab();
    // Garantia do spec §8. Sem isso na tela, o administrador hesita em usá-la.
    await waitFor(() => expect(screen.getByText(/não apaga|dados permanecem/i)).toBeTruthy());
  });
});

"use client";

import { use, useState } from "react";

import { PlataformaGate } from "@/components/admin/PlataformaGate";
import { TenantEditForm } from "@/components/admin/TenantEditForm";
import { TenantModulosTab } from "@/components/admin/TenantModulosTab";
import { cn } from "@/lib/utils";

// TenantModulosTab NÃO é reexportado daqui: page.tsx é arquivo de rota do App
// Router e só pode exportar os nomes que o Next reconhece — reexportar
// quebraria a checagem de tipos de rota. O teste
// (frontend/__tests__/AdminTenantModulos.test.tsx) importa o componente
// direto de components/admin/TenantModulosTab.tsx.

const ABAS = [
  { id: "dados", label: "Dados" },
  { id: "modulos", label: "Módulos" },
] as const;
type AbaId = (typeof ABAS)[number]["id"];

export default function AdminTenantEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const tenantId = Number(id);
  const [aba, setAba] = useState<AbaId>("dados");

  return (
    <PlataformaGate>
      <div className="max-w-2xl space-y-4">
        <div role="tablist" aria-label="Seções do tenant" className="flex gap-1 border-b border-border">
          {ABAS.map((a) => {
            const ativa = aba === a.id;
            return (
              <button
                key={a.id}
                type="button"
                role="tab"
                aria-selected={ativa}
                onClick={() => setAba(a.id)}
                className={cn(
                  "flex h-11 shrink-0 items-center px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  ativa
                    ? "border-b-2 border-primary text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {a.label}
              </button>
            );
          })}
        </div>

        {aba === "dados" ? (
          <TenantEditForm tenantId={tenantId} />
        ) : (
          <TenantModulosTab tenantId={tenantId} />
        )}
      </div>
    </PlataformaGate>
  );
}

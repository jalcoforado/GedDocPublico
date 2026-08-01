"use client";

import { useState } from "react";

import { TenantEditForm } from "@/components/admin/TenantEditForm";
import { TenantModulosTab } from "@/components/admin/TenantModulosTab";
import { cn } from "@/lib/utils";

const ABAS = [
  { id: "dados", label: "Dados" },
  { id: "modulos", label: "Módulos" },
] as const;
type AbaId = (typeof ABAS)[number]["id"];

/**
 * Abas "Dados" / "Módulos" da edição de tenant. Extraído de `page.tsx` (que
 * só pode exportar os nomes que o App Router reconhece — ver comentário lá)
 * para poder ser testado sem a ginástica de `use(params)`/Suspense da rota.
 */
export function TenantEditTabs({ tenantId }: { tenantId: number }) {
  const [aba, setAba] = useState<AbaId>("dados");

  return (
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

      {/*
        As duas abas ficam MONTADAS o tempo todo — só a visível troca de
        `hidden`. Alternativa a isso era condicional (`aba === "dados" ? A : B`),
        mas essa desmonta a aba inativa: o admin marca módulos, dá uma
        olhada em "Dados" e volta achando as marcações perdidas, sem
        nenhum aviso. Manter os dois montados preserva o estado local de
        cada aba de graça — nenhuma das duas tem efeito colateral ao
        montar (sem toast, sem redirect), então o custo é só a query de
        cada uma disparar um pouco mais cedo.
      */}
      <div className={cn(aba !== "dados" && "hidden")}>
        <TenantEditForm tenantId={tenantId} />
      </div>
      <div className={cn(aba !== "modulos" && "hidden")}>
        <TenantModulosTab tenantId={tenantId} />
      </div>
    </div>
  );
}

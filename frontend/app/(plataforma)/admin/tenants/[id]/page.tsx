"use client";

import { use } from "react";

import { PlataformaGate } from "@/components/admin/PlataformaGate";
import { TenantEditTabs } from "@/components/admin/TenantEditTabs";

// TenantEditTabs (e os componentes que ela usa) NÃO são reexportados daqui:
// page.tsx é arquivo de rota do App Router e só pode exportar os nomes que o
// Next reconhece — reexportar quebraria a checagem de tipos de rota. Os
// testes (frontend/__tests__/AdminTenant*.test.tsx) importam os componentes
// direto de components/admin/.

export default function AdminTenantEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const tenantId = Number(id);

  return (
    <PlataformaGate>
      <TenantEditTabs tenantId={tenantId} />
    </PlataformaGate>
  );
}

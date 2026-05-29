"use client";

import { use } from "react";

import { PlataformaGate } from "@/components/admin/PlataformaGate";
import { TenantEditForm } from "@/components/admin/TenantEditForm";

export default function AdminTenantEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <PlataformaGate>
      <TenantEditForm tenantId={Number(id)} />
    </PlataformaGate>
  );
}

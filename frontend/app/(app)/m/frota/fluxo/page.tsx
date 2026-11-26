"use client";

import { Workflow } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { MapaDaFrota } from "@/components/frota/MapaDaFrota";

export default function FluxoDaFrotaPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Frota", href: "/m/frota" }]}
        title="Fluxo do processo"
        description="O caminho de uma solicitação de veículo, do pedido ao retorno: o que acontece em cada passo e onde as solicitações estão agora."
        icon={Workflow}
      />
      <MapaDaFrota />
    </div>
  );
}

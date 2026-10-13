"use client";

import { Workflow } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { MapaDoTransporte } from "@/components/transporte/MapaDoTransporte";

export default function FluxoDoTransportePage() {
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Transporte Regulado", href: "/m/transporte" }]}
        title="Fluxo do processo"
        description="Os três caminhos do transporte regulado — alvará, recadastramento e ocorrência — e o que acontece em cada passo."
        icon={Workflow}
      />
      <MapaDoTransporte />
    </div>
  );
}

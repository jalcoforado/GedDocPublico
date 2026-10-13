"use client";

import { Workflow } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { MapaDoProcesso } from "@/components/pagamentos/MapaDoProcesso";

export default function FluxoDoProcessoPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Pagamentos", href: "/m/pagamentos" }]}
        title="Fluxo do processo"
        description="O caminho de um pagamento, da solicitação à conciliação: quem atua em cada passo e onde o trabalho está agora."
        icon={Workflow}
      />
      <MapaDoProcesso />
    </div>
  );
}

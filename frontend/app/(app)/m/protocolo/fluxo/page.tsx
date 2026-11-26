"use client";

import { Workflow } from "lucide-react";

import { PageHeader } from "@/components/ui/page-header";
import { MapaDoProtocolo } from "@/components/protocolo/MapaDoProtocolo";

export default function FluxoDoProtocoloPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumbs={[{ label: "Processos", href: "/m/protocolo/processos" }]}
        title="Fluxo do processo"
        description="O caminho de um processo, da abertura ao arquivamento: quem faz cada passo e onde o trabalho da sua unidade está agora."
        icon={Workflow}
      />
      <MapaDoProtocolo />
    </div>
  );
}

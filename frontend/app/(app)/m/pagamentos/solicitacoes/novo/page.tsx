"use client";

import { FilePlus } from "lucide-react";

import { FormularioDebito } from "@/components/pagamentos/FormularioDebito";
import { PageHeader } from "@/components/ui/page-header";

export default function NovasolicitacaoPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        breadcrumbs={[
          { label: "Pagamentos", href: "/m/pagamentos" },
          { label: "Solicitações", href: "/m/pagamentos/solicitacoes" },
        ]}
        title="Nova Solicitação de Pagamento"
        description="Preencha os dados da solicitação. Você poderá editar enquanto estiver em rascunho."
        icon={FilePlus}
      />
      <FormularioDebito />
    </div>
  );
}

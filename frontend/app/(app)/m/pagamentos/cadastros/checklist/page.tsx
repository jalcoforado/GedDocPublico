"use client";

import { ListChecks } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { AtivoBadge } from "@/components/pagamentos/Rotulos";
import { api, type ChecklistItemTemplate } from "@/lib/api";

export default function ChecklistItensPage() {
  return (
    <CrudPage<ChecklistItemTemplate>
      title="Checklist documental"
      icon={ListChecks}
      description="Documentos que a validação financeira confere em toda solicitação."
      novoLabel="Novo item do checklist"
      queryKey={["pag-checklist-itens"]}
      fetchList={() => api.pagamentos.cadastros.checklistItens.list()}
      createFn={api.pagamentos.cadastros.checklistItens.create}
      updateFn={api.pagamentos.cadastros.checklistItens.update}
      deleteFn={api.pagamentos.cadastros.checklistItens.remove}
      emptyForm={{ descricao: "", obrigatorio: true, ordem: 0, ativo: true }}
      columns={[
        { header: "Descrição", render: (r) => r.descricao },
        { header: "Obrigatório", render: (r) => (r.obrigatorio ? "Sim" : "Não") },
        { header: "Ordem", render: (r) => String(r.ordem), className: "tabular-nums" },
        { header: "Situação", render: (r) => <AtivoBadge ativo={r.ativo} /> },
      ]}
      fields={[
        { name: "descricao", label: "Descrição", type: "textarea", required: true, colSpan: 2 },
        { name: "obrigatorio", label: "Obrigatório para validar", type: "checkbox" },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

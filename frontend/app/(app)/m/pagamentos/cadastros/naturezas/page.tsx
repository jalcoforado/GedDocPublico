"use client";

import { Layers } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { AtivoBadge, CriticidadeBadge } from "@/components/pagamentos/Rotulos";
import { api, type NaturezaDespesa } from "@/lib/api";

export default function NaturezasPage() {
  return (
    <CrudPage<NaturezaDespesa>
      title="Naturezas de despesa"
      icon={Layers}
      description="Classificação das despesas e a criticidade que cada uma traz por padrão."
      novoLabel="Nova natureza"
      queryKey={["pag-naturezas"]}
      fetchList={() => api.pagamentos.cadastros.naturezas.list()}
      createFn={api.pagamentos.cadastros.naturezas.create}
      updateFn={api.pagamentos.cadastros.naturezas.update}
      deleteFn={api.pagamentos.cadastros.naturezas.remove}
      emptyForm={{ codigo: "", descricao: "", criticidade_padrao: "MEDIA", ativa: true }}
      columns={[
        { header: "Código", render: (r) => r.codigo },
        { header: "Descrição", render: (r) => r.descricao },
        { header: "Criticidade", render: (r) => <CriticidadeBadge valor={r.criticidade_padrao} /> },
        { header: "Situação", render: (r) => <AtivoBadge ativo={r.ativa} feminino /> },
      ]}
      fields={[
        { name: "codigo", label: "Código", type: "text", required: true },
        { name: "descricao", label: "Descrição", type: "textarea", required: true, colSpan: 2 },
        {
          name: "criticidade_padrao",
          label: "Criticidade",
          type: "select",
          required: true,
          options: [
            { value: "URGENTE", label: "Urgente" },
            { value: "ALTA", label: "Alta" },
            { value: "MEDIA", label: "Média" },
            { value: "BAIXA", label: "Baixa" },
          ],
        },
        { name: "ativa", label: "Ativa", type: "checkbox" },
      ]}
    />
  );
}

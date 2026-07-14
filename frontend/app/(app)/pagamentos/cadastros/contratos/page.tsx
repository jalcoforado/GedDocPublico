"use client";

import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Contrato } from "@/lib/api";

export default function ContratosPage() {
  const credoresQ = useQuery({
    queryKey: ["pag-credores-select"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
  });

  return (
    <CrudPage<Contrato>
      title="Contratos"
      queryKey={["pag-contratos"]}
      fetchList={() => api.pagamentos.cadastros.contratos.list()}
      createFn={api.pagamentos.cadastros.contratos.create}
      updateFn={api.pagamentos.cadastros.contratos.update}
      deleteFn={api.pagamentos.cadastros.contratos.remove}
      dialogSize="lg"
      emptyForm={{
        numero: "",
        id_credor: credoresQ.data?.[0]?.id ?? null,
        id_unidade: null,
        objeto: "",
        vigencia_inicio: "",
        vigencia_fim: "",
        valor_total: null,
      }}
      columns={[
        { header: "Número", render: (r) => r.numero },
        {
          header: "Credor",
          render: (r) => credoresQ.data?.find((c) => c.id === r.id_credor)?.nome ?? "—",
        },
        { header: "Objeto", render: (r) => r.objeto },
        {
          header: "Vigência",
          render: (r) => `${r.vigencia_inicio} a ${r.vigencia_fim}`,
        },
        { header: "Valor total", render: (r) => r.valor_total },
      ]}
      fields={[
        { name: "numero", label: "Número", type: "text", required: true },
        {
          name: "id_credor",
          label: "Credor",
          type: "select",
          required: true,
          options: credoresQ.data?.map((c) => ({ value: c.id, label: c.nome })),
        },
        { name: "id_unidade", label: "ID da unidade", type: "number", required: true },
        { name: "objeto", label: "Objeto", type: "textarea", required: true, colSpan: 2 },
        {
          name: "vigencia_inicio",
          label: "Vigência início (aaaa-mm-dd)",
          type: "text",
          required: true,
          placeholder: "aaaa-mm-dd",
        },
        {
          name: "vigencia_fim",
          label: "Vigência fim (aaaa-mm-dd)",
          type: "text",
          required: true,
          placeholder: "aaaa-mm-dd",
        },
        { name: "valor_total", label: "Valor total", type: "number", required: true },
      ]}
    />
  );
}

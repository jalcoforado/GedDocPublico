"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Assunto } from "@/lib/api";

export default function AssuntosPage() {
  const [q, setQ] = useState("");
  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });

  return (
    <CrudPage<Assunto>
      title="Assuntos"
      queryKey={["assuntos", q]}
      fetchList={() => api.assuntos.list({ q: q || undefined, page_size: 50 })}
      createFn={api.assuntos.create}
      updateFn={api.assuntos.update}
      deleteFn={api.assuntos.remove}
      searchable
      onSearchChange={setQ}
      dialogSize="lg"
      emptyForm={{
        assunto: "",
        id_tipo_processo: tiposQ.data?.[0]?.id ?? null,
        exige_processo_pai: false,
        ativo: true,
      }}
      columns={[
        { header: "Assunto", render: (r) => r.assunto },
        {
          header: "Tipo de Processo",
          render: (r) =>
            tiposQ.data?.find((t) => t.id === r.id_tipo_processo)?.tipo_processo ?? "—",
        },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "assunto", label: "Assunto", type: "textarea", required: true, colSpan: 2 },
        {
          name: "id_tipo_processo",
          label: "Tipo de Processo",
          type: "select",
          required: true,
          colSpan: 2,
          options: tiposQ.data?.map((t) => ({ value: t.id, label: t.tipo_processo })),
        },
        { name: "exige_processo_pai", label: "Exige processo pai", type: "checkbox" },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

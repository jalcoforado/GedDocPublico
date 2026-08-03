"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Cidade } from "@/lib/api";

export default function CidadesPage() {
  const [q, setQ] = useState("");
  const estadosQ = useQuery({ queryKey: ["estados"], queryFn: api.estados });

  return (
    <CrudPage<Cidade>
      title="Cidades"
      queryKey={["cidades", q]}
      fetchList={() => api.cidades.list({ q: q || undefined, page_size: 50 })}
      createFn={api.cidades.create}
      updateFn={api.cidades.update}
      deleteFn={api.cidades.remove}
      searchable
      onSearchChange={setQ}
      emptyForm={{ cidade: "", id_estado: null }}
      columns={[
        { header: "Cidade", render: (r) => r.cidade },
        {
          header: "Estado",
          render: (r) =>
            estadosQ.data?.find((e) => e.id === r.id_estado)?.uf ?? "—",
          className: "w-24",
        },
      ]}
      fields={[
        { name: "cidade", label: "Nome", type: "text", required: true, colSpan: 2 },
        {
          name: "id_estado",
          label: "Estado",
          type: "select",
          options: estadosQ.data?.map((e) => ({
            value: e.id,
            label: `${e.uf} - ${e.estado}`,
          })),
          colSpan: 2,
        },
      ]}
    />
  );
}

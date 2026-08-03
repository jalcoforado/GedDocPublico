"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Bairro } from "@/lib/api";

export default function BairrosPage() {
  const [q, setQ] = useState("");
  const cidadesQ = useQuery({
    queryKey: ["cidades-all"],
    queryFn: () => api.cidades.list({ page_size: 200 }),
  });

  return (
    <CrudPage<Bairro>
      title="Bairros"
      queryKey={["bairros", q]}
      fetchList={() => api.bairros.list({ q: q || undefined, page_size: 50 })}
      createFn={api.bairros.create}
      updateFn={api.bairros.update}
      deleteFn={api.bairros.remove}
      searchable
      onSearchChange={setQ}
      emptyForm={{ bairro: "", id_cidade: null, ativo: true }}
      columns={[
        { header: "Bairro", render: (r) => r.bairro },
        {
          header: "Cidade",
          render: (r) =>
            cidadesQ.data?.items.find((c) => c.id === r.id_cidade)?.cidade ?? "—",
        },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "bairro", label: "Nome", type: "text", required: true, colSpan: 2 },
        {
          name: "id_cidade",
          label: "Cidade",
          type: "select",
          options: cidadesQ.data?.items.map((c) => ({ value: c.id, label: c.cidade })),
        },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

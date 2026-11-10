"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Map as MapIcon } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { BadgeAtivo } from "@/components/protocolo/BadgeAtivo";
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
      icon={MapIcon}
      description="Bairros usados no endereço dos manifestantes."
      novoLabel="Novo bairro"
      queryKey={["bairros", q]}
      fetchList={({ page }) => api.bairros.list({ q: q || undefined, page, page_size: 50 })}
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
        { header: "Situação", render: (r) => <BadgeAtivo ativo={r.ativo} />, className: "w-24" },
      ]}
      fields={[
        { name: "bairro", label: "Nome", type: "text", required: true, colSpan: 2, placeholder: "Ex.: Centro" },
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

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Endereco } from "@/lib/api";

export default function EnderecosPage() {
  const [q, setQ] = useState("");
  const cidadesQ = useQuery({
    queryKey: ["cidades-all"],
    queryFn: () => api.cidades.list({ page_size: 200 }),
  });
  const bairrosQ = useQuery({
    queryKey: ["bairros-all"],
    queryFn: () => api.bairros.list({ page_size: 500 }),
  });
  const estadosQ = useQuery({ queryKey: ["estados"], queryFn: api.estados });

  return (
    <CrudPage<Endereco>
      title="Endereços"
      queryKey={["enderecos", q]}
      fetchList={() => api.enderecos.list({ q: q || undefined, page_size: 50 })}
      createFn={api.enderecos.create}
      updateFn={api.enderecos.update}
      deleteFn={api.enderecos.remove}
      searchable
      onSearchChange={setQ}
      dialogSize="lg"
      emptyForm={{
        id_cidade: null,
        id_bairro: null,
        id_estado: null,
        rua: "",
        numero: "",
        complemento: "",
      }}
      columns={[
        { header: "Rua", render: (r) => r.rua ?? "—" },
        { header: "Nº", render: (r) => r.numero ?? "—", className: "w-16" },
        {
          header: "Bairro",
          render: (r) =>
            bairrosQ.data?.items.find((b) => b.id === r.id_bairro)?.bairro ?? "—",
        },
        {
          header: "Cidade",
          render: (r) =>
            cidadesQ.data?.items.find((c) => c.id === r.id_cidade)?.cidade ?? "—",
        },
      ]}
      fields={[
        { name: "rua", label: "Rua", type: "text", colSpan: 2 },
        { name: "numero", label: "Número", type: "text" },
        { name: "complemento", label: "Complemento", type: "text" },
        {
          name: "id_estado",
          label: "Estado",
          type: "select",
          options: estadosQ.data?.map((e) => ({ value: e.id, label: e.uf })),
        },
        {
          name: "id_cidade",
          label: "Cidade",
          type: "select",
          options: cidadesQ.data?.items.map((c) => ({ value: c.id, label: c.cidade })),
        },
        {
          name: "id_bairro",
          label: "Bairro",
          type: "select",
          options: bairrosQ.data?.items.map((b) => ({ value: b.id, label: b.bairro })),
          colSpan: 2,
        },
      ]}
    />
  );
}

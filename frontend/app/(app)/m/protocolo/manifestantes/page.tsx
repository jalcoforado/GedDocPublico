"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Manifestante } from "@/lib/api";

export default function ManifestantesPage() {
  const [q, setQ] = useState("");
  const tiposQ = useQuery({
    queryKey: ["tipos-manifestante"],
    queryFn: () => api.tiposManifestante.list(),
  });

  return (
    <CrudPage<Manifestante>
      title="Manifestantes"
      queryKey={["manifestantes", q]}
      fetchList={() => api.manifestantes.list({ q: q || undefined, page_size: 50 })}
      createFn={api.manifestantes.create}
      updateFn={api.manifestantes.update}
      deleteFn={api.manifestantes.remove}
      searchable
      onSearchChange={setQ}
      dialogSize="lg"
      emptyForm={{
        id_tipo_manifestante: tiposQ.data?.[0]?.id ?? null,
        cpf_cnpj: "",
        nome: "",
        organizacao: "",
        telefone_celular: "",
        email: "",
        ativo: true,
      }}
      columns={[
        { header: "Nome", render: (r) => r.nome ?? "—" },
        { header: "CPF/CNPJ", render: (r) => r.cpf_cnpj ?? "—" },
        {
          header: "Tipo",
          render: (r) =>
            tiposQ.data?.find((t) => t.id === r.id_tipo_manifestante)
              ?.tipo_manifestante ?? "—",
        },
        { header: "Email", render: (r) => r.email ?? "—" },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        {
          name: "id_tipo_manifestante",
          label: "Tipo",
          type: "select",
          required: true,
          colSpan: 2,
          options: tiposQ.data?.map((t) => ({ value: t.id, label: t.tipo_manifestante })),
        },
        { name: "nome", label: "Nome", type: "text", colSpan: 2 },
        { name: "cpf_cnpj", label: "CPF/CNPJ", type: "text" },
        { name: "email", label: "E-mail", type: "text" },
        { name: "telefone_celular", label: "Celular", type: "text" },
        { name: "telefone_residencial", label: "Residencial", type: "text" },
        { name: "telefone_comercial", label: "Comercial", type: "text" },
        { name: "organizacao", label: "Organização", type: "text" },
        { name: "responsavel", label: "Responsável", type: "text" },
        { name: "observacao", label: "Observação", type: "textarea", colSpan: 2 },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

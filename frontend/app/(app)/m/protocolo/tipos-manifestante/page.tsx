"use client";

import { CrudPage } from "@/components/CrudPage";
import { api, type TipoManifestante } from "@/lib/api";

const NATUREZA = { F: "Pessoa física (CPF)", J: "Pessoa jurídica (CNPJ)" } as const;

export default function TiposManifestantePage() {
  return (
    <CrudPage<TipoManifestante>
      title="Tipos de Manifestante"
      queryKey={["tipos-manifestante"]}
      fetchList={() => api.tiposManifestante.list()}
      createFn={api.tiposManifestante.create}
      updateFn={api.tiposManifestante.update}
      deleteFn={api.tiposManifestante.remove}
      emptyForm={{ tipo_manifestante: "", id_categoria: 1, natureza: "F", ativo: true }}
      columns={[
        { header: "Tipo", render: (r) => r.tipo_manifestante },
        { header: "Natureza", render: (r) => NATUREZA[r.natureza] ?? r.natureza },
        { header: "Categoria", render: (r) => r.id_categoria, className: "w-24" },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "tipo_manifestante", label: "Nome", type: "text", required: true, colSpan: 2 },
        {
          // Decide a máscara do documento no cadastro de manifestante.
          name: "natureza",
          label: "Natureza",
          type: "select",
          required: true,
          colSpan: 2,
          options: Object.entries(NATUREZA).map(([value, label]) => ({ value, label })),
        },
        { name: "id_categoria", label: "ID Categoria", type: "number", required: true },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

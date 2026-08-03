"use client";

import { CrudPage } from "@/components/CrudPage";
import { api, type TipoManifestante } from "@/lib/api";

export default function TiposManifestantePage() {
  return (
    <CrudPage<TipoManifestante>
      title="Tipos de Manifestante"
      queryKey={["tipos-manifestante"]}
      fetchList={() => api.tiposManifestante.list()}
      createFn={api.tiposManifestante.create}
      updateFn={api.tiposManifestante.update}
      deleteFn={api.tiposManifestante.remove}
      emptyForm={{ tipo_manifestante: "", id_categoria: 1, ativo: true }}
      columns={[
        { header: "Tipo", render: (r) => r.tipo_manifestante },
        { header: "Categoria", render: (r) => r.id_categoria, className: "w-24" },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "tipo_manifestante", label: "Nome", type: "text", required: true, colSpan: 2 },
        { name: "id_categoria", label: "ID Categoria", type: "number", required: true },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

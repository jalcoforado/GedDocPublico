"use client";

import { CrudPage } from "@/components/CrudPage";
import { api, type TipoAnexo } from "@/lib/api";

export default function TiposAnexoPage() {
  return (
    <CrudPage<TipoAnexo>
      title="Tipos de Anexo"
      queryKey={["tipos-anexo"]}
      fetchList={() => api.tiposAnexo.list()}
      createFn={api.tiposAnexo.create}
      updateFn={api.tiposAnexo.update}
      deleteFn={api.tiposAnexo.remove}
      emptyForm={{ tipo_anexo: "" }}
      columns={[{ header: "Nome", render: (r) => r.tipo_anexo }]}
      fields={[
        { name: "tipo_anexo", label: "Nome", type: "text", required: true, colSpan: 2 },
      ]}
    />
  );
}

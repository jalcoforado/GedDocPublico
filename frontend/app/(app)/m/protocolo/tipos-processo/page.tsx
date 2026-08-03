"use client";

import { CrudPage } from "@/components/CrudPage";
import { api, type TipoProcesso } from "@/lib/api";

export default function TiposProcessoPage() {
  return (
    <CrudPage<TipoProcesso>
      title="Tipos de Processo"
      queryKey={["tipos-processo"]}
      fetchList={() => api.tiposProcesso.list()}
      createFn={api.tiposProcesso.create}
      updateFn={api.tiposProcesso.update}
      deleteFn={api.tiposProcesso.remove}
      emptyForm={{ tipo_processo: "", exige_processo_pai: false, ativo: true }}
      columns={[
        { header: "Nome", render: (r) => r.tipo_processo },
        {
          header: "Exige Pai",
          render: (r) => (r.exige_processo_pai ? "Sim" : "Não"),
          className: "w-24",
        },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "tipo_processo", label: "Nome", type: "text", required: true, colSpan: 2 },
        { name: "exige_processo_pai", label: "Exige processo pai", type: "checkbox" },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

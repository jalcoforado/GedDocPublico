"use client";

import { Layers } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { BadgeAtivo } from "@/components/protocolo/BadgeAtivo";
import { api, type TipoProcesso } from "@/lib/api";

export default function TiposProcessoPage() {
  return (
    <CrudPage<TipoProcesso>
      title="Tipos de Processo"
      icon={Layers}
      description="Tipos de processo e se exigem um processo pai."
      novoLabel="Novo tipo de processo"
      queryKey={["tipos-processo"]}
      fetchList={() => api.tiposProcesso.list()}
      createFn={api.tiposProcesso.create}
      updateFn={api.tiposProcesso.update}
      deleteFn={api.tiposProcesso.remove}
      emptyForm={{ tipo_processo: "", exige_processo_pai: false, ativo: true }}
      columns={[
        { header: "Nome", render: (r) => r.tipo_processo },
        {
          header: "Exige pai",
          render: (r) => (r.exige_processo_pai ? "Sim" : "Não"),
          className: "w-24",
        },
        { header: "Situação", render: (r) => <BadgeAtivo ativo={r.ativo} />, className: "w-24" },
      ]}
      fields={[
        { name: "tipo_processo", label: "Nome", type: "text", required: true, colSpan: 2, placeholder: "Ex.: Requerimento" },
        {
          name: "exige_processo_pai",
          label: "Exige processo pai",
          type: "checkbox",
          dica: "Só pode ser aberto vinculado a outro processo.",
        },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CrudPage } from "@/components/CrudPage";
import { api, type Assunto } from "@/lib/api";
import { useAssuntosAll } from "@/lib/assuntos";

export default function AssuntosPage() {
  const [q, setQ] = useState("");
  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });
  // E2 (benchmark SUiTE) — mesmo cache que Processos/Balcão/Relatórios usam
  // (lib/assuntos.ts), reaproveitado aqui pra montar o seletor de pai. Um
  // assunto poder ser pai de si mesmo já é barrado pelo backend (400); não
  // duplicamos a checagem de ciclo aqui.
  const assuntosQ = useAssuntosAll();
  const assuntoPorId = new Map((assuntosQ.data ?? []).map((a) => [a.id, a.assunto]));

  return (
    <CrudPage<Assunto>
      title="Assuntos"
      queryKey={["assuntos", q]}
      fetchList={({ page }) => api.assuntos.list({ q: q || undefined, page, page_size: 50 })}
      createFn={api.assuntos.create}
      updateFn={api.assuntos.update}
      deleteFn={api.assuntos.remove}
      searchable
      onSearchChange={setQ}
      dialogSize="lg"
      emptyForm={{
        assunto: "",
        id_tipo_processo: tiposQ.data?.[0]?.id ?? null,
        exige_processo_pai: false,
        ativo: true,
        id_assunto_pai: null,
        codigo: "",
      }}
      columns={[
        { header: "Assunto", render: (r) => r.assunto },
        {
          header: "Assunto pai",
          render: (r) =>
            r.id_assunto_pai !== null ? assuntoPorId.get(r.id_assunto_pai) ?? "—" : "—",
        },
        { header: "Nível", render: (r) => String(r.nivel), className: "w-16" },
        {
          header: "Tipo de Processo",
          render: (r) =>
            tiposQ.data?.find((t) => t.id === r.id_tipo_processo)?.tipo_processo ?? "—",
        },
        { header: "Ativo", render: (r) => (r.ativo ? "Sim" : "Não"), className: "w-20" },
      ]}
      fields={[
        { name: "assunto", label: "Assunto", type: "textarea", required: true, colSpan: 2 },
        {
          name: "id_assunto_pai",
          label: "Assunto pai (opcional — vazio = raiz)",
          type: "select",
          colSpan: 2,
          options: (assuntosQ.data ?? []).map((a) => ({
            value: a.id,
            label: `${"—".repeat(a.nivel - 1)} ${a.assunto}`.trim(),
          })),
        },
        { name: "codigo", label: "Código (opcional)", type: "text" },
        {
          name: "id_tipo_processo",
          label: "Tipo de Processo",
          type: "select",
          required: true,
          options: tiposQ.data?.map((t) => ({ value: t.id, label: t.tipo_processo })),
        },
        { name: "exige_processo_pai", label: "Exige processo pai", type: "checkbox" },
        { name: "ativo", label: "Ativo", type: "checkbox" },
      ]}
    />
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { Shield } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { fmtMoeda } from "@/components/pagamentos/format";
import { api, type Alcada } from "@/lib/api";

export default function AlcadasPage() {
  const naturezasQ = useQuery({
    queryKey: ["pag-naturezas-select"],
    queryFn: () => api.pagamentos.cadastros.naturezas.list(),
  });

  return (
    <CrudPage<Alcada>
      title="Alçadas de aprovação"
      icon={Shield}
      description="Até quanto cada usuário pode aprovar, por natureza de despesa."
      novoLabel="Nova alçada"
      queryKey={["pag-alcadas"]}
      fetchList={() => api.pagamentos.cadastros.alcadas.list()}
      createFn={api.pagamentos.cadastros.alcadas.create}
      updateFn={api.pagamentos.cadastros.alcadas.update}
      deleteFn={api.pagamentos.cadastros.alcadas.remove}
      emptyForm={{ id_usuario: null, id_natureza: null, valor_maximo: null }}
      columns={[
        { header: "Usuário (ID)", render: (r) => r.id_usuario },
        {
          header: "Natureza",
          render: (r) =>
            r.id_natureza
              ? naturezasQ.data?.find((n) => n.id === r.id_natureza)?.descricao ?? r.id_natureza
              : "Todas",
        },
        {
          header: "Valor máximo",
          render: (r) => fmtMoeda(r.valor_maximo),
          className: "text-right tabular-nums",
        },
      ]}
      fields={[
        { name: "id_usuario", label: "ID do usuário", type: "number", required: true },
        {
          name: "id_natureza",
          label: "Natureza (opcional)",
          type: "select",
          options: naturezasQ.data?.map((n) => ({ value: n.id, label: n.descricao })),
        },
        { name: "valor_maximo", label: "Valor máximo (R$)", type: "number", required: true },
      ]}
    />
  );
}

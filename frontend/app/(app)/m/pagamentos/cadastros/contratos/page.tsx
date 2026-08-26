"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { CATEGORIA_CONTRATO_LABEL, api, type Contrato } from "@/lib/api";

const OPCOES_CATEGORIA = Object.entries(CATEGORIA_CONTRATO_LABEL).map(([value, label]) => ({
  value,
  label,
}));

export default function ContratosPage() {
  const fornecedoresQ = useQuery({
    queryKey: ["pag-fornecedores-select"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
  });
  const contratosQ = useQuery({
    queryKey: ["pag-contratos-sem-categoria"],
    queryFn: () => api.pagamentos.cadastros.contratos.list(),
  });
  // Defensivo: `ContratoCreate` já exige categoria desde a 0107/Task 2, então
  // isto só deveria aparecer para contratos legados sem backfill.
  const semCategoria = (contratosQ.data ?? []).filter((c) => !c.categoria);

  return (
    <CrudPage<Contrato>
      title="Contratos"
      queryKey={["pag-contratos"]}
      fetchList={() => api.pagamentos.cadastros.contratos.list()}
      createFn={api.pagamentos.cadastros.contratos.create}
      updateFn={api.pagamentos.cadastros.contratos.update}
      deleteFn={api.pagamentos.cadastros.contratos.remove}
      dialogSize="lg"
      toolbar={
        semCategoria.length > 0 ? (
          <div className="mb-3 flex items-start gap-2 rounded-lg border border-warning bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            <span>
              {semCategoria.length} contrato(s) sem categoria da fila cronológica — edite-os para
              classificar (Bens, Locações, Serviços ou Obras).
            </span>
          </div>
        ) : undefined
      }
      emptyForm={{
        numero: "",
        id_fornecedor: fornecedoresQ.data?.[0]?.id ?? null,
        id_unidade: null,
        objeto: "",
        vigencia_inicio: "",
        vigencia_fim: "",
        valor_total: null,
        categoria: "",
      }}
      columns={[
        { header: "Número", render: (r) => r.numero },
        {
          header: "Fornecedor",
          render: (r) => fornecedoresQ.data?.find((c) => c.id === r.id_fornecedor)?.nome ?? "—",
        },
        { header: "Objeto", render: (r) => r.objeto },
        {
          header: "Vigência",
          render: (r) => `${r.vigencia_inicio} a ${r.vigencia_fim}`,
        },
        { header: "Valor total", render: (r) => r.valor_total },
        {
          header: "Categoria",
          render: (r) => (r.categoria ? CATEGORIA_CONTRATO_LABEL[r.categoria] : "—"),
        },
      ]}
      fields={[
        { name: "numero", label: "Número", type: "text", required: true },
        {
          name: "id_fornecedor",
          label: "Fornecedor",
          type: "select",
          required: true,
          options: fornecedoresQ.data?.map((c) => ({ value: c.id, label: c.nome })),
        },
        { name: "id_unidade", label: "ID da unidade", type: "number", required: true },
        { name: "objeto", label: "Objeto", type: "textarea", required: true, colSpan: 2 },
        {
          name: "vigencia_inicio",
          label: "Vigência início (aaaa-mm-dd)",
          type: "text",
          required: true,
          placeholder: "aaaa-mm-dd",
        },
        {
          name: "vigencia_fim",
          label: "Vigência fim (aaaa-mm-dd)",
          type: "text",
          required: true,
          placeholder: "aaaa-mm-dd",
        },
        { name: "valor_total", label: "Valor total", type: "number", required: true },
        {
          name: "categoria",
          label: "Categoria (fila cronológica)",
          type: "select",
          required: true,
          options: OPCOES_CATEGORIA,
        },
      ]}
    />
  );
}

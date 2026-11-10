"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FileText } from "lucide-react";

import { CrudPage } from "@/components/CrudPage";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
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
  // Mesma chave e tamanho da solicitação de pagamento: a lista vem do cache.
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
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
      icon={FileText}
      description="Contratos com fornecedores: vigência, valor e a categoria da fila cronológica."
      novoLabel="Novo contrato"
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
        // Vazio, e não o primeiro da lista: pré-escolher um fornecedor
        // qualquer fazia o contrato nascer com quem ninguém escolheu.
        id_fornecedor: null,
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
          render: (r) => `${fmtData(r.vigencia_inicio)} a ${fmtData(r.vigencia_fim)}`,
          className: "whitespace-nowrap tabular-nums",
        },
        {
          header: "Valor total",
          render: (r) => fmtMoeda(r.valor_total),
          className: "whitespace-nowrap text-right tabular-nums",
        },
        {
          header: "Categoria",
          render: (r) => (r.categoria ? CATEGORIA_CONTRATO_LABEL[r.categoria] : "—"),
        },
      ]}
      // Ordem: com quem (fornecedor) → qual contrato → para quem (unidade) →
      // por quanto tempo → por quanto → em que fila.
      fields={[
        {
          name: "id_fornecedor",
          label: "Fornecedor",
          type: "select",
          required: true,
          colSpan: 2,
          options: fornecedoresQ.data?.map((c) => ({ value: c.id, label: c.nome })),
        },
        {
          name: "numero",
          label: "Número",
          type: "text",
          required: true,
          placeholder: "Ex.: 012/2026",
        },
        {
          name: "id_unidade",
          label: "Unidade",
          type: "select",
          required: true,
          options: unidadesQ.data?.items.map((u) => ({
            value: u.id,
            label: u.sigla ? `${u.unidade_trabalho} (${u.sigla})` : u.unidade_trabalho,
          })),
          dica: "A unidade gestora do contrato.",
        },
        {
          name: "objeto",
          label: "Objeto",
          type: "textarea",
          required: true,
          colSpan: 2,
          placeholder: "Ex.: Fornecimento de gêneros alimentícios para a merenda escolar",
        },
        { name: "vigencia_inicio", label: "Início da vigência", type: "date", required: true },
        { name: "vigencia_fim", label: "Fim da vigência", type: "date", required: true },
        {
          name: "valor_total",
          label: "Valor total",
          type: "number",
          required: true,
          prefixo: "R$",
          placeholder: "0,00",
        },
        {
          name: "categoria",
          label: "Categoria",
          type: "select",
          required: true,
          options: OPCOES_CATEGORIA,
          dica: "A fila cronológica em que entram os pagamentos deste contrato.",
        },
      ]}
    />
  );
}

"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { useToast } from "@/components/ui/toast";
import { WorkflowEditPage } from "@/components/workflow/WorkflowEditPage";
import { workflowApi, type WorkflowDSL } from "@/lib/api";

const INITIAL_DSL: WorkflowDSL = {
  version: "1.0",
  estado_inicial: "aberto",
  estados: [
    {
      slug: "aberto",
      nome: "Aberto",
      descricao: null,
      final: false,
      sla_dias: null,
      posicao: { x: 80, y: 80 },
    },
    {
      slug: "concluido",
      nome: "Concluído",
      descricao: null,
      final: true,
      sla_dias: null,
      posicao: { x: 380, y: 80 },
    },
  ],
  transicoes: [
    {
      de: "aberto",
      para: "concluido",
      label: "Concluir",
      descricao: null,
      condicao: null,
      grupos_permitidos: [],
      evento: "manual",
    },
  ],
};

export default function NovoWorkflowPage() {
  const router = useRouter();
  const toast = useToast();

  const create = useMutation({
    mutationFn: (data: { slug: string; nome: string; descricao: string | null; dsl: WorkflowDSL }) =>
      workflowApi.createDefinition(data),
    onSuccess: (wf) => {
      toast.success(`Workflow "${wf.nome}" criado (v${wf.versao}).`);
      router.push(`/workflow/${wf.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <WorkflowEditPage
      mode="novo"
      initialDsl={INITIAL_DSL}
      saving={create.isPending}
      onSave={async (d) => {
        await create.mutateAsync(d);
      }}
    />
  );
}

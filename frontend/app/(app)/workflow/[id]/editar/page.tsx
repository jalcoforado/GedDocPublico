"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";

import { useToast } from "@/components/ui/toast";
import { WorkflowEditPage } from "@/components/workflow/WorkflowEditPage";
import { workflowApi, type WorkflowDSL } from "@/lib/api";

export default function EditarWorkflowPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const router = useRouter();
  const toast = useToast();

  const q = useQuery({
    queryKey: ["workflow-definition", id],
    queryFn: () => workflowApi.getDefinition(id),
    enabled: Number.isFinite(id),
  });

  const update = useMutation({
    mutationFn: (data: { nome: string; descricao: string | null; dsl: WorkflowDSL }) =>
      workflowApi.updateDefinition(id, data),
    onSuccess: (wf) => {
      toast.success(`Nova versão salva (v${wf.versao}).`);
      router.push(`/workflow/${wf.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) {
    return <div className="text-muted-foreground">Carregando…</div>;
  }
  if (q.error || !q.data) {
    return (
      <div className="text-danger-soft-foreground">
        Erro: {(q.error as Error)?.message ?? "workflow não encontrado"}
      </div>
    );
  }

  const wf = q.data;

  return (
    <WorkflowEditPage
      mode="editar"
      workflowId={wf.id}
      initialSlug={wf.slug}
      initialNome={wf.nome}
      initialDescricao={wf.descricao}
      initialDsl={wf.dsl}
      versao={wf.versao}
      saving={update.isPending}
      onSave={async (d) => {
        await update.mutateAsync({ nome: d.nome, descricao: d.descricao, dsl: d.dsl });
      }}
    />
  );
}

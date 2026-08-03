"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Link2Off } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, workflowApi, type WorkflowDefinition } from "@/lib/api";

/** Lista todos os tipos_processo do tenant e mostra qual está vinculado a este
 * workflow. Permite vincular/desvincular com 1 clique. */
export function WorkflowMapeamentoTipos({ wf }: { wf: WorkflowDefinition }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState<number | null>(null);

  const tiposQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });

  const mapeamentosQ = useQuery({
    queryKey: ["workflow-mapeamentos"],
    queryFn: () => workflowApi.listMapeamentos(),
  });

  const setMapeamento = useMutation({
    mutationFn: ({ tipoId, slug }: { tipoId: number; slug: string | null }) =>
      workflowApi.setMapeamento(tipoId, slug),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["workflow-mapeamentos"] });
      toast.success(
        vars.slug ? "Tipo vinculado a este workflow." : "Vínculo removido.",
      );
      setBusy(null);
    },
    onError: (e: Error) => {
      toast.error(e.message);
      setBusy(null);
    },
  });

  if (tiposQ.isLoading || mapeamentosQ.isLoading) {
    return (
      <p className="text-sm text-muted-foreground">Carregando tipos de processo…</p>
    );
  }

  const tipos = tiposQ.data ?? [];
  const mapeamentos = mapeamentosQ.data ?? [];

  // Mapa id_tipo_processo → slug atualmente mapeado
  const slugPorTipo = new Map<number, string>();
  for (const m of mapeamentos) slugPorTipo.set(m.id_tipo_processo, m.slug_workflow);

  // Conta quantos tipos já apontam pra ESTE workflow
  const ligados = tipos.filter((t) => slugPorTipo.get(t.id) === wf.slug);

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Tipos de processo vinculados
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Quando um processo desses tipos é aberto, este workflow é
            auto-instanciado.
          </p>
        </div>
        <Badge intent={ligados.length > 0 ? "success" : "neutral"}>
          {ligados.length} vinculado{ligados.length === 1 ? "" : "s"}
        </Badge>
      </div>

      {tipos.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Nenhum tipo de processo cadastrado.{" "}
          <a href="/m/protocolo/tipos-processo" className="text-primary hover:underline">
            Cadastrar
          </a>
        </p>
      )}

      <ul className="space-y-1">
        {tipos.map((t) => {
          const slugAtual = slugPorTipo.get(t.id);
          const isEsse = slugAtual === wf.slug;
          const isOutro = slugAtual && slugAtual !== wf.slug;
          const disabled = busy !== null;

          return (
            <li
              key={t.id}
              className="flex items-center justify-between gap-2 rounded border border-border px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{t.tipo_processo}</div>
                {isOutro && (
                  <div className="text-xs text-muted-foreground">
                    Vinculado a:{" "}
                    <span className="font-mono">{slugAtual}</span>
                  </div>
                )}
              </div>
              {isEsse ? (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => {
                    setBusy(t.id);
                    setMapeamento.mutate({ tipoId: t.id, slug: null });
                  }}
                >
                  <Link2Off className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                  Desvincular
                </Button>
              ) : (
                <Button
                  size="sm"
                  disabled={disabled}
                  title={
                    isOutro
                      ? `Substitui o vínculo atual (${slugAtual})`
                      : "Vincular este tipo a este workflow"
                  }
                  onClick={() => {
                    setBusy(t.id);
                    setMapeamento.mutate({ tipoId: t.id, slug: wf.slug });
                  }}
                >
                  <Link2 className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
                  {isOutro ? "Substituir" : "Vincular"}
                </Button>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

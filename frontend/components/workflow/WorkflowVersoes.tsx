"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, GitBranch, MoveRight, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { workflowApi, type WorkflowDefinition } from "@/lib/api";

interface Props {
  wf: WorkflowDefinition;
}

/** Painel de versões do mesmo slug. Mostra todas as versões e, para cada uma
 * que tem instances ativas, oferece botão "Migrar todas pra esta versão"
 * (identidade — estados com mesmo slug). */
export function WorkflowVersoes({ wf }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const versoesQ = useQuery({
    queryKey: ["workflow-versoes", wf.id],
    queryFn: () => workflowApi.listVersoes(wf.id),
  });

  const instancesAntigas = useQuery({
    queryKey: ["workflow-instances", "antigas", wf.slug],
    queryFn: async () => {
      const versoes = await workflowApi.listVersoes(wf.id);
      const antigas = versoes.filter(
        (v) => !v.ativo && v.instances_ativas > 0,
      );
      // Junta as instances de todas as versões antigas
      const lists = await Promise.all(
        antigas.map((v) =>
          workflowApi.listInstances({
            id_workflow_definition: v.id,
            apenas_ativas: true,
          }),
        ),
      );
      return lists.flat();
    },
    enabled: !!versoesQ.data,
  });

  const migrar = useMutation({
    mutationFn: (instanceId: number) =>
      workflowApi.migrarInstance(instanceId, wf.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflow-versoes", wf.id] });
      qc.invalidateQueries({ queryKey: ["workflow-instances", "antigas", wf.slug] });
      toast.success("Instance migrada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const migrarTodas = useMutation({
    mutationFn: async (ids: number[]) => {
      const results: { id: number; ok: boolean; erro?: string }[] = [];
      for (const id of ids) {
        try {
          await workflowApi.migrarInstance(id, wf.id);
          results.push({ id, ok: true });
        } catch (e) {
          results.push({ id, ok: false, erro: (e as Error).message });
        }
      }
      return results;
    },
    onSuccess: (results) => {
      qc.invalidateQueries({ queryKey: ["workflow-versoes", wf.id] });
      qc.invalidateQueries({ queryKey: ["workflow-instances", "antigas", wf.slug] });
      const ok = results.filter((r) => r.ok).length;
      const fail = results.length - ok;
      if (fail === 0) {
        toast.success(`${ok} instances migradas.`);
      } else {
        toast.error(`${ok} migradas, ${fail} falharam.`);
      }
    },
  });

  if (versoesQ.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando versões…</p>;
  }

  const versoes = versoesQ.data ?? [];
  if (versoes.length <= 1) {
    return null; // Só uma versão = nada pra mostrar
  }

  const antigas = instancesAntigas.data ?? [];
  const ehAtual = wf.id === versoes.find((v) => v.ativo)?.id;

  async function onMigrarTodas() {
    if (antigas.length === 0) return;
    const ok = await confirm({
      title: "Migrar todas as instances?",
      message: `Vamos migrar ${antigas.length} instance(s) ativa(s) para v${wf.versao} (mapa identidade: estado com mesmo slug vira o mesmo no destino). Instances cujo estado atual não existir na v${wf.versao} falharão e ficarão na versão antiga.`,
      confirmLabel: "Migrar todas",
    });
    if (!ok) return;
    migrarTodas.mutate(antigas.map((i) => i.id));
  }

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Versões deste workflow
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Cada salvamento do editor cria uma nova versão. Instances em versões
            antigas seguem rodando até serem migradas ou finalizadas naturalmente.
          </p>
        </div>
        {ehAtual && antigas.length > 0 && (
          <Button
            size="sm"
            onClick={onMigrarTodas}
            disabled={migrarTodas.isPending}
          >
            <MoveRight className="mr-1 h-4 w-4" aria-hidden="true" />
            {migrarTodas.isPending
              ? "Migrando…"
              : `Migrar ${antigas.length} → v${wf.versao}`}
          </Button>
        )}
      </div>

      <ul className="space-y-1">
        {versoes.map((v) => (
          <li
            key={v.id}
            className={`flex items-center justify-between gap-2 rounded border px-3 py-2 text-sm ${
              v.id === wf.id ? "border-primary bg-primary/5" : "border-border"
            }`}
          >
            <div className="flex items-center gap-2">
              <GitBranch className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
              <span className="font-mono text-xs">v{v.versao}</span>
              {v.ativo ? (
                <Badge intent="success" icon={CheckCircle2}>
                  Ativa
                </Badge>
              ) : (
                <Badge intent="neutral" icon={XCircle}>
                  Inativa
                </Badge>
              )}
              {v.id === wf.id && (
                <span className="text-xs text-primary font-medium">(esta)</span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">
                {v.instances_ativas} instance(s) ativa(s)
              </span>
            </div>
          </li>
        ))}
      </ul>

      {ehAtual && antigas.length > 0 && (
        <details className="text-xs">
          <summary className="cursor-pointer text-primary">
            Ver instances em versões antigas ({antigas.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {antigas.map((inst) => (
              <li
                key={inst.id}
                className="flex items-center justify-between rounded border border-border bg-muted/30 px-2 py-1"
              >
                <span className="font-mono">
                  instance #{inst.id} · processo #{inst.id_processo} · estado{" "}
                  <strong>{inst.estado_atual}</strong>
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={migrar.isPending}
                  onClick={() => migrar.mutate(inst.id)}
                >
                  <MoveRight className="mr-1 h-3 w-3" aria-hidden="true" />
                  Migrar
                </Button>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

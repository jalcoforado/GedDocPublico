"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock, PlayCircle } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePrompt } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { WorkflowDiagram } from "@/components/workflow/WorkflowDiagram";
import { workflowApi } from "@/lib/api";

function fmtDateTime(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

interface Props {
  processoId: number;
}

export function ProcessoWorkflowPanel({ processoId }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const prompt = usePrompt();

  const instQ = useQuery({
    queryKey: ["processo-workflow", processoId],
    queryFn: () => workflowApi.getProcessoWorkflow(processoId),
  });

  const defQ = useQuery({
    queryKey: ["workflow-definition", instQ.data?.id_workflow_definition],
    queryFn: () => workflowApi.getDefinition(instQ.data!.id_workflow_definition),
    enabled: !!instQ.data,
  });

  const alertasQ = useQuery({
    queryKey: ["workflow-alertas", { processoId, apenas_pendentes: false }],
    queryFn: () =>
      workflowApi.listAlertas({ apenas_pendentes: false, id_processo: processoId }),
  });

  const transitar = useMutation({
    mutationFn: ({ instanceId, para }: { instanceId: number; para: string }) =>
      workflowApi.transicionar(instanceId, para),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo-workflow", processoId] });
      qc.invalidateQueries({ queryKey: ["workflow-alertas"] });
      toast.success("Transição executada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const resolverAlerta = useMutation({
    mutationFn: ({ id, resolucao }: { id: number; resolucao: string }) =>
      workflowApi.resolverAlerta(id, resolucao),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["workflow-alertas"] });
      toast.success("Alerta resolvido.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onResolver(alertaId: number) {
    const v = await prompt({
      title: "Resolver alerta",
      message: "Descreva como o alerta foi resolvido (ex: ciente, escalado).",
      label: "Resolução",
      defaultValue: "ciente",
      confirmLabel: "Resolver",
      required: true,
    });
    if (!v) return;
    resolverAlerta.mutate({ id: alertaId, resolucao: v });
  }

  if (instQ.isLoading) {
    return <p className="text-sm text-muted-foreground">Carregando workflow…</p>;
  }
  if (!instQ.data) {
    return <IniciarManualmente processoId={processoId} />;
  }

  const inst = instQ.data;
  const alertasPendentes = (alertasQ.data ?? []).filter((a) => !a.resolvido_em);
  const alertasResolvidos = (alertasQ.data ?? []).filter((a) => !!a.resolvido_em);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm">
            Estado atual:{" "}
            <span className="font-mono font-semibold text-primary">
              {inst.estado_atual}
            </span>
            {!inst.ativa && (
              <Badge intent="success" icon={CheckCircle2} className="ml-2">
                Finalizado
              </Badge>
            )}
          </div>
          {defQ.data && (
            <div className="flex items-center gap-2">
              <Link
                href={`/workflow/${defQ.data.id}`}
                className="text-xs text-muted-foreground hover:underline"
              >
                {defQ.data.nome} (v{defQ.data.versao})
              </Link>
              {defQ.data.dsl.strict && (
                <Badge
                  intent="warning"
                  className="text-[10px]"
                  title="Fluxo obrigatório — encaminhamentos fora do trilho são bloqueados pelo backend."
                >
                  Fluxo obrigatório
                </Badge>
              )}
            </div>
          )}
        </div>
      </div>

      {defQ.data?.dsl.strict && inst.ativa && (
        <div className="rounded-md border border-warning/30 bg-warning-soft/30 px-3 py-2 text-xs text-warning-soft-foreground">
          Este processo segue um <strong>fluxo obrigatório</strong>. Use os
          botões de transição abaixo — encaminhamentos manuais para unidades
          fora do trilho são bloqueados.
        </div>
      )}

      {alertasPendentes.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 p-3">
          <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-amber-900">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            {alertasPendentes.length} alerta{alertasPendentes.length > 1 ? "s" : ""}{" "}
            de SLA pendente{alertasPendentes.length > 1 ? "s" : ""}
          </div>
          <ul className="space-y-2">
            {alertasPendentes.map((a) => (
              <li
                key={a.id}
                className="flex items-center justify-between gap-2 text-sm text-amber-900"
              >
                <span>
                  Estado <span className="font-mono">{a.estado}</span> — parado há{" "}
                  <strong>{a.dias_no_estado}d</strong> (SLA {a.sla_dias}d)
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => onResolver(a.id)}
                  disabled={resolverAlerta.isPending}
                >
                  Resolver
                </Button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {defQ.data && (
        <WorkflowDiagram
          dsl={defQ.data.dsl}
          estadoAtual={inst.estado_atual}
          height={400}
        />
      )}

      {inst.ativa && inst.transicoes_disponiveis.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Transições disponíveis
          </h3>
          <div className="flex flex-col gap-2">
            {inst.transicoes_disponiveis.map((t) => {
              const destinoEstado = defQ.data?.dsl.estados.find(
                (e) => e.slug === t.para,
              );
              const unidDest = destinoEstado?.id_unidade_responsavel ?? null;
              return (
                <div
                  key={`${t.de}->${t.para}`}
                  className="flex flex-wrap items-center gap-2"
                >
                  <Button
                    size="sm"
                    onClick={() =>
                      transitar.mutate({ instanceId: inst.id, para: t.para })
                    }
                    disabled={transitar.isPending}
                    title={`${t.de} → ${t.para}`}
                  >
                    {t.label}
                  </Button>
                  {unidDest != null && (
                    <span className="text-xs text-muted-foreground">
                      → será encaminhado pra unidade #{unidDest}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {inst.ativa && inst.transicoes_disponiveis.length === 0 && (
        <p className="text-xs text-muted-foreground">
          Nenhuma transição disponível neste estado. Pode ser que ele esteja
          esperando um evento (encaminhamento/recebimento) ou que sua unidade
          não seja a responsável por avançar.
        </p>
      )}

      {inst.log.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Histórico
          </h3>
          <ol className="space-y-1">
            {inst.log.map((l) => (
              <li
                key={l.id}
                className="flex items-start gap-2 rounded border border-border bg-card px-3 py-2 text-xs"
              >
                <Clock
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <div className="flex-1">
                  <div>
                    <span className="font-mono">{l.estado_de}</span> →{" "}
                    <span className="font-mono">{l.estado_para}</span> —{" "}
                    {l.transicao_label}
                  </div>
                  <div className="text-muted-foreground">{fmtDateTime(l.executada_em)}</div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}

      {alertasResolvidos.length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            Alertas já resolvidos ({alertasResolvidos.length})
          </summary>
          <ul className="mt-2 space-y-1">
            {alertasResolvidos.map((a) => (
              <li key={a.id} className="rounded border border-border px-2 py-1">
                <span className="font-mono">{a.estado}</span> — {a.dias_no_estado}d ·
                resolvido em {fmtDateTime(a.resolvido_em)} ({a.resolucao})
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function IniciarManualmente({ processoId }: { processoId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [selectedId, setSelectedId] = useState<number | "">("");

  const defsQ = useQuery({
    queryKey: ["workflow-definitions", { apenasAtivos: true }],
    queryFn: () => workflowApi.listDefinitions(true),
  });

  const iniciar = useMutation({
    mutationFn: ({ wfId }: { wfId: number }) =>
      workflowApi.iniciarInstance(wfId, processoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo-workflow", processoId] });
      toast.success("Workflow iniciado para este processo.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const defs = defsQ.data ?? [];

  return (
    <div className="space-y-3 rounded-md border border-dashed border-border bg-muted/30 p-4">
      <div className="flex items-center gap-2 text-sm">
        <PlayCircle className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-muted-foreground">
          Nenhum workflow ativo neste processo.
        </span>
      </div>

      {defs.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          Nenhum workflow ativo no tenant.{" "}
          <Link href="/workflow/novo" className="text-primary hover:underline">
            Criar um
          </Link>
          .
        </p>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Você pode iniciar manualmente um workflow ativo para este processo. Pra
            isso virar automático para processos futuros do mesmo tipo, vincule em{" "}
            <Link href="/workflow" className="text-primary hover:underline">
              Workflows
            </Link>{" "}
            (Tipos de processo vinculados).
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={selectedId}
              onChange={(e) =>
                setSelectedId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="h-9 rounded-md border border-input bg-card px-2 text-sm"
              aria-label="Workflow"
            >
              <option value="">Escolha um workflow…</option>
              {defs.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.nome} (v{d.versao})
                </option>
              ))}
            </select>
            <Button
              size="sm"
              disabled={selectedId === "" || iniciar.isPending}
              onClick={() => {
                if (selectedId === "") return;
                iniciar.mutate({ wfId: selectedId });
              }}
            >
              <PlayCircle className="mr-1 h-4 w-4" aria-hidden="true" />
              {iniciar.isPending ? "Iniciando…" : "Iniciar"}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

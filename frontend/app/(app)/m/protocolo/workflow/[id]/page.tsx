"use client";

import { useQuery } from "@tanstack/react-query";
import { GitBranch, Pencil } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { BadgeAtivo } from "@/components/protocolo/BadgeAtivo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { PageHeader } from "@/components/ui/page-header";
import { COR_WF } from "@/components/workflow/cores";
import { WorkflowDiagram } from "@/components/workflow/WorkflowDiagram";
import { WorkflowMapeamentoTipos } from "@/components/workflow/WorkflowMapeamentoTipos";
import { WorkflowVersoes } from "@/components/workflow/WorkflowVersoes";
import { workflowApi } from "@/lib/api";

export default function WorkflowDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);

  const q = useQuery({
    queryKey: ["workflow-definition", id],
    queryFn: () => workflowApi.getDefinition(id),
    enabled: Number.isFinite(id),
  });

  if (q.isLoading) {
    return <Carregando className="text-muted-foreground" />;
  }
  if (q.error || !q.data) {
    return (
      <div className="text-danger-soft-foreground">
        Erro ao carregar workflow: {(q.error as Error)?.message ?? "não encontrado"}
      </div>
    );
  }

  const wf = q.data;
  const dsl = wf.dsl;

  return (
    <div className="space-y-4">
      {/* A seta de voltar vem do PageHeader, pela trilha até a lista. */}
      <PageHeader
        icon={GitBranch}
        breadcrumbs={[
          { label: "Workflows", href: "/m/protocolo/workflow" },
          { label: wf.nome },
        ]}
        title={wf.nome}
        description={
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <span className="font-mono">{wf.slug}</span> · v{wf.versao} ·
            <BadgeAtivo ativo={wf.ativo} />
          </span>
        }
        actions={
          <Button asChild variant="secondary">
            <Link href={`/m/protocolo/workflow/${wf.id}/editar`}>
              <Pencil className="h-4 w-4" aria-hidden="true" />
              Editar (nova versão)
            </Link>
          </Button>
        }
      />

      {wf.descricao && (
        <p className="text-sm text-foreground">{wf.descricao}</p>
      )}

      <WorkflowVersoes wf={wf} />

      <WorkflowMapeamentoTipos wf={wf} />

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Diagrama
        </h2>
        <WorkflowDiagram dsl={dsl} height={520} />
        <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          {/* Legenda com as mesmas cores do diagrama (`components/workflow/cores`). */}
          <span>
            <span
              className="inline-block h-2 w-4 align-middle border-2 border-dashed"
              style={{ borderColor: COR_WF.inicial }}
            />{" "}
            inicial
          </span>
          <span>
            <span
              className="inline-block h-2 w-4 align-middle border-2"
              style={{ borderColor: COR_WF.final, background: COR_WF.finalFundo }}
            />{" "}
            final
          </span>
          <span>
            <span
              className="inline-block h-px w-4 align-middle"
              style={{ background: COR_WF.transicao }}
            />{" "}
            transição manual
          </span>
          <span>
            <span
              className="inline-block w-4 align-middle border-t border-dashed"
              style={{ borderColor: COR_WF.transicao }}
            />{" "}
            transição auto (evento)
          </span>
          <span>
            <span
              className="inline-block h-px w-4 align-middle"
              style={{ background: COR_WF.condicao }}
            />{" "}
            com condição
          </span>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Estados
          </h2>
          <ul className="space-y-1">
            {dsl.estados.map((e) => (
              <li
                key={e.slug}
                className="rounded border border-border bg-card px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="font-medium">{e.nome}</span>{" "}
                    <span className="font-mono text-xs text-muted-foreground">
                      {e.slug}
                    </span>
                  </div>
                  <div className="flex gap-1">
                    {e.slug === dsl.estado_inicial && (
                      <Badge intent="info">inicial</Badge>
                    )}
                    {e.final && <Badge intent="success">final</Badge>}
                    {e.sla_dias != null && (
                      <Badge intent="warning">SLA {e.sla_dias}d</Badge>
                    )}
                  </div>
                </div>
                {e.descricao && (
                  <p className="mt-1 text-xs text-muted-foreground">{e.descricao}</p>
                )}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Transições
          </h2>
          <ul className="space-y-1">
            {dsl.transicoes.length === 0 && (
              <li className="text-sm text-muted-foreground">Nenhuma transição.</li>
            )}
            {dsl.transicoes.map((t, i) => (
              <li
                key={i}
                className="rounded border border-border bg-card px-3 py-2 text-sm"
              >
                <div className="font-mono text-xs">
                  {t.de} → {t.para}
                </div>
                <div className="text-xs">{t.label}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {t.evento !== "manual" && (
                    <Badge intent="info">evento: {t.evento}</Badge>
                  )}
                  {t.condicao && (
                    <Badge intent="warning" title={t.condicao}>
                      condição
                    </Badge>
                  )}
                  {t.grupos_permitidos.length > 0 && (
                    <Badge intent="neutral">
                      grupos: {t.grupos_permitidos.join(", ")}
                    </Badge>
                  )}
                </div>
                {t.condicao && (
                  <pre className="mt-1 overflow-x-auto rounded bg-muted px-2 py-1 font-mono text-[10px]">
                    {t.condicao}
                  </pre>
                )}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </div>
  );
}

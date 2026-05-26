"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, GitBranch, Plus, XCircle } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { workflowApi } from "@/lib/api";

function fmtDate(s: string | null) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("pt-BR");
}

export default function WorkflowListPage() {
  const q = useQuery({
    queryKey: ["workflow-definitions", { apenasAtivos: false }],
    queryFn: () => workflowApi.listDefinitions(false),
  });

  return (
    <div className="space-y-4">
      <PageHeader
        icon={GitBranch}
        title="Workflows"
        description="Defina fluxos BPM associados a tipos de processo. Estados, transições, SLA e auto-encaminhamento por unidade."
        actions={
          <Link href="/workflow/novo">
            <Button size="md">
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo workflow
            </Button>
          </Link>
        }
      />

      <details className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
        <summary className="cursor-pointer font-medium text-blue-900">
          Como funciona o workflow? (3 passos)
        </summary>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-blue-900">
          <li>
            <strong>Crie um workflow</strong> aqui (botão "Novo workflow"). No
            editor: arraste da borda direita de um nodo até outro pra criar
            transição, ou segure <kbd className="rounded bg-white px-1">Shift</kbd>{" "}
            e clique nos dois nodos.
          </li>
          <li>
            <strong>Vincule a um tipo de processo</strong> na página do workflow
            (seção "Tipos de processo vinculados"). Sem isso, o workflow não
            instancia automaticamente.
          </li>
          <li>
            <strong>Abra um processo</strong> daquele tipo. O card{" "}
            <em>Workflow</em> mostra estado atual, transições disponíveis e SLA.
            Transições com <code>evento=encaminhamento/recebimento</code> disparam
            sozinhas; <code>manual</code> tem botão.
          </li>
        </ol>
      </details>

      {!q.isLoading && (q.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={GitBranch}
          title="Nenhum workflow definido ainda"
          description="Crie seu primeiro fluxo BPM para automatizar transições, SLA e auto-encaminhamento entre unidades."
          action={
            <Link href="/workflow/novo">
              <Button>
                <Plus className="h-4 w-4" aria-hidden="true" />
                Criar primeiro workflow
              </Button>
            </Link>
          }
        />
      ) : (
      <Table>
        <THead>
          <TR>
            <TH>#</TH>
            <TH>Nome</TH>
            <TH>Slug</TH>
            <TH>Versão</TH>
            <TH>Ativo</TH>
            <TH>Criado em</TH>
          </TR>
        </THead>
        <TBody>
          {q.isLoading &&
            Array.from({ length: 3 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {q.data?.map((w) => (
            <TR key={w.id}>
              <TD className="font-mono text-xs tabular-nums">{w.id}</TD>
              <TD>
                <Link
                  href={`/workflow/${w.id}`}
                  className="inline-flex items-center gap-2 font-medium text-primary hover:underline"
                >
                  <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
                  {w.nome}
                </Link>
              </TD>
              <TD className="font-mono text-xs">{w.slug}</TD>
              <TD className="font-mono text-xs tabular-nums">v{w.versao}</TD>
              <TD>
                {w.ativo ? (
                  <Badge intent="success" icon={CheckCircle2}>
                    Ativo
                  </Badge>
                ) : (
                  <Badge intent="neutral" icon={XCircle}>
                    Inativo
                  </Badge>
                )}
              </TD>
              <TD className="text-xs tabular-nums">{fmtDate(w.criado_em)}</TD>
            </TR>
          ))}
        </TBody>
      </Table>
      )}
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { auditApi, type AuditFilters } from "@/lib/api";
import { Shield } from "lucide-react";

function fmtDataHora(s: string): string {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    })
  );
}

function badgeIntentForAcao(acao: string): "info" | "success" | "warning" | "danger" | "neutral" {
  if (acao.endsWith(".aberto") || acao.endsWith(".criado")) return "success";
  if (acao.endsWith(".excluido") || acao.endsWith(".cancelado")) return "danger";
  if (acao.endsWith(".arquivado") || acao.endsWith(".finalizado")) return "neutral";
  if (acao.endsWith(".encaminhado") || acao.endsWith(".recebido")) return "info";
  if (acao.includes("workflow")) return "warning";
  return "neutral";
}

export default function AuditoriaPage() {
  const [draft, setDraft] = useState<AuditFilters>({ page: 1, page_size: 50 });
  const [applied, setApplied] = useState<AuditFilters>({ page: 1, page_size: 50 });

  const q = useQuery({
    queryKey: ["audit", applied],
    queryFn: () => auditApi.list(applied),
  });

  function apply() {
    setApplied({ ...draft, page: 1 });
  }

  function reset() {
    const fresh = { page: 1, page_size: 50 };
    setDraft(fresh);
    setApplied(fresh);
  }

  function goPage(p: number) {
    setApplied({ ...applied, page: p });
  }

  const data = q.data;
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;
  const currentPage = applied.page ?? 1;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Shield}
        title="Auditoria"
        description="Registro de ações realizadas no sistema (append-only). Filtre por entidade, ação, usuário ou período."
      />

      <div className="grid gap-3 rounded-md border border-border bg-card p-4 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <Label htmlFor="f-acao">Ação (prefixo)</Label>
          <Input
            id="f-acao"
            value={draft.acao ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, acao: e.target.value || undefined })
            }
            placeholder="ex: processo."
          />
        </div>
        <div>
          <Label htmlFor="f-ent">Entidade</Label>
          <Input
            id="f-ent"
            value={draft.entidade ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, entidade: e.target.value || undefined })
            }
            placeholder="ex: processo"
          />
        </div>
        <div>
          <Label htmlFor="f-id-ent">ID da entidade</Label>
          <Input
            id="f-id-ent"
            type="number"
            value={draft.id_entidade ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                id_entidade: e.target.value ? Number(e.target.value) : undefined,
              })
            }
          />
        </div>
        <div>
          <Label htmlFor="f-desde">Desde</Label>
          <Input
            id="f-desde"
            type="datetime-local"
            value={draft.desde ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, desde: e.target.value || undefined })
            }
          />
        </div>
        <div>
          <Label htmlFor="f-ate">Até</Label>
          <Input
            id="f-ate"
            type="datetime-local"
            value={draft.ate ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, ate: e.target.value || undefined })
            }
          />
        </div>
        <div className="sm:col-span-2 lg:col-span-5 flex gap-2">
          <Button onClick={apply}>
            <Search className="mr-1 h-4 w-4" aria-hidden="true" />
            Aplicar filtros
          </Button>
          <Button variant="ghost" onClick={reset}>
            Limpar
          </Button>
        </div>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>#</TH>
            <TH>Quando</TH>
            <TH>Usuário</TH>
            <TH>Ação</TH>
            <TH>Entidade</TH>
            <TH>Payload</TH>
          </TR>
        </THead>
        <TBody>
          {q.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {!q.isLoading && (data?.items.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={6} className="px-0 py-0">
                <EmptyState
                  className="border-0 rounded-none"
                  icon={Shield}
                  title="Nenhum registro encontrado"
                  description="Ajuste os filtros acima ou aguarde — toda ação no sistema aparece aqui."
                />
              </TD>
            </TR>
          )}
          {data?.items.map((it) => (
            <TR key={it.id}>
              <TD className="font-mono text-xs tabular-nums">{it.id}</TD>
              <TD className="text-xs tabular-nums">{fmtDataHora(it.criado_em)}</TD>
              <TD className="text-sm">
                {it.nome_usuario ?? (it.id_usuario ? `#${it.id_usuario}` : "—")}
              </TD>
              <TD>
                <Badge intent={badgeIntentForAcao(it.acao)}>
                  <span className="font-mono text-[10px]">{it.acao}</span>
                </Badge>
              </TD>
              <TD className="text-xs">
                {it.entidade}
                {it.id_entidade != null && (
                  <span className="font-mono text-muted-foreground"> #{it.id_entidade}</span>
                )}
              </TD>
              <TD className="text-xs">
                {it.payload ? (
                  <details>
                    <summary className="cursor-pointer text-primary">ver</summary>
                    <pre className="mt-1 max-w-md overflow-x-auto rounded bg-muted p-2 text-[10px]">
                      {JSON.stringify(it.payload, null, 2)}
                    </pre>
                  </details>
                ) : (
                  "—"
                )}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {data && data.total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {data.total} registro{data.total === 1 ? "" : "s"} ·{" "}
            página {currentPage} de {totalPages}
          </span>
          <div className="flex gap-1">
            <Button
              size="sm"
              variant="secondary"
              disabled={currentPage <= 1}
              onClick={() => goPage(currentPage - 1)}
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={currentPage >= totalPages}
              onClick={() => goPage(currentPage + 1)}
            >
              <ChevronRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

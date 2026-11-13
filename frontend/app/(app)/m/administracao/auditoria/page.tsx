"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, Shield, X as XIcon } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FilterBar } from "@/components/ui/filter-bar";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { auditApi, type AuditFilters } from "@/lib/api";

// dd/mm/aaaa hh:mm na lista; o segundo exato fica no title da célula — numa
// trilha de auditoria ele importa, mas não precisa alargar a coluna.
function fmtDataHora(s: string): string {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function fmtDataHoraCompleta(s: string): string {
  return new Date(s).toLocaleString("pt-BR");
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

  // Enter num campo de texto aplica, como numa busca.
  function aoTeclar(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") apply();
  }

  // "Limpar" só aparece quando há filtro digitado ou aplicado.
  const temFiltro = (f: AuditFilters) =>
    !!(f.acao || f.entidade || f.id_entidade != null || f.desde || f.ate);
  const filtrado = temFiltro(draft) || temFiltro(applied);

  const data = q.data;
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;
  const currentPage = applied.page ?? 1;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Shield}
        title="Auditoria"
        description="Registro de tudo o que foi feito no sistema, sem edição nem exclusão. Filtre por ação, entidade ou período."
      />

      <FilterBar>
        <FilterBar.Group label="Ação (prefixo)" className="w-full sm:w-44">
          <Input
            aria-label="Ação (prefixo)"
            value={draft.acao ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, acao: e.target.value || undefined })
            }
            onKeyDown={aoTeclar}
            placeholder="Ex.: processo."
          />
        </FilterBar.Group>
        <FilterBar.Group label="Entidade" className="w-full sm:w-44">
          <Input
            aria-label="Entidade"
            value={draft.entidade ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, entidade: e.target.value || undefined })
            }
            onKeyDown={aoTeclar}
            placeholder="Ex.: processo"
          />
        </FilterBar.Group>
        <FilterBar.Group label="ID da entidade" className="w-full sm:w-32">
          <Input
            aria-label="ID da entidade"
            type="number"
            inputMode="numeric"
            value={draft.id_entidade ?? ""}
            onChange={(e) =>
              setDraft({
                ...draft,
                id_entidade: e.target.value ? Number(e.target.value) : undefined,
              })
            }
            onKeyDown={aoTeclar}
            placeholder="Ex.: 1234"
          />
        </FilterBar.Group>
        <FilterBar.Group label="Desde" className="w-full sm:w-52">
          <Input
            aria-label="Desde"
            type="datetime-local"
            value={draft.desde ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, desde: e.target.value || undefined })
            }
          />
        </FilterBar.Group>
        <FilterBar.Group label="Até" className="w-full sm:w-52">
          <Input
            aria-label="Até"
            type="datetime-local"
            value={draft.ate ?? ""}
            onChange={(e) =>
              setDraft({ ...draft, ate: e.target.value || undefined })
            }
          />
        </FilterBar.Group>
        <FilterBar.Actions>
          {filtrado && (
            <Button variant="ghost" onClick={reset}>
              <XIcon className="h-4 w-4" aria-hidden="true" />
              Limpar
            </Button>
          )}
          <Button onClick={apply}>
            <Search className="h-4 w-4" aria-hidden="true" />
            Aplicar filtros
          </Button>
        </FilterBar.Actions>
      </FilterBar>

      <Table>
        <THead>
          <TR>
            <TH>#</TH>
            <TH>Quando</TH>
            <TH>Usuário</TH>
            <TH>Ação</TH>
            <TH>Entidade</TH>
            <TH>Dados</TH>
          </TR>
        </THead>
        <TBody>
          {q.isLoading &&
            Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={6} />)}
          {!q.isLoading && (data?.items.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={6} className="px-0 py-0">
                <EmptyState
                  className="border-0 bg-transparent"
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
              <TD className="whitespace-nowrap text-xs tabular-nums" title={fmtDataHoraCompleta(it.criado_em)}>
                {fmtDataHora(it.criado_em)}
              </TD>
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
                  <span className="font-mono text-foreground-muted"> #{it.id_entidade}</span>
                )}
              </TD>
              <TD className="text-xs">
                {it.payload ? (
                  <details>
                    <summary className="cursor-pointer text-primary hover:underline">Ver dados</summary>
                    <pre className="mt-1 max-w-md overflow-x-auto rounded-md bg-surface-2 p-2 text-[10px] text-foreground">
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
        <div className="flex items-center justify-between text-sm text-foreground-muted">
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

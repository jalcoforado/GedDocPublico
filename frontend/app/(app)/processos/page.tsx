"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, FileText, Lock, Pause, Plus, SearchX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { SkeletonRow } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { api, NIVEL_SIGILO_LABEL, type ProcessoListFilters } from "@/lib/api";

const PAGE_SIZE = 20;

function fmtDate(s: string) {
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

export default function ProcessosPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<ProcessoListFilters>({
    apenas_ativos: true,
  });
  const [draft, setDraft] = useState<ProcessoListFilters>({});

  const assuntosQ = useQuery({
    queryKey: ["assuntos-all"],
    queryFn: () => api.assuntos.list({ page_size: 200 }),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  const processosQ = useQuery({
    queryKey: ["processos", page, filters],
    queryFn: () =>
      api.processos.list({
        ...filters,
        page,
        page_size: PAGE_SIZE,
      }),
  });

  function applyFilters() {
    setPage(1);
    setFilters({ ...draft, apenas_ativos: draft.apenas_ativos ?? false });
  }

  function clearFilters() {
    setDraft({});
    setFilters({});
    setPage(1);
  }

  const totalPages = processosQ.data
    ? Math.max(1, Math.ceil(processosQ.data.total / PAGE_SIZE))
    : 1;

  return (
    <div className="space-y-4">
      <PageHeader
        icon={FileText}
        title="Processos"
        description="Liste, filtre e abra processos administrativos. Use a busca avançada nos filtros abaixo ou tecle / para busca global."
        actions={
          <Link href="/processos/novo">
            <Button>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Novo processo
            </Button>
          </Link>
        }
      />

      <Card>
        <CardContent>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <div className="md:col-span-2">
              <Label htmlFor="q">Busca (número / manifestante / assunto)</Label>
              <Input
                id="q"
                value={draft.q ?? ""}
                onChange={(e) => setDraft({ ...draft, q: e.target.value })}
                placeholder="Ex: 2026/000001 ou José"
                inputMode="search"
              />
            </div>
            <div>
              <Label htmlFor="assunto">Assunto</Label>
              <Select
                id="assunto"
                value={draft.id_assunto ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_assunto: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todos</option>
                {assuntosQ.data?.items.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.assunto.length > 60 ? a.assunto.slice(0, 60) + "…" : a.assunto}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="unidade">Unidade (proprietária ou local atual)</Label>
              <Select
                id="unidade"
                value={draft.id_unidade ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    id_unidade: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
              >
                <option value="">Todas</option>
                {unidadesQ.data?.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.unidade_trabalho}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="desde">Aberto desde</Label>
              <Input
                id="desde"
                type="date"
                value={draft.desde?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    desde: e.target.value ? `${e.target.value}T00:00:00` : undefined,
                  })
                }
              />
            </div>
            <div>
              <Label htmlFor="ate">Aberto até</Label>
              <Input
                id="ate"
                type="date"
                value={draft.ate?.slice(0, 10) ?? ""}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    ate: e.target.value ? `${e.target.value}T23:59:59` : undefined,
                  })
                }
              />
            </div>
            <div className="flex items-center gap-2">
              <Checkbox
                id="ativos"
                checked={!!draft.apenas_ativos}
                onChange={(e) => setDraft({ ...draft, apenas_ativos: e.target.checked })}
              />
              <Label htmlFor="ativos" className="!mb-0">
                Apenas ativos
              </Label>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <Button onClick={applyFilters}>Filtrar</Button>
              <Button variant="ghost" onClick={clearFilters}>
                Limpar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Table>
        <THead>
          <TR>
            <TH>Número</TH>
            <TH>Aberto em</TH>
            <TH>Manifestante</TH>
            <TH>Assunto</TH>
            <TH>Local atual</TH>
            <TH>Status</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {processosQ.isLoading &&
            Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} cols={7} />)}
          {!processosQ.isLoading && (processosQ.data?.items.length ?? 0) === 0 && (
            <TR>
              <TD colSpan={7} className="p-0">
                <EmptyState
                  icon={SearchX}
                  title="Nenhum processo encontrado"
                  description="Ajuste os filtros ou crie um novo processo."
                  className="border-0 bg-transparent"
                />
              </TD>
            </TR>
          )}
          {processosQ.data?.items.map((p) => (
            <TR key={p.id}>
              <TD className="font-mono text-xs tabular-nums">
                {p.nup ? (
                  <>
                    <div>{p.nup}</div>
                    <div className="text-[10px] text-foreground-muted">
                      {p.numero_processo}
                    </div>
                  </>
                ) : (
                  p.numero_processo
                )}
              </TD>
              <TD className="text-xs tabular-nums">{fmtDate(p.data_hora_abertura)}</TD>
              <TD>
                <div className="text-sm text-foreground">{p.manifestante ?? "—"}</div>
                <div className="text-xs text-muted-foreground">
                  {p.manifestante_cpf_cnpj ?? ""}
                </div>
              </TD>
              <TD>
                <div className="line-clamp-1 text-sm">{p.assunto ?? "—"}</div>
                <div className="text-xs text-muted-foreground">{p.tipo_processo ?? ""}</div>
              </TD>
              <TD className="text-sm">{p.local_atual ?? "—"}</TD>
              <TD>
                <div className="flex flex-wrap gap-1">
                  {p.ativo ? (
                    <Badge intent="success" icon={CheckCircle2}>
                      Ativo
                    </Badge>
                  ) : (
                    <Badge intent="neutral" icon={Pause}>
                      Inativo
                    </Badge>
                  )}
                  {!p.publico && (
                    <Badge intent="warning" icon={Lock}>
                      {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                    </Badge>
                  )}
                </div>
              </TD>
              <TD className="text-right">
                <Link
                  href={`/processos/${p.id}`}
                  className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Abrir →
                </Link>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      {processosQ.data && processosQ.data.total > 0 && (
        <div className="flex flex-col items-start justify-between gap-2 text-sm text-muted-foreground sm:flex-row sm:items-center">
          <span className="tabular-nums">
            {processosQ.data.total} processos — página {page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              Anterior
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Próxima
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

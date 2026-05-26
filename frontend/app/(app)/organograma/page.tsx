"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronsDownUp,
  ChevronsUpDown,
  LayoutList,
  Loader2,
  Network,
  Plus,
  Search,
  X as XIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { OrganogramaDiagramView } from "@/components/organograma/OrganogramaDiagramView";
import { OrganogramaListView } from "@/components/organograma/OrganogramaListView";
import {
  UnidadeEditDrawer,
  type DrawerMode,
} from "@/components/organograma/UnidadeEditDrawer";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import {
  api,
  organogramaApi,
  type OrganogramaNo,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

type ViewMode = "list" | "diagram";
type HeatmapMetric = "none" | "processos_ativos" | "sla_pendentes" | "tempo_medio_dias";

const COLLAPSED_KEY = "aprimora.organograma.collapsed.v1";
const VIEW_KEY = "aprimora.organograma.view.v1";

const HEATMAP_LABELS: Record<HeatmapMetric, string> = {
  none: "Sem heatmap",
  processos_ativos: "Processos ativos",
  sla_pendentes: "SLA pendentes",
  tempo_medio_dias: "Tempo médio (30d)",
};

function metricValue(no: OrganogramaNo, m: HeatmapMetric): number | null {
  if (m === "none") return null;
  if (m === "tempo_medio_dias") return no.tempo_medio_dias;
  return no[m] as number;
}

function heatColor(normalized: number): string {
  const n = Math.max(0, Math.min(1, normalized));
  const hue = (1 - n) * 120;
  return `hsl(${hue}, 60%, 92%)`;
}

export default function OrganogramaPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();

  const canInsert = can("unidadeTrabalho", "inserir");
  const canUpdate = can("unidadeTrabalho", "atualizar");
  const canDelete = can("unidadeTrabalho", "excluir");
  const isReadOnly = !canInsert && !canUpdate && !canDelete;

  const q = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
    refetchInterval: 60_000,
  });

  const [view, setView] = useState<ViewMode>("list");
  const [search, setSearch] = useState("");
  const [metric, setMetric] = useState<HeatmapMetric>("none");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const [drawerMode, setDrawerMode] = useState<DrawerMode | null>(null);

  // Hydrate state from localStorage
  useEffect(() => {
    try {
      const v = window.localStorage.getItem(VIEW_KEY);
      if (v === "list" || v === "diagram") setView(v);
      const c = window.localStorage.getItem(COLLAPSED_KEY);
      if (c) {
        const arr = JSON.parse(c);
        if (Array.isArray(arr)) setCollapsed(new Set(arr.map(Number)));
      }
    } catch {
      // ignore
    }
  }, []);

  // Persist view
  useEffect(() => {
    try {
      window.localStorage.setItem(VIEW_KEY, view);
    } catch {
      // ignore
    }
  }, [view]);

  // Persist collapsed
  useEffect(() => {
    try {
      window.localStorage.setItem(
        COLLAPSED_KEY,
        JSON.stringify(Array.from(collapsed)),
      );
    } catch {
      // ignore
    }
  }, [collapsed]);

  const nos = q.data ?? [];

  const heatMax = useMemo(() => {
    if (metric === "none" || nos.length === 0) return 0;
    const vals = nos
      .map((n) => metricValue(n, metric))
      .filter((v): v is number => v != null && v > 0);
    return vals.length > 0 ? Math.max(...vals) : 0;
  }, [nos, metric]);

  const heatBg = useMemo(() => {
    const m = new Map<number, string>();
    if (metric === "none" || heatMax <= 0) return m;
    for (const no of nos) {
      const v = metricValue(no, metric);
      if (v != null && v > 0) m.set(no.id, heatColor(v / heatMax));
    }
    return m;
  }, [nos, metric, heatMax]);

  function toggle(id: number) {
    setCollapsed((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function expandAll() {
    setCollapsed(new Set());
  }

  function collapseAll() {
    // Recolhe todos que têm filhos
    const withChildren = new Set<number>();
    const hasChild = new Set<number>();
    for (const n of nos) {
      if (n.id_unidade_pai != null) hasChild.add(n.id_unidade_pai);
    }
    for (const id of hasChild) withChildren.add(id);
    setCollapsed(withChildren);
  }

  const deleteM = useMutation({
    mutationFn: (id: number) => api.unidades.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organograma"] });
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Unidade excluída.");
      setSelectedId(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reparentM = useMutation({
    mutationFn: (args: { id: number; newParentId: number | null }) =>
      api.unidades.update(args.id, { id_unidade_pai: args.newParentId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organograma"] });
      qc.invalidateQueries({ queryKey: ["unidades"] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Descobre se `candidateParent` é descendente de `id` (impede ciclo).
  function isDescendantOf(id: number, candidateParent: number): boolean {
    const children = new Map<number | null, number[]>();
    for (const n of nos) {
      if (!children.has(n.id_unidade_pai)) children.set(n.id_unidade_pai, []);
      children.get(n.id_unidade_pai)!.push(n.id);
    }
    const stack = [id];
    const visited = new Set<number>();
    while (stack.length > 0) {
      const cur = stack.pop()!;
      if (visited.has(cur)) continue;
      visited.add(cur);
      if (cur === candidateParent) return true;
      const kids = children.get(cur) ?? [];
      for (const k of kids) stack.push(k);
    }
    return false;
  }

  async function handleReparent(
    draggedId: number,
    newParentId: number | null,
  ): Promise<boolean> {
    const dragged = nos.find((n) => n.id === draggedId);
    if (!dragged) return false;
    if (dragged.id_unidade_pai === newParentId) return false; // sem mudança
    if (newParentId === draggedId) {
      toast.error("Não pode definir uma unidade como pai dela mesma.");
      return false;
    }
    if (newParentId != null && isDescendantOf(draggedId, newParentId)) {
      toast.error("Não pode mover para baixo de uma subordinada (cria ciclo).");
      return false;
    }
    const oldParentId = dragged.id_unidade_pai;
    const newParentLabel =
      newParentId == null
        ? "raiz"
        : nos.find((n) => n.id === newParentId)?.unidade_trabalho ?? `#${newParentId}`;
    try {
      await reparentM.mutateAsync({ id: draggedId, newParentId });
      toast.success(`${dragged.unidade_trabalho} → ${newParentLabel}.`, {
        action: {
          label: "Desfazer",
          onClick: () => {
            reparentM.mutate(
              { id: draggedId, newParentId: oldParentId },
              {
                onSuccess: () => toast.info("Movimento desfeito."),
              },
            );
          },
        },
      });
      return true;
    } catch {
      return false;
    }
  }

  async function handleDelete(no: OrganogramaNo) {
    const hasChildren = nos.some((n) => n.id_unidade_pai === no.id);
    const ok = await confirm({
      title: "Excluir unidade?",
      message: (
        <div className="space-y-2 text-sm">
          <p>
            Excluir <strong>{no.unidade_trabalho}</strong>?
          </p>
          {hasChildren && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="text-xs">
                Esta unidade tem subordinadas — elas ficarão órfãs no
                organograma. Considere mover as filhas antes.
              </span>
            </div>
          )}
        </div>
      ),
      confirmLabel: "Excluir",
      cancelLabel: "Cancelar",
      intent: "danger",
    });
    if (ok) deleteM.mutate(no.id);
  }

  // Auto-load Unidade detail for drawer edit
  const editM = useMutation({
    mutationFn: (id: number) => api.unidades.get(id),
    onSuccess: (u) => setDrawerMode({ kind: "edit", unidade: u }),
    onError: (e: Error) => toast.error(e.message),
  });

  function openEdit(no: OrganogramaNo) {
    editM.mutate(no.id);
  }

  function openAddChild(parentId: number) {
    setDrawerMode({ kind: "create", parentId });
  }

  function openAddRoot() {
    setDrawerMode({ kind: "create", parentId: null });
  }

  const selecionada = nos.find((n) => n.id === selectedId) ?? null;

  const isFiltered = search.trim().length > 0;
  // Auto-expand quando há filtro pra mostrar matches
  const effectiveCollapsed = useMemo(
    () => (isFiltered ? new Set<number>() : collapsed),
    [isFiltered, collapsed],
  );

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Network}
        title="Organograma"
        description={
          isReadOnly
            ? "Estrutura hierárquica das unidades com KPIs em tempo real. Você tem acesso de leitura — peça permissão pra editar."
            : "Estrutura hierárquica das unidades com KPIs em tempo real. Edite, mova e organize."
        }
        actions={
          canInsert && (
            <Button size="md" onClick={openAddRoot}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Nova unidade
            </Button>
          )
        }
      />

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3">
        {/* View toggle */}
        <div className="flex rounded-md border border-border bg-surface-1 p-0.5">
          <button
            type="button"
            onClick={() => setView("list")}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded px-3 text-xs font-medium transition-colors duration-fast",
              view === "list"
                ? "bg-brand text-primary-foreground shadow-sm"
                : "text-foreground-muted hover:bg-muted",
            )}
          >
            <LayoutList className="h-3.5 w-3.5" aria-hidden="true" />
            Lista
          </button>
          <button
            type="button"
            onClick={() => setView("diagram")}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded px-3 text-xs font-medium transition-colors duration-fast",
              view === "diagram"
                ? "bg-brand text-primary-foreground shadow-sm"
                : "text-foreground-muted hover:bg-muted",
            )}
          >
            <Network className="h-3.5 w-3.5" aria-hidden="true" />
            Diagrama
          </button>
        </div>

        {/* Search */}
        <div className="relative min-w-[200px] flex-1">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground-muted"
            aria-hidden="true"
          />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Buscar por nome ou sigla…"
            className="pl-8 pr-8"
          />
          {search && (
            <button
              type="button"
              onClick={() => setSearch("")}
              aria-label="Limpar busca"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-foreground-muted hover:bg-muted hover:text-foreground"
            >
              <XIcon className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Expand/Collapse all */}
        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={expandAll}
            title="Expandir tudo"
          >
            <ChevronsUpDown className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">Expandir</span>
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={collapseAll}
            title="Recolher tudo"
          >
            <ChevronsDownUp className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">Recolher</span>
          </Button>
        </div>

        {/* Heatmap selector */}
        <div className="flex rounded-md border border-border bg-surface-1 p-0.5">
          {(
            ["none", "processos_ativos", "sla_pendentes", "tempo_medio_dias"] as HeatmapMetric[]
          ).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMetric(m)}
              className={cn(
                "h-9 rounded px-2.5 text-[11px] font-medium transition-colors duration-fast",
                metric === m
                  ? "bg-brand text-primary-foreground shadow-sm"
                  : "text-foreground-muted hover:bg-muted",
              )}
              title={HEATMAP_LABELS[m]}
            >
              {HEATMAP_LABELS[m]}
            </button>
          ))}
        </div>
      </div>

      {/* Heatmap legend */}
      {metric !== "none" && heatMax > 0 && (
        <div className="flex items-center gap-2 text-xs text-foreground-muted">
          <span>{HEATMAP_LABELS[metric]}: baixo</span>
          <span
            className="inline-block h-3 w-32 rounded"
            style={{
              background:
                "linear-gradient(to right, hsl(120,60%,92%), hsl(60,60%,92%), hsl(0,60%,92%))",
            }}
          />
          <span>alto (máx {heatMax.toFixed(0)})</span>
        </div>
      )}

      {/* Conteúdo */}
      {q.isLoading && (
        <div className="flex items-center justify-center rounded-lg border border-border bg-card p-12 text-sm text-foreground-muted">
          <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
          Carregando organograma…
        </div>
      )}

      {!q.isLoading && nos.length === 0 && (
        <EmptyState
          icon={Network}
          title="Nenhuma unidade cadastrada"
          description="Crie a primeira unidade do organograma. Geralmente comece pela 'raiz' (a Prefeitura, por exemplo) e vá adicionando secretarias como subordinadas."
          action={
            <Button onClick={openAddRoot}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Criar primeira unidade
            </Button>
          }
        />
      )}

      {!q.isLoading && nos.length > 0 && view === "list" && (
        <OrganogramaListView
          nos={nos}
          collapsed={effectiveCollapsed}
          onToggle={toggle}
          onSelect={setSelectedId}
          selectedId={selectedId}
          onEdit={canUpdate ? openEdit : undefined}
          onAddChild={canInsert ? openAddChild : undefined}
          onDelete={canDelete ? handleDelete : undefined}
          onReparent={canUpdate ? handleReparent : undefined}
          search={search}
          heatBg={heatBg}
        />
      )}

      {!q.isLoading && nos.length > 0 && view === "diagram" && (
        <div
          className="rounded-lg border border-border bg-surface-2/30"
          style={{ height: "calc(100vh - 380px)", minHeight: 480 }}
        >
          <OrganogramaDiagramView
            nos={nos}
            collapsed={effectiveCollapsed}
            onToggle={toggle}
            onSelect={(id) => setSelectedId(id < 0 ? null : id)}
            selectedId={selectedId}
            onEdit={canUpdate ? openEdit : undefined}
            onAddChild={canInsert ? openAddChild : undefined}
            onDelete={canDelete ? handleDelete : undefined}
            onReparent={canUpdate ? handleReparent : undefined}
            heatBg={heatBg}
          />
        </div>
      )}

      {/* Detalhe da seleção */}
      {selecionada && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold">
                {selecionada.unidade_trabalho}
              </h2>
              <p className="mt-0.5 text-xs text-foreground-muted">
                {selecionada.sigla ? `${selecionada.sigla} · ` : ""}id #
                {selecionada.id}
                {selecionada.id_unidade_pai != null &&
                  ` · subordinada à #${selecionada.id_unidade_pai}`}
              </p>
            </div>
            <div className="flex gap-1">
              {canUpdate && (
                <Button size="sm" variant="secondary" onClick={() => openEdit(selecionada)}>
                  Editar
                </Button>
              )}
              {canInsert && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => openAddChild(selecionada.id)}
                >
                  + Subordinada
                </Button>
              )}
            </div>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
            <div className="rounded-md border border-border bg-surface-2/50 p-2">
              <div className="text-[10px] uppercase tracking-wide text-foreground-subtle">
                Processos ativos
              </div>
              <div className="font-mono text-lg font-bold tabular-nums">
                {selecionada.processos_ativos}
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface-2/50 p-2">
              <div className="text-[10px] uppercase tracking-wide text-foreground-subtle">
                Usuários ativos
              </div>
              <div className="font-mono text-lg font-bold tabular-nums">
                {selecionada.usuarios}
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface-2/50 p-2">
              <div className="text-[10px] uppercase tracking-wide text-foreground-subtle">
                SLA pendentes
              </div>
              <div
                className={cn(
                  "font-mono text-lg font-bold tabular-nums",
                  selecionada.sla_pendentes > 0 && "text-warning",
                )}
              >
                {selecionada.sla_pendentes}
              </div>
            </div>
            <div className="rounded-md border border-border bg-surface-2/50 p-2">
              <div className="text-[10px] uppercase tracking-wide text-foreground-subtle">
                Tempo médio (30d)
              </div>
              <div className="font-mono text-lg font-bold tabular-nums">
                {selecionada.tempo_medio_dias != null
                  ? `${selecionada.tempo_medio_dias.toFixed(1)}d`
                  : "—"}
              </div>
            </div>
          </div>
        </div>
      )}

      <UnidadeEditDrawer
        open={drawerMode !== null}
        mode={drawerMode}
        allNos={nos}
        canDelete={canDelete}
        onClose={() => setDrawerMode(null)}
      />
    </div>
  );
}
// drag-to-reparent v1

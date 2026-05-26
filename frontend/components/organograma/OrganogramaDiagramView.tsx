"use client";

import {
  Background,
  ConnectionMode,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  AlertTriangle,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  Pencil,
  Plus,
  Trash2,
  Users,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";

import type { OrganogramaNo } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  nos: OrganogramaNo[];
  collapsed: Set<number>;
  onToggle: (id: number) => void;
  onSelect: (id: number) => void;
  selectedId: number | null;
  /** Quando ausente, o usuário não tem perm pra editar (botão escondido). */
  onEdit?: (no: OrganogramaNo) => void;
  /** Quando ausente, sem perm pra criar (botão + escondido). */
  onAddChild?: (parentId: number) => void;
  /** Quando ausente, sem perm pra excluir (botão 🗑 escondido). */
  onDelete?: (no: OrganogramaNo) => void;
  /** Quando ausente, sem perm pra mover (drag desabilitado). */
  onReparent?: (draggedId: number, newParentId: number | null) => Promise<boolean>;
  /** Heatmap por unidade: id → cor (string CSS), opcional */
  heatBg?: Map<number, string>;
}

function descendantsOf(nos: OrganogramaNo[], id: number): Set<number> {
  const children = new Map<number | null, number[]>();
  for (const n of nos) {
    if (!children.has(n.id_unidade_pai)) children.set(n.id_unidade_pai, []);
    children.get(n.id_unidade_pai)!.push(n.id);
  }
  const out = new Set<number>([id]);
  const stack = [id];
  while (stack.length) {
    const cur = stack.pop()!;
    for (const k of children.get(cur) ?? []) {
      if (!out.has(k)) {
        out.add(k);
        stack.push(k);
      }
    }
  }
  return out;
}

const NODE_WIDTH = 240;
const NODE_HEIGHT = 96;
const COL_GAP = 40;
const ROW_GAP = 48;

interface LayoutResult {
  positions: Map<number, { x: number; y: number }>;
  visible: Set<number>;
  hiddenCount: Map<number, number>;
}

function layout(
  nos: OrganogramaNo[],
  collapsed: Set<number>,
): LayoutResult {
  const byId = new Map(nos.map((n) => [n.id, n]));
  const children = new Map<number | null, OrganogramaNo[]>();
  for (const n of nos) {
    if (!children.has(n.id_unidade_pai))
      children.set(n.id_unidade_pai, []);
    children.get(n.id_unidade_pai)!.push(n);
  }
  for (const list of children.values()) {
    list.sort((a, b) => a.unidade_trabalho.localeCompare(b.unidade_trabalho));
  }

  const positions = new Map<number, { x: number; y: number }>();
  const visible = new Set<number>();
  const hiddenCount = new Map<number, number>();
  let nextX = 0;

  function countDescendants(id: number): number {
    const kids = children.get(id) ?? [];
    let total = kids.length;
    for (const k of kids) total += countDescendants(k.id);
    return total;
  }

  function visit(node: OrganogramaNo, depth: number) {
    visible.add(node.id);
    const kids = children.get(node.id) ?? [];
    const isCollapsed = collapsed.has(node.id);

    if (kids.length === 0 || isCollapsed) {
      if (isCollapsed && kids.length > 0) {
        hiddenCount.set(node.id, countDescendants(node.id));
      }
      positions.set(node.id, {
        x: nextX * (NODE_WIDTH + COL_GAP),
        y: depth * (NODE_HEIGHT + ROW_GAP),
      });
      nextX++;
      return;
    }

    const startX = nextX;
    for (const k of kids) visit(k, depth + 1);
    const endX = nextX - 1;
    const centerX = (startX + endX) / 2;
    positions.set(node.id, {
      x: centerX * (NODE_WIDTH + COL_GAP),
      y: depth * (NODE_HEIGHT + ROW_GAP),
    });
  }

  const roots = nos.filter(
    (n) => n.id_unidade_pai == null || !byId.has(n.id_unidade_pai),
  );
  roots.sort((a, b) => a.unidade_trabalho.localeCompare(b.unidade_trabalho));
  for (const r of roots) visit(r, 0);

  return { positions, visible, hiddenCount };
}

function NodeCard({
  no,
  selected,
  hiddenChildren,
  hasChildren,
  isCollapsed,
  onToggle,
  onEdit,
  onAddChild,
  onDelete,
}: {
  no: OrganogramaNo;
  selected: boolean;
  hiddenChildren: number;
  hasChildren: boolean;
  isCollapsed: boolean;
  onToggle: (id: number) => void;
  onEdit?: (no: OrganogramaNo) => void;
  onAddChild?: (parentId: number) => void;
  onDelete?: (no: OrganogramaNo) => void;
}) {
  const hasActions = !!(onEdit || onAddChild || onDelete);
  return (
    <div className="group relative h-full" style={{ width: NODE_WIDTH - 24 }}>
      <div className="flex items-start gap-2">
        <Building2
          className="h-4 w-4 shrink-0 text-foreground-muted"
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold leading-tight">
            {no.unidade_trabalho}
          </div>
          {no.sigla && (
            <div className="font-mono text-[10px] uppercase text-foreground-subtle">
              {no.sigla}
            </div>
          )}
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px]">
        <span className="inline-flex items-center gap-1 text-foreground-muted">
          <FileText className="h-3 w-3 text-blue-600" aria-hidden="true" />
          <span className="font-mono tabular-nums font-medium text-foreground">
            {no.processos_ativos}
          </span>
          proc.
        </span>
        <span className="inline-flex items-center gap-1 text-foreground-muted">
          <Users className="h-3 w-3" aria-hidden="true" />
          <span className="font-mono tabular-nums font-medium text-foreground">
            {no.usuarios}
          </span>
          usu.
        </span>
        <span
          className={cn(
            "inline-flex items-center gap-1 text-foreground-muted",
            no.sla_pendentes > 0 && "text-warning",
          )}
        >
          <AlertTriangle className="h-3 w-3" aria-hidden="true" />
          <span className="font-mono tabular-nums font-medium">
            {no.sla_pendentes}
          </span>
          SLA
        </span>
        {no.tempo_medio_dias != null && (
          <span className="inline-flex items-center gap-1 text-foreground-muted">
            <Clock className="h-3 w-3" aria-hidden="true" />
            <span className="font-mono tabular-nums font-medium text-foreground">
              {no.tempo_medio_dias.toFixed(1)}d
            </span>
          </span>
        )}
      </div>

      {/* Collapse toggle bottom-center */}
      {hasChildren && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onToggle(no.id);
          }}
          aria-label={isCollapsed ? "Expandir filhas" : "Recolher filhas"}
          className={cn(
            "absolute -bottom-3 left-1/2 inline-flex h-6 w-6 -translate-x-1/2 items-center justify-center",
            "rounded-full border border-border bg-card shadow-sm transition-colors duration-fast",
            "hover:bg-brand/10 hover:text-brand hover:border-brand/30",
            isCollapsed && "bg-brand/10 text-brand border-brand/30",
          )}
        >
          {isCollapsed ? (
            <span className="relative">
              <ChevronRight className="h-3 w-3" aria-hidden="true" />
              {hiddenChildren > 0 && (
                <span className="absolute -right-3 -top-2 rounded-full bg-accent px-1 text-[8px] font-bold leading-tight text-white">
                  {hiddenChildren > 99 ? "99+" : hiddenChildren}
                </span>
              )}
            </span>
          ) : (
            <ChevronDown className="h-3 w-3" aria-hidden="true" />
          )}
        </button>
      )}

      {/* Floating action toolbar — visible on hover/selected, esconde se sem perm */}
      {hasActions && (
        <div
          className={cn(
            "absolute -top-3 right-0 flex items-center gap-0.5 rounded-md border border-border bg-card p-0.5 shadow-md transition-opacity duration-fast",
            selected
              ? "opacity-100"
              : "opacity-0 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto",
          )}
        >
          {onAddChild && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onAddChild(no.id);
              }}
              title="Adicionar subordinada"
              className="inline-flex h-6 w-6 items-center justify-center rounded text-foreground-muted hover:bg-brand/10 hover:text-brand"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
          {onEdit && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(no);
              }}
              title="Editar"
              className="inline-flex h-6 w-6 items-center justify-center rounded text-foreground-muted hover:bg-muted hover:text-foreground"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(no);
              }}
              title="Excluir"
              className="inline-flex h-6 w-6 items-center justify-center rounded text-foreground-muted hover:bg-danger-soft hover:text-danger"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export function OrganogramaDiagramView({
  nos,
  collapsed,
  onToggle,
  onSelect,
  selectedId,
  onEdit,
  onAddChild,
  onDelete,
  onReparent,
  heatBg,
}: Props) {
  const flowRef = useRef<ReactFlowInstance | null>(null);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [hoverTargetId, setHoverTargetId] = useState<number | null>(null);
  const draggedDescendants = useRef<Set<number>>(new Set());
  const dragStartPos = useRef<{ x: number; y: number } | null>(null);
  // Bump this on every drag stop to force layout/positions reset
  const [resetTick, setResetTick] = useState(0);

  const { nodes, edges } = useMemo(() => {
    const { positions, visible, hiddenCount } = layout(nos, collapsed);
    const byId = new Map(nos.map((n) => [n.id, n]));
    const childrenSet = new Set<number>();
    for (const n of nos) {
      if (n.id_unidade_pai != null) {
        const parent = byId.get(n.id_unidade_pai);
        if (parent) childrenSet.add(parent.id);
      }
    }

    const visibleNos = nos.filter((n) => visible.has(n.id));
    const ids = new Set(visibleNos.map((n) => n.id));

    const nodes: Node[] = visibleNos.map((no) => {
      const p = positions.get(no.id) ?? { x: 0, y: 0 };
      const bg = heatBg?.get(no.id);
      const isSelected = selectedId === no.id;
      const isDropTarget = hoverTargetId === no.id;
      const isDragging = draggedId === no.id;
      const isInvalidTarget =
        draggedId !== null && draggedDescendants.current.has(no.id) && no.id !== draggedId;
      return {
        id: String(no.id),
        position: p,
        draggable: !!onReparent,
        data: {
          label: (
            <NodeCard
              no={no}
              selected={isSelected}
              hiddenChildren={hiddenCount.get(no.id) ?? 0}
              hasChildren={childrenSet.has(no.id)}
              isCollapsed={collapsed.has(no.id)}
              onToggle={onToggle}
              onEdit={onEdit}
              onAddChild={onAddChild}
              onDelete={onDelete}
            />
          ),
        },
        style: {
          border: isDropTarget
            ? "2px dashed hsl(var(--success))"
            : isSelected
              ? "2px solid hsl(var(--accent))"
              : isInvalidTarget
                ? "1px solid hsl(var(--danger) / 0.3)"
                : "1px solid hsl(var(--border))",
          background: isDropTarget
            ? "hsl(var(--success-soft))"
            : bg ?? "hsl(var(--card))",
          borderRadius: 10,
          padding: 12,
          width: NODE_WIDTH,
          opacity: isInvalidTarget ? 0.35 : isDragging ? 0.6 : 1,
          boxShadow: isDropTarget
            ? "0 0 0 4px hsl(var(--success) / 0.15)"
            : isSelected
              ? "0 4px 14px hsl(var(--accent) / 0.15)"
              : undefined,
          transition: "background 120ms ease-out, border-color 120ms ease-out",
        },
        sourcePosition: "bottom" as const,
        targetPosition: "top" as const,
      };
    });

    const edges: Edge[] = visibleNos
      .filter((n) => n.id_unidade_pai != null && ids.has(n.id_unidade_pai!))
      .map((n) => ({
        id: `e-${n.id_unidade_pai}-${n.id}`,
        source: String(n.id_unidade_pai),
        target: String(n.id),
        style: { stroke: "hsl(var(--foreground-muted))", strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(var(--foreground-muted))" },
      }));

    return { nodes, edges };
  }, [
    nos,
    collapsed,
    selectedId,
    heatBg,
    onToggle,
    onEdit,
    onAddChild,
    onDelete,
    onReparent,
    hoverTargetId,
    draggedId,
    resetTick,
  ]);

  function handleNodeDragStart(_evt: React.MouseEvent, node: Node) {
    if (!onReparent) return;
    const id = Number(node.id);
    setDraggedId(id);
    draggedDescendants.current = descendantsOf(nos, id);
    dragStartPos.current = { x: node.position.x, y: node.position.y };
    setHoverTargetId(null);
  }

  function handleNodeDrag(_evt: React.MouseEvent, node: Node) {
    if (!onReparent || !flowRef.current) return;
    const inst = flowRef.current;
    const intersecting = inst.getIntersectingNodes(node, false);
    // Filtra self + descendentes
    const candidate = intersecting.find(
      (n) => !draggedDescendants.current.has(Number(n.id)),
    );
    const id = candidate ? Number(candidate.id) : null;
    if (id !== hoverTargetId) setHoverTargetId(id);
  }

  async function handleNodeDragStop(evt: React.MouseEvent, node: Node) {
    if (!onReparent) {
      setDraggedId(null);
      setHoverTargetId(null);
      return;
    }
    const draggedNodeId = Number(node.id);
    const target = hoverTargetId;
    // Detecta drag-to-root: sem alvo + arrastou distância significativa (>120px) +
    // nó não era raiz. Threshold evita "tornar raiz" por arrasto acidental.
    const draggedNo = nos.find((n) => n.id === draggedNodeId);
    const start = dragStartPos.current;
    const distance = start
      ? Math.hypot(node.position.x - start.x, node.position.y - start.y)
      : 0;
    const droppedInEmpty =
      target == null &&
      draggedNo != null &&
      draggedNo.id_unidade_pai != null &&
      distance > 120;
    setDraggedId(null);
    setHoverTargetId(null);
    draggedDescendants.current = new Set();
    dragStartPos.current = null;
    setResetTick((t) => t + 1);

    if (target != null) {
      await onReparent(draggedNodeId, target);
    } else if (droppedInEmpty) {
      await onReparent(draggedNodeId, null);
    }
  }

  return (
    <ReactFlow
      key={resetTick}
      nodes={nodes}
      edges={edges}
      fitView
      fitViewOptions={{ padding: 0.1, maxZoom: 1.2 }}
      nodesDraggable={!!onReparent}
      nodesConnectable={false}
      connectionMode={ConnectionMode.Loose}
      onNodeClick={(_, n) => onSelect(Number(n.id))}
      onPaneClick={() => onSelect(-1)}
      onNodeDragStart={handleNodeDragStart}
      onNodeDrag={handleNodeDrag}
      onNodeDragStop={handleNodeDragStop}
      onInit={(inst) => {
        flowRef.current = inst;
      }}
      proOptions={{ hideAttribution: true }}
      minZoom={0.2}
      maxZoom={2}
    >
      <Background gap={20} size={1} color="hsl(var(--border))" />
      <Controls showInteractive={false} />
      <MiniMap
        pannable
        zoomable
        nodeStrokeWidth={3}
        maskColor="hsl(var(--background) / 0.6)"
        style={{
          backgroundColor: "hsl(var(--surface-2))",
          border: "1px solid hsl(var(--border))",
          borderRadius: 6,
        }}
      />
    </ReactFlow>
  );
}

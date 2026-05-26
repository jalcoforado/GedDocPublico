"use client";

import {
  AlertTriangle,
  ArrowUpFromLine,
  Building2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  GripVertical,
  MoreVertical,
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
  /** Quando ausente, sem perm pra criar (botão +/Nova subordinada escondido). */
  onAddChild?: (parentId: number) => void;
  /** Quando ausente, sem perm pra excluir (botão 🗑 escondido). */
  onDelete?: (no: OrganogramaNo) => void;
  /** Quando ausente, sem perm pra mover (drag/drop desabilitado, botão ↑raiz escondido). */
  onReparent?: (draggedId: number, newParentId: number | null) => Promise<boolean>;
  search?: string;
  /** Heatmap por unidade: id → cor (string CSS), opcional */
  heatBg?: Map<number, string>;
}

interface Node {
  no: OrganogramaNo;
  depth: number;
  childrenIds: number[];
  matchesSearch: boolean;
  /** True quando algum descendente bate na busca (mantém branch visível) */
  hasMatchInSubtree: boolean;
}

interface DragCtx {
  draggedId: number | null;
  hoverId: number | null;
  descendantsOfDragged: Set<number>;
  onDragStart: (id: number) => void;
  onHover: (id: number | null) => void;
  onDragEnd: () => void;
}

function descendantsOfId(nos: OrganogramaNo[], id: number): Set<number> {
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

function buildTree(
  nos: OrganogramaNo[],
  search: string,
): { roots: number[]; byId: Map<number, Node> } {
  const byId = new Map<number, Node>();
  const ids = new Set(nos.map((n) => n.id));
  const norm = search.trim().toLowerCase();

  // Inicializa todos
  for (const no of nos) {
    const text = (
      no.unidade_trabalho +
      " " +
      (no.sigla ?? "")
    ).toLowerCase();
    const matches = norm.length > 0 && text.includes(norm);
    byId.set(no.id, {
      no,
      depth: 0,
      childrenIds: [],
      matchesSearch: matches,
      hasMatchInSubtree: matches,
    });
  }

  // Linka pais ↔ filhos
  const roots: number[] = [];
  for (const no of nos) {
    if (no.id_unidade_pai != null && ids.has(no.id_unidade_pai)) {
      byId.get(no.id_unidade_pai)!.childrenIds.push(no.id);
    } else {
      roots.push(no.id);
    }
  }

  // Ordena filhos alfabeticamente
  for (const node of byId.values()) {
    node.childrenIds.sort((a, b) =>
      byId
        .get(a)!
        .no.unidade_trabalho.localeCompare(byId.get(b)!.no.unidade_trabalho),
    );
  }

  // Calcula depth e propagação de match (bottom-up)
  function visit(id: number, depth: number): boolean {
    const node = byId.get(id)!;
    node.depth = depth;
    let subtreeMatch = node.matchesSearch;
    for (const cid of node.childrenIds) {
      if (visit(cid, depth + 1)) subtreeMatch = true;
    }
    node.hasMatchInSubtree = subtreeMatch;
    return subtreeMatch;
  }
  roots.sort((a, b) =>
    byId
      .get(a)!
      .no.unidade_trabalho.localeCompare(byId.get(b)!.no.unidade_trabalho),
  );
  for (const r of roots) visit(r, 0);

  return { roots, byId };
}

function KpiBadges({ no }: { no: OrganogramaNo }) {
  return (
    <div className="hidden items-center gap-2 text-[10px] text-foreground-muted sm:flex">
      <span className="inline-flex items-center gap-0.5" title="Processos ativos">
        <FileText className="h-3 w-3 text-blue-600" aria-hidden="true" />
        <span className="font-mono tabular-nums font-medium text-foreground">
          {no.processos_ativos}
        </span>
      </span>
      <span className="inline-flex items-center gap-0.5" title="Usuários">
        <Users className="h-3 w-3" aria-hidden="true" />
        <span className="font-mono tabular-nums font-medium text-foreground">
          {no.usuarios}
        </span>
      </span>
      <span
        className={cn(
          "inline-flex items-center gap-0.5",
          no.sla_pendentes > 0 && "text-warning",
        )}
        title="SLA pendentes"
      >
        <AlertTriangle className="h-3 w-3" aria-hidden="true" />
        <span className="font-mono tabular-nums font-medium">
          {no.sla_pendentes}
        </span>
      </span>
      {no.tempo_medio_dias != null && (
        <span
          className="inline-flex items-center gap-0.5"
          title="Tempo médio (30d)"
        >
          <Clock className="h-3 w-3" aria-hidden="true" />
          <span className="font-mono tabular-nums font-medium text-foreground">
            {no.tempo_medio_dias.toFixed(1)}d
          </span>
        </span>
      )}
    </div>
  );
}

function HighlightText({ text, q }: { text: string; q: string }) {
  if (!q.trim()) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx < 0) return <>{text}</>;
  const before = text.slice(0, idx);
  const match = text.slice(idx, idx + q.length);
  const after = text.slice(idx + q.length);
  return (
    <>
      {before}
      <mark className="rounded bg-accent/30 px-0.5 text-foreground">{match}</mark>
      {after}
    </>
  );
}

interface RowExtras {
  node: Node;
  byId: Map<number, Node>;
  dragCtx: DragCtx;
}

function Row({
  node,
  byId,
  collapsed,
  onToggle,
  onSelect,
  selectedId,
  onEdit,
  onAddChild,
  onDelete,
  onReparent,
  search,
  heatBg,
  dragCtx,
}: Props & RowExtras) {
  const { no, depth, childrenIds, hasMatchInSubtree, matchesSearch } = node;
  const isCollapsed = collapsed.has(no.id);
  const hasChildren = childrenIds.length > 0;
  const isSelected = selectedId === no.id;
  const isFiltered = (search ?? "").trim().length > 0;
  const visibleByFilter = !isFiltered || hasMatchInSubtree;

  if (!visibleByFilter) return null;

  const bg = heatBg?.get(no.id);
  const isDragging = dragCtx.draggedId === no.id;
  const isDropTarget = dragCtx.hoverId === no.id && dragCtx.draggedId !== no.id;
  const isInvalidTarget =
    dragCtx.draggedId !== null &&
    dragCtx.descendantsOfDragged.has(no.id) &&
    !isDragging;

  return (
    <>
      <div
        role="treeitem"
        aria-expanded={hasChildren ? !isCollapsed : undefined}
        aria-selected={isSelected}
        draggable={!!onReparent}
        onDragStart={(e) => {
          if (!onReparent) return;
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", String(no.id));
          dragCtx.onDragStart(no.id);
        }}
        onDragEnd={() => dragCtx.onDragEnd()}
        onDragOver={(e) => {
          if (!onReparent || dragCtx.draggedId == null) return;
          if (isInvalidTarget || isDragging) return;
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          if (dragCtx.hoverId !== no.id) dragCtx.onHover(no.id);
        }}
        onDragLeave={() => {
          if (dragCtx.hoverId === no.id) dragCtx.onHover(null);
        }}
        onDrop={async (e) => {
          if (!onReparent) return;
          e.preventDefault();
          e.stopPropagation();
          const draggedId = Number(e.dataTransfer.getData("text/plain"));
          dragCtx.onDragEnd();
          if (Number.isNaN(draggedId) || draggedId === no.id) return;
          await onReparent(draggedId, no.id);
        }}
        onClick={() => onSelect(no.id)}
        className={cn(
          "group flex items-center gap-2 border-b border-border/60 px-2 py-1.5 transition-colors duration-fast",
          "hover:bg-surface-2/60 cursor-pointer",
          isSelected && "bg-brand/5",
          matchesSearch && isFiltered && "ring-1 ring-inset ring-accent/40",
          isDropTarget && "bg-success-soft ring-2 ring-inset ring-success",
          isInvalidTarget && "opacity-40 cursor-not-allowed",
          isDragging && "opacity-50",
        )}
        style={{
          paddingLeft: `${depth * 18 + 8}px`,
          background: isDropTarget ? undefined : bg,
        }}
      >
        {/* Drag handle (visible on hover) */}
        {onReparent && (
          <GripVertical
            className="h-3.5 w-3.5 shrink-0 cursor-grab text-foreground-subtle opacity-0 transition-opacity duration-fast group-hover:opacity-100"
            aria-hidden="true"
          />
        )}

        {/* Chevron expand/collapse */}
        {hasChildren ? (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggle(no.id);
            }}
            className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-foreground-muted hover:bg-muted hover:text-foreground"
            aria-label={isCollapsed ? "Expandir" : "Recolher"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ChevronDown className="h-3.5 w-3.5" aria-hidden="true" />
            )}
          </button>
        ) : (
          <span className="inline-block h-5 w-5 shrink-0" aria-hidden="true" />
        )}

        {/* Ícone + nome + sigla */}
        <Building2
          className="h-4 w-4 shrink-0 text-foreground-muted"
          aria-hidden="true"
        />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">
            <HighlightText text={no.unidade_trabalho} q={search ?? ""} />
            {no.sigla && (
              <span className="ml-2 font-mono text-[10px] uppercase text-foreground-subtle">
                <HighlightText text={no.sigla} q={search ?? ""} />
              </span>
            )}
            {hasChildren && isCollapsed && (
              <span className="ml-2 rounded-full bg-surface-3 px-1.5 py-0.5 text-[10px] font-medium text-foreground-muted">
                +{childrenIds.length}
              </span>
            )}
          </div>
        </div>

        {/* KPI badges (only on hover) */}
        <KpiBadges no={no} />

        {/* Ações inline (visíveis no hover) — escondidas se sem permissão */}
        {(onAddChild || onEdit || onDelete || onReparent) && (
          <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity duration-fast group-hover:opacity-100 focus-within:opacity-100">
            {onAddChild && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAddChild(no.id);
                }}
                title="Adicionar subordinada"
                className="inline-flex h-7 w-7 items-center justify-center rounded text-foreground-muted hover:bg-brand/10 hover:text-brand"
              >
                <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            )}
            {onReparent && no.id_unidade_pai != null && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onReparent(no.id, null);
                }}
                title="Tornar unidade-raiz (sem superior)"
                className="inline-flex h-7 w-7 items-center justify-center rounded text-foreground-muted hover:bg-accent/10 hover:text-accent-dark"
              >
                <ArrowUpFromLine className="h-3.5 w-3.5" aria-hidden="true" />
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
                className="inline-flex h-7 w-7 items-center justify-center rounded text-foreground-muted hover:bg-muted hover:text-foreground"
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
                className="inline-flex h-7 w-7 items-center justify-center rounded text-foreground-muted hover:bg-danger-soft hover:text-danger"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            )}
          </div>
        )}
      </div>

      {/* Filhos */}
      {hasChildren && !isCollapsed && (
        <>
          {childrenIds.map((cid) => (
            <Row
              key={cid}
              node={byId.get(cid)!}
              byId={byId}
              dragCtx={dragCtx}
              nos={[]}
              collapsed={collapsed}
              onToggle={onToggle}
              onSelect={onSelect}
              selectedId={selectedId}
              onEdit={onEdit}
              onAddChild={onAddChild}
              onDelete={onDelete}
              onReparent={onReparent}
              search={search}
              heatBg={heatBg}
            />
          ))}
        </>
      )}
    </>
  );
}

export function OrganogramaListView(props: Props) {
  const { nos, search = "" } = props;
  const { roots, byId } = useMemo(() => buildTree(nos, search), [nos, search]);

  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [hoverId, setHoverId] = useState<number | null>(null);

  const descendantsOfDragged = useMemo(
    () => (draggedId == null ? new Set<number>() : descendantsOfId(nos, draggedId)),
    [nos, draggedId],
  );

  const dragCtx: DragCtx = {
    draggedId,
    hoverId,
    descendantsOfDragged,
    onDragStart: (id) => {
      setDraggedId(id);
      setHoverId(null);
    },
    onHover: (id) => setHoverId(id),
    onDragEnd: () => {
      setDraggedId(null);
      setHoverId(null);
    },
  };

  if (nos.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface-2/30 p-12 text-center text-sm text-foreground-muted">
        Nenhuma unidade cadastrada ainda.
      </div>
    );
  }

  return (
    <div
      role="tree"
      aria-label="Organograma em lista"
      className="overflow-hidden rounded-lg border border-border bg-card"
    >
      {roots.map((rid) => (
        <Row
          key={rid}
          node={byId.get(rid)!}
          byId={byId}
          dragCtx={dragCtx}
          {...props}
        />
      ))}
    </div>
  );
}

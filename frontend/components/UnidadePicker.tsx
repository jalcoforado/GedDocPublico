"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Building2, ChevronDown, X as XIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { organogramaApi, type OrganogramaNo } from "@/lib/api";
import { cn } from "@/lib/utils";

const NODE_WIDTH = 180;
const NODE_HEIGHT = 70;
const COL_GAP = 40;
const ROW_GAP = 50;

function layoutTree(nodes: OrganogramaNo[]): Map<number, { x: number; y: number }> {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const children = new Map<number | null, OrganogramaNo[]>();
  for (const n of nodes) {
    const parent = n.id_unidade_pai;
    if (!children.has(parent)) children.set(parent, []);
    children.get(parent)!.push(n);
  }
  const positions = new Map<number, { x: number; y: number }>();
  let nextX = 0;
  function visit(node: OrganogramaNo, depth: number) {
    const kids = children.get(node.id) ?? [];
    if (kids.length === 0) {
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
  const raizes = nodes.filter(
    (n) => n.id_unidade_pai == null || !byId.has(n.id_unidade_pai),
  );
  for (const r of raizes) visit(r, 0);
  return positions;
}

interface Props {
  value: number | null;
  onChange: (v: number | null) => void;
  /** Label do botão quando sem seleção */
  placeholder?: string;
  /** Disabled state */
  disabled?: boolean;
}

export function UnidadePicker({
  value,
  onChange,
  placeholder = "Escolher unidade",
  disabled,
}: Props) {
  const [open, setOpen] = useState(false);

  const q = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
    enabled: open,
  });

  const selecionada = q.data?.find((u) => u.id === value);
  const nomeAtual = selecionada
    ? selecionada.unidade_trabalho + (selecionada.sigla ? ` (${selecionada.sigla})` : "")
    : null;

  const { nodes, edges } = useMemo(() => {
    const data = q.data ?? [];
    const pos = layoutTree(data);
    const ids = new Set(data.map((n) => n.id));
    const nodes: Node[] = data.map((no) => {
      const p = pos.get(no.id) ?? { x: 0, y: 0 };
      const isSelected = value === no.id;
      return {
        id: String(no.id),
        position: p,
        data: {
          label: (
            <div className="text-left" style={{ width: NODE_WIDTH - 24 }}>
              <div className="flex items-center gap-1.5">
                <Building2
                  className="h-3.5 w-3.5 shrink-0 text-primary"
                  aria-hidden="true"
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-semibold">
                    {no.unidade_trabalho}
                  </div>
                  {no.sigla && (
                    <div className="font-mono text-[9px] uppercase text-muted-foreground">
                      {no.sigla}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ),
        },
        style: {
          border: isSelected ? "2px solid #f59e0b" : "1px solid var(--border, #d4d4d8)",
          background: isSelected ? "#fef3c7" : "var(--card, #fff)",
          borderRadius: 8,
          padding: 8,
          width: NODE_WIDTH,
          cursor: "pointer",
        },
        sourcePosition: "bottom" as const,
        targetPosition: "top" as const,
      };
    });
    const edges: Edge[] = data
      .filter((n) => n.id_unidade_pai != null && ids.has(n.id_unidade_pai!))
      .map((n) => ({
        id: `e-${n.id_unidade_pai}-${n.id}`,
        source: String(n.id_unidade_pai),
        target: String(n.id),
        style: { stroke: "#64748b", strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed },
      }));
    return { nodes, edges };
  }, [q.data, value]);

  function handleNodeClick(_: unknown, node: Node) {
    const id = Number(node.id);
    onChange(id);
    setOpen(false);
  }

  function handleClear() {
    onChange(null);
    setOpen(false);
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled}
        className={cn(
          "flex h-11 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-sm transition-colors",
          "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50",
        )}
      >
        <span
          className={cn(
            "min-w-0 flex-1 truncate text-left",
            nomeAtual ? "text-foreground" : "text-muted-foreground",
          )}
        >
          {nomeAtual ?? placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      </button>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Escolher unidade no organograma"
        size="lg"
        footer={
          <div className="flex w-full justify-between">
            <Button variant="secondary" onClick={handleClear}>
              <XIcon className="mr-1 h-4 w-4" aria-hidden="true" />
              Sem unidade
            </Button>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
          </div>
        }
      >
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Clique numa unidade da árvore para selecioná-la.
          </p>
          <div
            className="rounded-md border border-border bg-muted/30"
            style={{ height: 420 }}
          >
            {q.isLoading && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Carregando…
              </div>
            )}
            {!q.isLoading && (q.data?.length ?? 0) === 0 && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Nenhuma unidade cadastrada.
              </div>
            )}
            {!q.isLoading && (q.data?.length ?? 0) > 0 && (
              <ReactFlow
                nodes={nodes}
                edges={edges}
                fitView
                nodesDraggable={false}
                nodesConnectable={false}
                onNodeClick={handleNodeClick}
                proOptions={{ hideAttribution: true }}
              >
                <Background />
                <Controls showInteractive={false} />
              </ReactFlow>
            )}
          </div>
        </div>
      </Dialog>
    </>
  );
}

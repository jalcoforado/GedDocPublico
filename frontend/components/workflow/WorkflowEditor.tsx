"use client";

import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  useReactFlow,
  ReactFlowProvider,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { HelpCircle, MousePointerClick, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  api,
  type PosicaoXY,
  type WorkflowDSL,
  type WorkflowEstado,
  type WorkflowTransicao,
} from "@/lib/api";

const COL_WIDTH = 220;
const ROW_HEIGHT = 110;
const NODE_PADDING_X = 40;
const NODE_PADDING_Y = 40;

function bfsLayout(
  dsl: WorkflowDSL,
): Map<string, { col: number; row: number }> {
  const adj = new Map<string, string[]>();
  for (const e of dsl.estados) adj.set(e.slug, []);
  for (const t of dsl.transicoes) {
    if (adj.has(t.de)) adj.get(t.de)!.push(t.para);
  }
  const dist = new Map<string, number>();
  const queue: string[] = [dsl.estado_inicial];
  if (adj.has(dsl.estado_inicial)) dist.set(dsl.estado_inicial, 0);
  while (queue.length) {
    const s = queue.shift()!;
    const d = dist.get(s)!;
    for (const next of adj.get(s) ?? []) {
      if (!dist.has(next)) {
        dist.set(next, d + 1);
        queue.push(next);
      }
    }
  }
  const maxDist = Math.max(0, ...Array.from(dist.values()));
  const cols: string[][] = [];
  for (const e of dsl.estados) {
    const c = dist.get(e.slug) ?? maxDist + 1;
    if (!cols[c]) cols[c] = [];
    cols[c].push(e.slug);
  }
  const pos = new Map<string, { col: number; row: number }>();
  cols.forEach((slugs, col) => {
    slugs.forEach((slug, row) => pos.set(slug, { col, row }));
  });
  return pos;
}

function estadosToNodes(
  estados: WorkflowEstado[],
  estadoInicial: string,
  selectedId: string | null,
  layout: Map<string, { col: number; row: number }>,
  unidadeNomes?: Record<number, string>,
): Node[] {
  return estados.map((est) => {
    const a = layout.get(est.slug);
    const x = est.posicao?.x ?? (a ? NODE_PADDING_X + a.col * COL_WIDTH : 100);
    const y = est.posicao?.y ?? (a ? NODE_PADDING_Y + a.row * ROW_HEIGHT : 100);
    const isInicial = est.slug === estadoInicial;
    const isFinal = est.final;
    const isSelected = selectedId === est.slug;

    let border = "1px solid var(--border, #d4d4d8)";
    let background = "var(--card, #fff)";
    if (isSelected) {
      border = "2px solid #f59e0b";
      background = "#fef3c7";
    } else if (isFinal) {
      border = "2px solid #16a34a";
      background = "#dcfce7";
    } else if (isInicial) {
      border = "2px dashed #2563eb";
    }

    return {
      id: est.slug,
      position: { x, y },
      data: {
        label: (
          <div className="text-left">
            <div className="text-sm font-semibold leading-tight">{est.nome}</div>
            <div className="mt-1 font-mono text-[10px] text-muted-foreground">
              {est.slug}
            </div>
            {est.sla_dias != null && (
              <div className="mt-1 text-[10px] text-amber-700">
                SLA: {est.sla_dias}d
              </div>
            )}
            {est.id_unidade_responsavel != null && (
              <div className="mt-1 text-[10px] text-slate-700">
                🏢{" "}
                {unidadeNomes?.[est.id_unidade_responsavel] ??
                  `#${est.id_unidade_responsavel}`}
              </div>
            )}
            {isInicial && (
              <div className="mt-1 text-[10px] font-medium text-blue-700">
                ● inicial
              </div>
            )}
            {isFinal && (
              <div className="mt-1 text-[10px] font-medium text-green-700">
                ● final
              </div>
            )}
          </div>
        ),
      },
      style: {
        border,
        background,
        borderRadius: 8,
        padding: 8,
        width: 170,
        fontSize: 12,
      },
      sourcePosition: "right" as const,
      targetPosition: "left" as const,
    };
  });
}

function transicoesToEdges(
  transicoes: WorkflowTransicao[],
  selectedId: string | null,
): Edge[] {
  return transicoes.map((t, i) => {
    const id = `e-${t.de}-${t.para}-${i}`;
    const isSelected = selectedId === id;
    return {
      id,
      source: t.de,
      target: t.para,
      label: t.label,
      labelStyle: { fontSize: 11 },
      labelBgStyle: { fill: "#fff", fillOpacity: 0.9 },
      labelBgPadding: [4, 2],
      style: {
        stroke: isSelected ? "#f59e0b" : t.condicao ? "#9333ea" : "#64748b",
        strokeWidth: isSelected ? 3 : 1.5,
        strokeDasharray: t.evento !== "manual" ? "4 2" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  });
}

export interface WorkflowEditorSelection {
  type: "estado" | "transicao" | null;
  /** estado slug ou transicao edge id */
  id: string | null;
  transicaoIndex: number | null;
}

interface WorkflowEditorProps {
  dsl: WorkflowDSL;
  onChange: (dsl: WorkflowDSL) => void;
  onSelectionChange: (sel: WorkflowEditorSelection) => void;
  height?: number;
}

function EditorInner({ dsl, onChange, onSelectionChange, height = 540 }: WorkflowEditorProps) {
  const { fitView } = useReactFlow();
  const [selection, setSelection] = useState<WorkflowEditorSelection>({
    type: null,
    id: null,
    transicaoIndex: null,
  });
  // Shift+click connect: 1º clique marca origem, 2º cria edge.
  const [shiftSource, setShiftSource] = useState<string | null>(null);
  const shiftSourceRef = useRef<string | null>(null);
  shiftSourceRef.current = shiftSource;

  const layout = useMemo(() => bfsLayout(dsl), [dsl]);

  // Mapa id→nome de unidade pra renderizar o badge no nodo
  const unidadesQ = useQuery({
    queryKey: ["unidades-trabalho"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const unidadeNomes = useMemo<Record<number, string>>(() => {
    const map: Record<number, string> = {};
    for (const u of unidadesQ.data?.items ?? []) {
      map[u.id] = u.unidade_trabalho;
    }
    return map;
  }, [unidadesQ.data]);

  const baseNodes = useMemo(
    () =>
      estadosToNodes(
        dsl.estados,
        dsl.estado_inicial,
        selection.type === "estado" ? selection.id : null,
        layout,
        unidadeNomes,
      ),
    [dsl.estados, dsl.estado_inicial, selection, layout, unidadeNomes],
  );

  // Aplica className extra no nó de origem do shift+click
  const nodes = useMemo(() => {
    if (!shiftSource) return baseNodes;
    return baseNodes.map((n) =>
      n.id === shiftSource ? { ...n, className: "workflow-shift-source" } : n,
    );
  }, [baseNodes, shiftSource]);
  const edges = useMemo(
    () =>
      transicoesToEdges(
        dsl.transicoes,
        selection.type === "transicao" ? selection.id : null,
      ),
    [dsl.transicoes, selection],
  );

  // Sincroniza seleção pra fora
  useEffect(() => {
    onSelectionChange(selection);
  }, [selection, onSelectionChange]);

  // Notifica posições novas após drag end
  const onNodesChange = useCallback(
    (changes: NodeChange[]) => {
      // Aplica nos current pra extrair as novas positions
      const updated = applyNodeChanges(changes, nodes);

      // Só commitamos quando há mudança de posição (drag) ou seleção
      const posChanges = changes.filter(
        (c) => c.type === "position" && (c as { dragging?: boolean }).dragging === false,
      );
      if (posChanges.length > 0) {
        // Constrói o DSL atualizado preservando ordem
        const novosEstados = dsl.estados.map((est) => {
          const n = updated.find((nn) => nn.id === est.slug);
          if (!n) return est;
          return { ...est, posicao: { x: n.position.x, y: n.position.y } as PosicaoXY };
        });
        onChange({ ...dsl, estados: novosEstados });
      }

      const selChange = changes.find((c) => c.type === "select" && c.selected);
      if (selChange && selChange.type === "select") {
        setSelection({ type: "estado", id: selChange.id, transicaoIndex: null });
      }
    },
    [dsl, nodes, onChange],
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => {
      const selChange = changes.find((c) => c.type === "select" && c.selected);
      if (selChange && selChange.type === "select") {
        const idx = edges.findIndex((e) => e.id === selChange.id);
        setSelection({ type: "transicao", id: selChange.id, transicaoIndex: idx });
      }
      // Remoções de edge tratadas via Backspace handler
      void applyEdgeChanges(changes, edges);
    },
    [edges],
  );

  const createConnection = useCallback(
    (source: string, target: string) => {
      if (!source || !target || source === target) return;
      // Não permite duplicata exata
      const existe = dsl.transicoes.some((t) => t.de === source && t.para === target);
      if (existe) return;
      const nova: WorkflowTransicao = {
        de: source,
        para: target,
        label: `${source}→${target}`,
        descricao: null,
        condicao: null,
        grupos_permitidos: [],
        evento: "manual",
      };
      const novoDsl = { ...dsl, transicoes: [...dsl.transicoes, nova] };
      onChange(novoDsl);
      // Marca a nova transição como selecionada
      const newIdx = novoDsl.transicoes.length - 1;
      const newId = `e-${source}-${target}-${newIdx}`;
      setSelection({ type: "transicao", id: newId, transicaoIndex: newIdx });
      void addEdge;
    },
    [dsl, onChange],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      createConnection(connection.source, connection.target);
    },
    [createConnection],
  );

  // Shift+click handler: marca origem no 1º click, cria edge no 2º
  const onNodeClick = useCallback(
    (event: React.MouseEvent, node: Node) => {
      if (!event.shiftKey) {
        setShiftSource(null);
        return;
      }
      event.preventDefault();
      const src = shiftSourceRef.current;
      if (!src) {
        setShiftSource(node.id);
        return;
      }
      if (src === node.id) {
        setShiftSource(null);
        return;
      }
      createConnection(src, node.id);
      setShiftSource(null);
    },
    [createConnection],
  );

  const onPaneClick = useCallback(() => {
    setSelection({ type: null, id: null, transicaoIndex: null });
    setShiftSource(null);
  }, []);

  // Add estado novo
  const onAddEstado = useCallback(() => {
    const existing = new Set(dsl.estados.map((e) => e.slug));
    let i = 1;
    while (existing.has(`estado_${i}`)) i++;
    const slug = `estado_${i}`;
    const novo: WorkflowEstado = {
      slug,
      nome: `Estado ${i}`,
      descricao: null,
      final: false,
      sla_dias: null,
      posicao: { x: 80 + 30 * dsl.estados.length, y: 60 + 30 * dsl.estados.length },
    };
    onChange({ ...dsl, estados: [...dsl.estados, novo] });
    setSelection({ type: "estado", id: slug, transicaoIndex: null });
  }, [dsl, onChange]);

  // Delete via Backspace
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key !== "Delete" && e.key !== "Backspace") return;
      const target = e.target as HTMLElement | null;
      // Não deleta se foco está em input/textarea/select
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      )
        return;
      if (selection.type === "estado" && selection.id) {
        const slug = selection.id;
        if (slug === dsl.estado_inicial) return; // não deleta inicial
        const novosEstados = dsl.estados.filter((e) => e.slug !== slug);
        const novasTransicoes = dsl.transicoes.filter(
          (t) => t.de !== slug && t.para !== slug,
        );
        onChange({ ...dsl, estados: novosEstados, transicoes: novasTransicoes });
        setSelection({ type: null, id: null, transicaoIndex: null });
      } else if (selection.type === "transicao" && selection.transicaoIndex !== null) {
        const novas = dsl.transicoes.filter((_, i) => i !== selection.transicaoIndex);
        onChange({ ...dsl, transicoes: novas });
        setSelection({ type: null, id: null, transicaoIndex: null });
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selection, dsl, onChange]);

  const onDeleteSelected = useCallback(() => {
    if (selection.type === "estado" && selection.id) {
      const slug = selection.id;
      if (slug === dsl.estado_inicial) return;
      const novosEstados = dsl.estados.filter((e) => e.slug !== slug);
      const novasTransicoes = dsl.transicoes.filter(
        (t) => t.de !== slug && t.para !== slug,
      );
      onChange({ ...dsl, estados: novosEstados, transicoes: novasTransicoes });
      setSelection({ type: null, id: null, transicaoIndex: null });
    } else if (selection.type === "transicao" && selection.transicaoIndex !== null) {
      const novas = dsl.transicoes.filter((_, i) => i !== selection.transicaoIndex);
      onChange({ ...dsl, transicoes: novas });
      setSelection({ type: null, id: null, transicaoIndex: null });
    }
  }, [selection, dsl, onChange]);

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-2 py-1.5">
        <Button size="sm" variant="secondary" onClick={onAddEstado}>
          <Plus className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
          Estado
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={onDeleteSelected}
          disabled={
            selection.type === null ||
            (selection.type === "estado" && selection.id === dsl.estado_inicial)
          }
          title={
            selection.type === "estado" && selection.id === dsl.estado_inicial
              ? "Não é possível excluir o estado inicial"
              : "Excluir selecionado"
          }
        >
          <Trash2 className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
          Excluir
        </Button>
        <Button size="sm" variant="secondary" onClick={() => fitView({ padding: 0.2 })}>
          Centralizar
        </Button>
        {shiftSource && (
          <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            <MousePointerClick className="mr-1 inline-block h-3 w-3" aria-hidden="true" />
            Clique no destino (com Shift) para criar transição a partir de "{shiftSource}"
          </span>
        )}
        <details className="ml-auto text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            <HelpCircle className="mr-1 inline-block h-3.5 w-3.5" aria-hidden="true" />
            Como usar
          </summary>
          <div className="absolute right-2 top-10 z-10 w-80 rounded-md border border-border bg-card p-3 text-xs shadow-lg">
            <ul className="list-disc space-y-1 pl-4">
              <li>
                <strong>Criar transição (mouse):</strong> passe o cursor na borda
                direita de um nodo até aparecer a bolinha azul, arraste até a borda
                esquerda do outro nodo.
              </li>
              <li>
                <strong>Criar transição (teclado):</strong> segure{" "}
                <kbd className="rounded bg-muted px-1">Shift</kbd> e clique no nodo
                de origem; segure <kbd className="rounded bg-muted px-1">Shift</kbd>{" "}
                e clique no destino.
              </li>
              <li>
                <strong>Editar:</strong> clique num nodo ou seta — painel direito
                abre.
              </li>
              <li>
                <strong>Excluir:</strong> selecione e tecle{" "}
                <kbd className="rounded bg-muted px-1">Backspace</kbd> (estado
                inicial não pode ser excluído).
              </li>
              <li>
                <strong>Reposicionar:</strong> arraste o nodo — posição é salva no
                DSL.
              </li>
            </ul>
          </div>
        </details>
      </div>
      <div style={{ height, width: "100%" }} className="workflow-editor bg-muted/20">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
    </div>
  );
}

export function WorkflowEditor(props: WorkflowEditorProps) {
  return (
    <ReactFlowProvider>
      <EditorInner {...props} />
    </ReactFlowProvider>
  );
}

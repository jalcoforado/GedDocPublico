"use client";

import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, type WorkflowDSL } from "@/lib/api";

interface WorkflowDiagramProps {
  dsl: WorkflowDSL;
  estadoAtual?: string;
  height?: number;
  /** Mapa id_unidade → nome para mostrar no badge do nodo. Sem o mapa,
   * cai em "🏢 #id". */
  unidadeNomes?: Record<number, string>;
}

/** Layout em colunas via BFS a partir do estado_inicial. Estados não
 * alcançáveis vão pra última coluna. Simples mas determinístico. */
function layoutColumns(dsl: WorkflowDSL): Map<string, { col: number; row: number }> {
  const adj = new Map<string, string[]>();
  for (const e of dsl.estados) adj.set(e.slug, []);
  for (const t of dsl.transicoes) {
    if (adj.has(t.de)) adj.get(t.de)!.push(t.para);
  }

  const dist = new Map<string, number>();
  const queue: string[] = [dsl.estado_inicial];
  dist.set(dsl.estado_inicial, 0);
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
  const fallback = maxDist + 1;
  const cols: string[][] = [];
  for (const e of dsl.estados) {
    const c = dist.get(e.slug) ?? fallback;
    if (!cols[c]) cols[c] = [];
    cols[c].push(e.slug);
  }

  const pos = new Map<string, { col: number; row: number }>();
  cols.forEach((slugs, col) => {
    slugs.forEach((slug, row) => pos.set(slug, { col, row }));
  });
  return pos;
}

const COL_WIDTH = 220;
const ROW_HEIGHT = 110;
const NODE_PADDING_X = 40;
const NODE_PADDING_Y = 40;

export function WorkflowDiagram({
  dsl,
  estadoAtual,
  height = 480,
  unidadeNomes,
}: WorkflowDiagramProps) {
  // Carrega unidades se o caller não passar o mapa. Não bloqueia render —
  // antes de chegar, mostra "🏢 #id".
  const unidadesQ = useQuery({
    queryKey: ["unidades-trabalho"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
    enabled: !unidadeNomes,
  });
  const effNomes = useMemo<Record<number, string>>(() => {
    if (unidadeNomes) return unidadeNomes;
    const map: Record<number, string> = {};
    for (const u of unidadesQ.data?.items ?? []) {
      map[u.id] = u.unidade_trabalho;
    }
    return map;
  }, [unidadeNomes, unidadesQ.data]);

  const { nodes, edges } = useMemo(() => {
    const auto = layoutColumns(dsl);

    const nodes: Node[] = dsl.estados.map((est) => {
      // Posição explícita no DSL ganha do layout BFS.
      const explicit = est.posicao;
      const a = auto.get(est.slug)!;
      const x = explicit?.x ?? NODE_PADDING_X + a.col * COL_WIDTH;
      const y = explicit?.y ?? NODE_PADDING_Y + a.row * ROW_HEIGHT;
      const isAtual = estadoAtual === est.slug;
      const isInicial = est.slug === dsl.estado_inicial;
      const isFinal = est.final;

      // Estilos por papel + estado atual
      let border = "1px solid var(--border, #d4d4d8)";
      let background = "var(--card, #fff)";
      if (isAtual) {
        border = "2px solid var(--primary, #2563eb)";
        background = "var(--primary-soft, #dbeafe)";
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
                  {effNomes[est.id_unidade_responsavel] ??
                    `#${est.id_unidade_responsavel}`}
                </div>
              )}
              {isAtual && (
                <div className="mt-1 text-[10px] font-medium text-primary">
                  ● ATUAL
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

    const edges: Edge[] = dsl.transicoes.map((t, i) => ({
      id: `e${i}`,
      source: t.de,
      target: t.para,
      label: t.label,
      labelStyle: { fontSize: 11 },
      labelBgStyle: { fill: "#fff", fillOpacity: 0.9 },
      labelBgPadding: [4, 2],
      style: {
        stroke: t.condicao ? "#9333ea" : "#64748b",
        strokeDasharray: t.evento !== "manual" ? "4 2" : undefined,
      },
      markerEnd: { type: MarkerType.ArrowClosed },
      data: { condicao: t.condicao, evento: t.evento },
    }));

    return { nodes, edges };
  }, [dsl, estadoAtual, effNomes]);

  return (
    <div style={{ height, width: "100%" }} className="rounded-md border bg-muted/30">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}

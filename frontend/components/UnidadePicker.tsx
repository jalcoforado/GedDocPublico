"use client";

import { Carregando } from "@/components/ui/carregando";

import { useQuery } from "@tanstack/react-query";
import {
  Background,
  Controls,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Building2, Network, X as XIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Dialog } from "@/components/ui/dialog";
import { COR_WF, TEMA_XYFLOW, estiloDoNo } from "@/components/workflow/cores";
import { organogramaApi, type OrganogramaNo } from "@/lib/api";

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
  /** Texto do campo quando sem seleção */
  placeholder?: string;
  /** Disabled state */
  disabled?: boolean;
  id?: string;
}

/** Busca sem acento e sem caixa: "saude" acha "Secretaria de Saúde". */
function normalizar(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Caminho dos ancestrais, da raiz até o pai: "PREF › Secretaria de Saúde". */
function caminho(no: OrganogramaNo, porId: Map<number, OrganogramaNo>): string {
  const partes: string[] = [];
  const vistos = new Set<number>();
  let pai = no.id_unidade_pai != null ? porId.get(no.id_unidade_pai) : undefined;
  while (pai && !vistos.has(pai.id)) {
    vistos.add(pai.id);
    partes.unshift(pai.sigla || pai.unidade_trabalho);
    pai = pai.id_unidade_pai != null ? porId.get(pai.id_unidade_pai) : undefined;
  }
  return partes.join(" › ");
}

/**
 * Escolha de unidade: um campo com busca (parte do nome ou a sigla, sem
 * acento), e cada opção mostra onde a unidade fica na hierarquia. O
 * organograma desenhado continua a um clique ("Ver no organograma"), para
 * quem prefere achar pela árvore.
 *
 * Antes o campo era só um botão que abria o diagrama — sem busca e sem
 * teclado, numa prefeitura com dezenas de unidades (pedido do Jorge,
 * 2026-11-06).
 */
export function UnidadePicker({
  value,
  onChange,
  placeholder = "Escolher unidade",
  disabled,
  id,
}: Props) {
  const [organograma, setOrganograma] = useState(false);

  const q = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
    staleTime: 5 * 60_000,
  });

  const opcoes = useMemo<ComboboxOption<OrganogramaNo>[]>(() => {
    const dados = q.data ?? [];
    const porId = new Map(dados.map((n) => [n.id, n]));
    return dados
      .map((no) => ({
        value: no.id,
        label: no.unidade_trabalho + (no.sigla ? ` (${no.sigla})` : ""),
        hint: caminho(no, porId) || undefined,
        data: no,
      }))
      .sort(
        (a, b) =>
          (a.hint ?? "").localeCompare(b.hint ?? "", "pt-BR") ||
          a.label.localeCompare(b.label, "pt-BR"),
      );
  }, [q.data]);

  return (
    <>
      <Combobox
        id={id}
        options={opcoes}
        value={value}
        onChange={(v) => onChange(v == null ? null : Number(v))}
        placeholder={placeholder}
        searchPlaceholder="Buscar pelo nome ou pela sigla…"
        emptyText="Nenhuma unidade com esse nome."
        loading={q.isLoading}
        disabled={disabled}
        clearable
        filter={(o, busca) => normalizar(`${o.label} ${o.hint ?? ""}`).includes(normalizar(busca))}
        footer={
          <button
            type="button"
            onClick={() => setOrganograma(true)}
            className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-xs font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
          >
            <Network className="h-3.5 w-3.5" aria-hidden="true" />
            Ver no organograma
          </button>
        }
      />

      <OrganogramaDialog
        aberto={organograma}
        onFechar={() => setOrganograma(false)}
        dados={q.data ?? []}
        carregando={q.isLoading}
        value={value}
        onEscolher={(v) => {
          onChange(v);
          setOrganograma(false);
        }}
      />
    </>
  );
}

/** O organograma desenhado (React Flow): clicar num nó escolhe a unidade. */
function OrganogramaDialog({
  aberto,
  onFechar,
  dados,
  carregando,
  value,
  onEscolher,
}: {
  aberto: boolean;
  onFechar: () => void;
  dados: OrganogramaNo[];
  carregando: boolean;
  value: number | null;
  onEscolher: (v: number | null) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const pos = layoutTree(dados);
    const ids = new Set(dados.map((n) => n.id));
    const nodes: Node[] = dados.map((no) => {
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
          ...estiloDoNo({ selecionado: isSelected }),
          color: COR_WF.texto,
          borderRadius: 8,
          padding: 8,
          width: NODE_WIDTH,
          cursor: "pointer",
        },
        sourcePosition: Position.Bottom,
        targetPosition: Position.Top,
      };
    });
    const edges: Edge[] = dados
      .filter((n) => n.id_unidade_pai != null && ids.has(n.id_unidade_pai!))
      .map((n) => ({
        id: `e-${n.id_unidade_pai}-${n.id}`,
        source: String(n.id_unidade_pai),
        target: String(n.id),
        style: { stroke: COR_WF.transicao, strokeWidth: 1.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: COR_WF.transicao },
      }));
    return { nodes, edges };
  }, [dados, value]);

  return (
    <Dialog
      open={aberto}
      onClose={onFechar}
      title="Escolher unidade no organograma"
      size="lg"
      footer={
        <div className="flex w-full justify-between">
          <Button variant="secondary" onClick={() => onEscolher(null)}>
            <XIcon className="mr-1 h-4 w-4" aria-hidden="true" />
            Sem unidade
          </Button>
          <Button variant="ghost" onClick={onFechar}>
            Cancelar
          </Button>
        </div>
      }
    >
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          Clique numa unidade da árvore para selecioná-la.
        </p>
        <div className="rounded-md border border-border bg-muted/30" style={{ height: 420 }}>
          {carregando && (
            <Carregando className="flex h-full items-center justify-center text-sm text-muted-foreground" />
          )}
          {!carregando && dados.length === 0 && (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Nenhuma unidade cadastrada.
            </div>
          )}
          {!carregando && dados.length > 0 && (
            <ReactFlow
              style={TEMA_XYFLOW}
              nodes={nodes}
              edges={edges}
              fitView
              nodesDraggable={false}
              nodesConnectable={false}
              onNodeClick={(_, node) => onEscolher(Number(node.id))}
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          )}
        </div>
      </div>
    </Dialog>
  );
}

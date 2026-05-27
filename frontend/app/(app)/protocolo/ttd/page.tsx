"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  CalendarClock,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import {
  ccdApi,
  protocoloApi,
  ttdApi,
  type CcdClasseTreeNode,
  type DestinoFinal,
  type TtdRegraCreatePayload,
  type TtdRegraDetail,
  type TtdRegraUpdatePayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface FlatClasse {
  id: number;
  codigo: string;
  nome: string;
}

function flattenTree(nodes: CcdClasseTreeNode[]): FlatClasse[] {
  const out: FlatClasse[] = [];
  function walk(ns: CcdClasseTreeNode[], depthCodigo = "") {
    for (const n of ns) {
      out.push({
        id: n.id,
        codigo: n.codigo,
        nome: depthCodigo + n.nome,
      });
      if (n.filhos.length) walk(n.filhos, depthCodigo);
    }
  }
  walk(nodes);
  return out;
}

export default function TtdPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();
  const canInsert = can("catalogo", "inserir");
  const canUpdate = can("catalogo", "atualizar");
  const canDelete = can("catalogo", "excluir");

  const [filtroClasse, setFiltroClasse] = useState<number | null>(null);
  const [editing, setEditing] = useState<TtdRegraDetail | null>(null);
  const [creating, setCreating] = useState(false);

  const ttdQ = useQuery({
    queryKey: ["ttd-regras", { id_ccd_classe: filtroClasse }],
    queryFn: () => ttdApi.list(filtroClasse ?? undefined),
  });
  const classesQ = useQuery({
    queryKey: ["ccd-tree"],
    queryFn: () => ccdApi.tree(),
  });
  const especiesQ = useQuery({
    queryKey: ["especies-documentais"],
    queryFn: () => protocoloApi.listEspecies(false),
  });

  const flatClasses = useMemo<FlatClasse[]>(
    () => (classesQ.data ? flattenTree(classesQ.data) : []),
    [classesQ.data],
  );

  const classeOptions = useMemo<ComboboxOption[]>(
    () => flatClasses.map((c) => ({ value: c.id, label: `${c.codigo} — ${c.nome}` })),
    [flatClasses],
  );

  const deleteM = useMutation({
    mutationFn: (id: number) => ttdApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ttd-regras"] });
      toast.success("Regra excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onDelete(r: TtdRegraDetail) {
    const ok = await confirm({
      title: "Excluir regra TTD",
      message: `Excluir regra da classe ${r.classe_codigo}?`,
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) deleteM.mutate(r.id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={CalendarClock}
        title="TTD — Tabela de Temporalidade Documental"
        description="Para cada classe CCD (opcionalmente combinada com espécie), define anos na fase corrente, intermediária e destino final (eliminação ou guarda permanente)."
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex w-full max-w-md flex-1 items-center gap-2">
          <Label className="shrink-0 text-xs text-foreground-muted">
            Filtrar classe:
          </Label>
          <Combobox
            options={classeOptions}
            value={filtroClasse}
            onChange={(v) => setFiltroClasse(typeof v === "number" ? v : null)}
            placeholder="Todas as classes"
          />
        </div>
        {canInsert && (
          <Button
            size="sm"
            onClick={() => {
              setEditing(null);
              setCreating(true);
            }}
          >
            <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
            Nova regra
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <section className="overflow-hidden rounded-xl border border-border bg-card shadow-xs">
          {ttdQ.isLoading && (
            <div className="p-6 text-sm text-foreground-muted">
              <Loader2 className="mr-1 inline h-4 w-4 animate-spin" /> Carregando…
            </div>
          )}
          {!ttdQ.isLoading && (ttdQ.data ?? []).length === 0 && (
            <p className="p-6 text-sm text-foreground-muted">
              Nenhuma regra cadastrada para o filtro.
            </p>
          )}
          {(ttdQ.data ?? []).length > 0 && (
            <table className="w-full text-sm">
              <thead className="bg-surface-2 text-left text-xs font-semibold uppercase tracking-wider text-foreground-muted">
                <tr>
                  <th className="px-3 py-2">Classe</th>
                  <th className="px-3 py-2">Espécie</th>
                  <th className="px-3 py-2 text-center">Corrente</th>
                  <th className="px-3 py-2 text-center">Intermed.</th>
                  <th className="px-3 py-2">Destino</th>
                  <th className="px-3 py-2 w-20"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(ttdQ.data ?? []).map((r) => (
                  <tr key={r.id} className="group hover:bg-surface-2">
                    <td className="px-3 py-2">
                      <span className="font-mono text-xs text-foreground-muted">
                        {r.classe_codigo}
                      </span>{" "}
                      {r.classe_nome}
                    </td>
                    <td className="px-3 py-2 text-foreground-muted">
                      {r.especie_nome ?? <em>(todas)</em>}
                    </td>
                    <td className="px-3 py-2 text-center font-mono">
                      {r.anos_corrente}a
                    </td>
                    <td className="px-3 py-2 text-center font-mono">
                      {r.anos_intermediario}a
                    </td>
                    <td className="px-3 py-2">
                      {r.destino_final === "GUARDA_PERMANENTE" ? (
                        <Badge intent="success" icon={Archive}>
                          Guarda permanente
                        </Badge>
                      ) : (
                        <Badge intent="warning">Eliminação</Badge>
                      )}
                      {r.observacao && (
                        <p className="mt-0.5 text-[10px] text-foreground-muted">
                          {r.observacao}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex opacity-0 transition-opacity group-hover:opacity-100">
                        {canUpdate && (
                          <button
                            onClick={() => {
                              setCreating(false);
                              setEditing(r);
                            }}
                            className="rounded p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
                            title="Editar"
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </button>
                        )}
                        {canDelete && (
                          <button
                            onClick={() => onDelete(r)}
                            className="rounded p-1 text-foreground-muted hover:bg-danger/10 hover:text-danger"
                            title="Excluir"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <aside className="space-y-4">
          {(editing || creating) && (
            <TtdForm
              key={editing?.id ?? "new"}
              regra={editing}
              classeOptions={classeOptions}
              especieOptions={(especiesQ.data ?? []).map((e) => ({
                value: e.id,
                label: e.nome,
              }))}
              onClose={() => {
                setEditing(null);
                setCreating(false);
              }}
            />
          )}
          {!editing && !creating && (
            <div className="rounded-xl border border-dashed border-border bg-surface-1 p-4 text-xs text-foreground-muted">
              Hover numa linha pra editar/excluir, ou clique em &ldquo;Nova
              regra&rdquo; pra criar.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function TtdForm({
  regra,
  classeOptions,
  especieOptions,
  onClose,
}: {
  regra: TtdRegraDetail | null;
  classeOptions: ComboboxOption[];
  especieOptions: ComboboxOption[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const isEditing = regra !== null;

  const [idClasse, setIdClasse] = useState<number | null>(regra?.id_ccd_classe ?? null);
  const [idEspecie, setIdEspecie] = useState<number | null>(
    regra?.id_especie_documental ?? null,
  );
  const [anosCorrente, setAnosCorrente] = useState(regra?.anos_corrente ?? 0);
  const [anosInter, setAnosInter] = useState(regra?.anos_intermediario ?? 0);
  const [destino, setDestino] = useState<DestinoFinal>(
    regra?.destino_final ?? "ELIMINACAO",
  );
  const [observacao, setObservacao] = useState(regra?.observacao ?? "");

  const createM = useMutation({
    mutationFn: (payload: TtdRegraCreatePayload) => ttdApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ttd-regras"] });
      toast.success("Regra criada.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const updateM = useMutation({
    mutationFn: (payload: TtdRegraUpdatePayload) =>
      ttdApi.update(regra!.id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ttd-regras"] });
      toast.success("Regra atualizada.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (idClasse == null) {
      toast.error("Escolha uma classe CCD.");
      return;
    }
    if (isEditing) {
      updateM.mutate({
        id_especie_documental: idEspecie,
        anos_corrente: anosCorrente,
        anos_intermediario: anosInter,
        destino_final: destino,
        observacao: observacao || null,
      });
    } else {
      createM.mutate({
        id_ccd_classe: idClasse,
        id_especie_documental: idEspecie,
        anos_corrente: anosCorrente,
        anos_intermediario: anosInter,
        destino_final: destino,
        observacao: observacao || null,
      });
    }
  }

  const pending = createM.isPending || updateM.isPending;

  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-xs"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          {isEditing ? "Editar regra TTD" : "Nova regra TTD"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="rounded p-1 text-foreground-muted hover:bg-surface-2"
          aria-label="Fechar"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div>
        <Label>
          Classe CCD <span className="text-danger">*</span>
        </Label>
        <Combobox
          options={classeOptions}
          value={idClasse}
          onChange={(v) => setIdClasse(typeof v === "number" ? v : null)}
          placeholder="Selecione…"
          disabled={isEditing}
        />
        {isEditing && (
          <p className="mt-1 text-xs text-foreground-muted">
            A classe não muda após criação — exclua e crie nova se precisar.
          </p>
        )}
      </div>

      <div>
        <Label>
          Espécie documental{" "}
          <span className="text-xs text-foreground-muted">
            (vazio = aplica a todas)
          </span>
        </Label>
        <Combobox
          options={especieOptions}
          value={idEspecie}
          onChange={(v) => setIdEspecie(typeof v === "number" ? v : null)}
          placeholder="Todas as espécies"
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="ttd-corrente">Anos na fase corrente</Label>
          <Input
            id="ttd-corrente"
            type="number"
            min={0}
            max={999}
            value={anosCorrente}
            onChange={(e) => setAnosCorrente(Number(e.target.value) || 0)}
          />
        </div>
        <div>
          <Label htmlFor="ttd-inter">Anos na fase intermediária</Label>
          <Input
            id="ttd-inter"
            type="number"
            min={0}
            max={999}
            value={anosInter}
            onChange={(e) => setAnosInter(Number(e.target.value) || 0)}
          />
        </div>
      </div>

      <div>
        <Label htmlFor="ttd-destino">
          Destino final <span className="text-danger">*</span>
        </Label>
        <Select
          id="ttd-destino"
          value={destino}
          onChange={(e) => setDestino(e.target.value as DestinoFinal)}
        >
          <option value="ELIMINACAO">Eliminação</option>
          <option value="GUARDA_PERMANENTE">Guarda permanente</option>
        </Select>
      </div>

      <div>
        <Label htmlFor="ttd-obs">Observação (opcional)</Label>
        <Textarea
          id="ttd-obs"
          value={observacao}
          onChange={(e) => setObservacao(e.target.value)}
          rows={2}
          maxLength={1000}
          placeholder="Ex: 100 anos previdência social"
        />
      </div>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" disabled={pending}>
          {pending && <Loader2 className="mr-1 h-4 w-4 animate-spin" />}
          {isEditing ? "Salvar" : "Criar"}
        </Button>
      </div>
    </form>
  );
}

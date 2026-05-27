"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  FolderTree,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { useConfirm } from "@/components/ui/confirm";
import {
  ccdApi,
  type CcdClasse,
  type CcdClasseCreatePayload,
  type CcdClasseTreeNode,
  type CcdClasseUpdatePayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface FlatClass {
  id: number;
  codigo: string;
  nome: string;
}

function flatten(nodes: CcdClasseTreeNode[]): FlatClass[] {
  const out: FlatClass[] = [];
  function walk(ns: CcdClasseTreeNode[]) {
    for (const n of ns) {
      out.push({ id: n.id, codigo: n.codigo, nome: n.nome });
      if (n.filhos.length) walk(n.filhos);
    }
  }
  walk(nodes);
  return out;
}

export default function CcdPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();
  const canInsert = can("catalogo", "inserir");
  const canUpdate = can("catalogo", "atualizar");
  const canDelete = can("catalogo", "excluir");

  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const [editing, setEditing] = useState<CcdClasse | null>(null);
  const [creatingParent, setCreatingParent] = useState<number | null | undefined>(
    undefined,
  );

  const treeQ = useQuery({
    queryKey: ["ccd-tree"],
    queryFn: () => ccdApi.tree(),
  });

  const flatPlaceholder = useMemo<FlatClass[]>(
    () => (treeQ.data ? flatten(treeQ.data) : []),
    [treeQ.data],
  );

  function toggle(id: number) {
    const next = new Set(expanded);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setExpanded(next);
  }

  function expandAll() {
    if (!treeQ.data) return;
    const all = new Set<number>();
    function walk(ns: CcdClasseTreeNode[]) {
      for (const n of ns) {
        if (n.filhos.length) {
          all.add(n.id);
          walk(n.filhos);
        }
      }
    }
    walk(treeQ.data);
    setExpanded(all);
  }

  function collapseAll() {
    setExpanded(new Set());
  }

  const deleteM = useMutation({
    mutationFn: (id: number) => ccdApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ccd-tree"] });
      toast.success("Classe excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onDelete(c: { id: number; codigo: string; nome: string }) {
    const ok = await confirm({
      title: "Excluir classe CCD",
      message: `Excluir ${c.codigo} ${c.nome}? Filhos precisam ser removidos antes.`,
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) deleteM.mutate(c.id);
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FolderTree}
        title="CCD — Classificação Documental"
        description="Taxonomia hierárquica de classes documentais. Cada protocolo recebe uma classe que determina o prazo de guarda via tabela de temporalidade (TTD)."
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" onClick={expandAll}>
            Expandir tudo
          </Button>
          <Button size="sm" variant="secondary" onClick={collapseAll}>
            Recolher
          </Button>
        </div>
        {canInsert && (
          <Button
            size="sm"
            onClick={() => {
              setEditing(null);
              setCreatingParent(null);
            }}
          >
            <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
            Nova classe raiz
          </Button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
        <section className="rounded-xl border border-border bg-card shadow-xs">
          {treeQ.isLoading && (
            <div className="p-6 text-sm text-foreground-muted">
              <Loader2 className="mr-1 inline h-4 w-4 animate-spin" />
              Carregando árvore CCD…
            </div>
          )}
          {!treeQ.isLoading && treeQ.data && treeQ.data.length === 0 && (
            <p className="p-6 text-sm text-foreground-muted">
              Nenhuma classe cadastrada.
            </p>
          )}
          {treeQ.data && treeQ.data.length > 0 && (
            <ul className="divide-y divide-border">
              {treeQ.data.map((n) => (
                <TreeRow
                  key={n.id}
                  node={n}
                  depth={0}
                  expanded={expanded}
                  toggle={toggle}
                  onEdit={
                    canUpdate
                      ? (c) => {
                          setCreatingParent(undefined);
                          setEditing(c);
                        }
                      : undefined
                  }
                  onAddChild={
                    canInsert
                      ? (id) => {
                          setEditing(null);
                          setCreatingParent(id);
                        }
                      : undefined
                  }
                  onDelete={canDelete ? onDelete : undefined}
                />
              ))}
            </ul>
          )}
        </section>

        <aside className="space-y-4">
          {(editing || creatingParent !== undefined) && (
            <ClasseForm
              key={editing?.id ?? `new-${creatingParent ?? "root"}`}
              classe={editing}
              parentId={creatingParent ?? null}
              allClasses={flatPlaceholder}
              onClose={() => {
                setEditing(null);
                setCreatingParent(undefined);
              }}
            />
          )}
          {!editing && creatingParent === undefined && (
            <div className="rounded-xl border border-dashed border-border bg-surface-1 p-4 text-xs text-foreground-muted">
              Clique numa classe pra editar, ou em &ldquo;Nova classe raiz&rdquo;
              pra criar. Use o + ao lado da linha pra criar subclasse.
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function TreeRow({
  node,
  depth,
  expanded,
  toggle,
  onEdit,
  onAddChild,
  onDelete,
}: {
  node: CcdClasseTreeNode;
  depth: number;
  expanded: Set<number>;
  toggle: (id: number) => void;
  onEdit?: (c: CcdClasse) => void;
  onAddChild?: (parentId: number) => void;
  onDelete?: (c: CcdClasse) => void;
}) {
  const hasChildren = node.filhos.length > 0;
  const isOpen = expanded.has(node.id);
  const classeForCallback: CcdClasse = {
    id: node.id,
    codigo: node.codigo,
    nome: node.nome,
    descricao: node.descricao,
    id_classe_pai: null,
    palavras_chave: node.palavras_chave,
    ativo: node.ativo,
  };

  return (
    <li>
      <div
        className="group flex items-center gap-2 px-3 py-2 hover:bg-surface-2"
        style={{ paddingLeft: `${depth * 1.25 + 0.75}rem` }}
      >
        <button
          type="button"
          onClick={() => hasChildren && toggle(node.id)}
          className={cn(
            "inline-flex h-5 w-5 shrink-0 items-center justify-center rounded",
            hasChildren ? "hover:bg-surface-3" : "invisible",
          )}
          aria-label={isOpen ? "Recolher" : "Expandir"}
        >
          {hasChildren && (isOpen ? (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          ))}
        </button>
        <span className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-xs text-foreground-muted">
          {node.codigo}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm">{node.nome}</span>
        {node.palavras_chave && (
          <span
            className="hidden truncate text-[10px] text-foreground-muted md:inline-block md:max-w-[200px]"
            title={node.palavras_chave}
          >
            kw: {node.palavras_chave}
          </span>
        )}
        <div className="flex shrink-0 opacity-0 transition-opacity group-hover:opacity-100">
          {onAddChild && (
            <button
              type="button"
              onClick={() => onAddChild(node.id)}
              className="rounded p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
              title="Adicionar subclasse"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
          {onEdit && (
            <button
              type="button"
              onClick={() => onEdit(classeForCallback)}
              className="rounded p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
              title="Editar"
            >
              <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(classeForCallback)}
              className="rounded p-1 text-foreground-muted hover:bg-danger/10 hover:text-danger"
              title="Excluir"
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
      {hasChildren && isOpen && (
        <ul className="divide-y divide-border">
          {node.filhos.map((c) => (
            <TreeRow
              key={c.id}
              node={c}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              onEdit={onEdit}
              onAddChild={onAddChild}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function ClasseForm({
  classe,
  parentId,
  allClasses,
  onClose,
}: {
  classe: CcdClasse | null;
  parentId: number | null;
  allClasses: FlatClass[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const isEditing = classe !== null;
  const [codigo, setCodigo] = useState(classe?.codigo ?? "");
  const [nome, setNome] = useState(classe?.nome ?? "");
  const [descricao, setDescricao] = useState(classe?.descricao ?? "");
  const [palavrasChave, setPalavrasChave] = useState(classe?.palavras_chave ?? "");

  const createM = useMutation({
    mutationFn: (payload: CcdClasseCreatePayload) => ccdApi.create(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ccd-tree"] });
      toast.success("Classe criada.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const updateM = useMutation({
    mutationFn: (payload: CcdClasseUpdatePayload) =>
      ccdApi.update(classe!.id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ccd-tree"] });
      toast.success("Classe atualizada.");
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!codigo.trim() || !nome.trim()) {
      toast.error("Código e nome são obrigatórios.");
      return;
    }
    if (isEditing) {
      updateM.mutate({
        codigo,
        nome,
        descricao: descricao || null,
        palavras_chave: palavrasChave || null,
      });
    } else {
      createM.mutate({
        codigo,
        nome,
        descricao: descricao || null,
        id_classe_pai: parentId,
        palavras_chave: palavrasChave || null,
      });
    }
  }

  const parentLabel = parentId
    ? allClasses.find((c) => c.id === parentId)
    : null;
  const pending = createM.isPending || updateM.isPending;

  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-xs"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          {isEditing ? "Editar classe" : "Nova classe"}
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

      {!isEditing && (
        <p className="text-xs text-foreground-muted">
          Pai:{" "}
          <span className="font-mono">
            {parentLabel ? `${parentLabel.codigo} ${parentLabel.nome}` : "(raiz)"}
          </span>
        </p>
      )}

      <div>
        <Label htmlFor="ccd-codigo">
          Código <span className="text-danger">*</span>
        </Label>
        <Input
          id="ccd-codigo"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          placeholder="Ex: 025"
          maxLength={20}
        />
      </div>

      <div>
        <Label htmlFor="ccd-nome">
          Nome <span className="text-danger">*</span>
        </Label>
        <Input
          id="ccd-nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Ex: Concursos e seleções"
          maxLength={200}
        />
      </div>

      <div>
        <Label htmlFor="ccd-desc">Descrição (opcional)</Label>
        <Textarea
          id="ccd-desc"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          rows={2}
          maxLength={1000}
        />
      </div>

      <div>
        <Label htmlFor="ccd-kw">
          Palavras-chave{" "}
          <span className="text-xs text-foreground-muted">
            (CSV — ajuda a sugestão automática)
          </span>
        </Label>
        <Input
          id="ccd-kw"
          value={palavrasChave}
          onChange={(e) => setPalavrasChave(e.target.value)}
          placeholder="Ex: edital, concurso, vaga"
          maxLength={500}
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

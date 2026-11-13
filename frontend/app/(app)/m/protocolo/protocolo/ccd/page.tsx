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

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { FormField } from "@/components/ui/form-field";
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
        actions={
          canInsert && (
            <Button
              onClick={() => {
                setEditing(null);
                setCreatingParent(null);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Nova classe raiz
            </Button>
          )
        }
      />

      <div className="flex gap-2">
        <Button size="sm" variant="secondary" onClick={expandAll}>
          Expandir tudo
        </Button>
        <Button size="sm" variant="secondary" onClick={collapseAll}>
          Recolher
        </Button>
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
            <EmptyState
              icon={FolderTree}
              title="Nenhuma classe cadastrada"
              description="Use “Nova classe raiz” para criar a primeira da árvore."
              className="border-0 bg-transparent"
            />
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
              Use Editar na linha para alterar uma classe, &ldquo;Subclasse&rdquo; para criar
              uma abaixo dela ou &ldquo;Nova classe raiz&rdquo; no topo.
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
        {/* Eram ícones que só apareciam no hover: invisíveis no toque e no
            teclado. */}
        <AcoesDaLinha
          className="shrink-0"
          acoes={[
            {
              label: "Subclasse",
              icon: Plus,
              oculta: !onAddChild,
              onClick: () => onAddChild?.(node.id),
            },
            {
              label: "Editar",
              icon: Pencil,
              oculta: !onEdit,
              onClick: () => onEdit?.(classeForCallback),
            },
            {
              label: "Excluir",
              icon: Trash2,
              perigo: true,
              oculta: !onDelete,
              onClick: () => onDelete?.(classeForCallback),
            },
          ]}
        />
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

  // Erro sob o campo só depois de tentar salvar (antes era um toast genérico).
  const [tentou, setTentou] = useState(false);
  const faltaCodigo = !codigo.trim();
  const faltaNome = !nome.trim();

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setTentou(true);
    if (faltaCodigo || faltaNome) {
      document.getElementById(faltaCodigo ? "ccd-codigo" : "ccd-nome")?.focus();
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
      noValidate
      className="space-y-4 rounded-card border border-border bg-card p-4 shadow-card"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">
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
          Dentro de:{" "}
          <span className="font-mono text-foreground">
            {parentLabel ? `${parentLabel.codigo} ${parentLabel.nome}` : "raiz do plano"}
          </span>
        </p>
      )}

      <FormField
        label="Código"
        required
        error={tentou && faltaCodigo ? "Informe o código da classe, ex.: 025." : undefined}
      >
        <Input
          id="ccd-codigo"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value)}
          placeholder="Ex.: 025"
          maxLength={20}
          className="font-mono"
        />
      </FormField>

      <FormField
        label="Nome"
        required
        error={tentou && faltaNome ? "Dê um nome à classe." : undefined}
      >
        <Input
          id="ccd-nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          placeholder="Ex.: Concursos e seleções"
          maxLength={200}
        />
      </FormField>

      <FormField label="Descrição" opcional>
        <Textarea
          id="ccd-desc"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          rows={2}
          maxLength={1000}
        />
      </FormField>

      <FormField
        label="Palavras-chave"
        opcional
        hint="Separadas por vírgula. Ajudam a sugerir esta classe no balcão."
      >
        <Input
          id="ccd-kw"
          value={palavrasChave}
          onChange={(e) => setPalavrasChave(e.target.value)}
          placeholder="Ex.: edital, concurso, vaga"
          maxLength={500}
        />
      </FormField>

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" loading={pending}>
          {isEditing ? "Salvar alterações" : "Criar classe"}
        </Button>
      </div>
    </form>
  );
}

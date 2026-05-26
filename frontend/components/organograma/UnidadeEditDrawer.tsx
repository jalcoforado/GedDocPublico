"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Building2, Loader2, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { api, type OrganogramaNo, type UnidadeTrabalho } from "@/lib/api";

export type DrawerMode =
  | { kind: "create"; parentId: number | null }
  | { kind: "edit"; unidade: UnidadeTrabalho };

interface Props {
  open: boolean;
  mode: DrawerMode | null;
  allNos: OrganogramaNo[];
  onClose: () => void;
  /** Se false, o botão "Excluir" no modo edit fica escondido. */
  canDelete?: boolean;
}

/** IDs que NÃO podem ser pai da unidade sendo editada — ela mesma + descendentes
 * (impede ciclo). Para criação retorna conjunto vazio. */
function getInvalidParents(
  mode: DrawerMode,
  allNos: OrganogramaNo[],
): Set<number> {
  if (mode.kind !== "edit") return new Set();
  const invalid = new Set<number>([mode.unidade.id]);
  const children = new Map<number | null, OrganogramaNo[]>();
  for (const n of allNos) {
    if (!children.has(n.id_unidade_pai)) children.set(n.id_unidade_pai, []);
    children.get(n.id_unidade_pai)!.push(n);
  }
  function walk(id: number) {
    const kids = children.get(id) ?? [];
    for (const k of kids) {
      invalid.add(k.id);
      walk(k.id);
    }
  }
  walk(mode.unidade.id);
  return invalid;
}

export function UnidadeEditDrawer({
  open,
  mode,
  allNos,
  onClose,
  canDelete = true,
}: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [nome, setNome] = useState("");
  const [sigla, setSigla] = useState("");
  const [parentId, setParentId] = useState<number | null>(null);
  const [tipoId, setTipoId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const tiposQ = useQuery({
    queryKey: ["tipos-unidade"],
    queryFn: () => api.tiposUnidade(),
    staleTime: 5 * 60_000,
  });

  // Reset form quando abre/troca de mode
  useEffect(() => {
    if (!open || !mode) return;
    setErr(null);
    if (mode.kind === "create") {
      setNome("");
      setSigla("");
      setParentId(mode.parentId);
      setTipoId(null);
    } else {
      setNome(mode.unidade.unidade_trabalho);
      setSigla(mode.unidade.sigla ?? "");
      setParentId(mode.unidade.id_unidade_pai);
      setTipoId(mode.unidade.id_tipo_unidade_trabalho);
    }
  }, [open, mode]);

  const invalidParents = useMemo(
    () => (mode ? getInvalidParents(mode, allNos) : new Set<number>()),
    [mode, allNos],
  );

  const parentOptions: ComboboxOption[] = useMemo(() => {
    return allNos
      .filter((n) => !invalidParents.has(n.id))
      .map((n) => ({
        value: n.id,
        label: n.unidade_trabalho,
        hint: n.sigla ?? undefined,
      }));
  }, [allNos, invalidParents]);

  const saveM = useMutation({
    mutationFn: async () => {
      if (!mode) throw new Error("Sem modo definido");
      const payload = {
        unidade_trabalho: nome.trim(),
        sigla: sigla.trim() || null,
        id_unidade_pai: parentId,
        id_tipo_unidade_trabalho: tipoId,
      };
      if (mode.kind === "create") {
        return api.unidades.create(payload);
      }
      return api.unidades.update(mode.unidade.id, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organograma"] });
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success(
        mode?.kind === "create" ? "Unidade criada." : "Unidade atualizada.",
      );
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const deleteM = useMutation({
    mutationFn: async () => {
      if (mode?.kind !== "edit") throw new Error("Só edita exclui");
      return api.unidades.remove(mode.unidade.id);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organograma"] });
      qc.invalidateQueries({ queryKey: ["unidades"] });
      toast.success("Unidade excluída.");
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  async function handleDelete() {
    if (mode?.kind !== "edit") return;
    const hasChildren = allNos.some((n) => n.id_unidade_pai === mode.unidade.id);
    const ok = await confirm({
      title: "Excluir unidade?",
      message: (
        <div className="space-y-2 text-sm">
          <p>
            Excluir <strong>{mode.unidade.unidade_trabalho}</strong>?
          </p>
          {hasChildren && (
            <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className="text-xs">
                Esta unidade tem subordinadas. Excluí-la pode deixar filhas órfãs
                no organograma. Considere mover as filhas antes.
              </span>
            </div>
          )}
          <p className="text-xs text-foreground-muted">
            A exclusão é lógica (soft delete) — a unidade não aparece mais nas
            listagens, mas processos históricos preservam a referência.
          </p>
        </div>
      ),
      confirmLabel: "Excluir",
      cancelLabel: "Cancelar",
      intent: "danger",
    });
    if (ok) deleteM.mutate();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!nome.trim()) {
      setErr("Informe o nome da unidade.");
      return;
    }
    saveM.mutate();
  }

  if (!open || !mode) return null;

  const title =
    mode.kind === "create"
      ? mode.parentId == null
        ? "Nova unidade (raiz)"
        : "Nova subunidade"
      : `Editar: ${mode.unidade.unidade_trabalho}`;

  const isEdit = mode.kind === "edit";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <div className="flex w-full items-center justify-between">
          {isEdit && canDelete ? (
            <Button
              type="button"
              variant="ghost"
              onClick={handleDelete}
              disabled={deleteM.isPending}
              className="text-danger hover:bg-danger-soft hover:text-danger-soft-foreground"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
              {deleteM.isPending ? "Excluindo…" : "Excluir"}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              form="unidade-form"
              disabled={saveM.isPending}
            >
              {saveM.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Salvando…
                </>
              ) : (
                "Salvar"
              )}
            </Button>
          </div>
        </div>
      }
    >
      <form id="unidade-form" onSubmit={submit} className="space-y-4" noValidate>
        {err && (
          <div
            role="alert"
            className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </div>
        )}

        <div>
          <Label htmlFor="u-nome" required>
            Nome da unidade
          </Label>
          <Input
            id="u-nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Ex: Secretaria de Planejamento e Gestão"
            autoFocus
            required
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-[1fr_2fr]">
          <div>
            <Label htmlFor="u-sigla">Sigla</Label>
            <Input
              id="u-sigla"
              value={sigla}
              onChange={(e) => setSigla(e.target.value.toUpperCase())}
              placeholder="Ex: SEPLAG"
              maxLength={20}
              className="font-mono uppercase"
            />
          </div>

          <div>
            <Label htmlFor="u-tipo">Tipo</Label>
            <Select
              id="u-tipo"
              value={tipoId ?? ""}
              onChange={(e) => setTipoId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">— Sem tipo —</option>
              {tiposQ.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.tipo_unidade_trabalho}
                  {t.codigo ? ` (${t.codigo})` : ""}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <div>
          <Label htmlFor="u-pai">Unidade superior</Label>
          <Combobox
            id="u-pai"
            options={parentOptions}
            value={parentId}
            onChange={(v) => setParentId(typeof v === "number" ? v : null)}
            placeholder="(raiz — nenhuma)"
            searchPlaceholder="Buscar superior…"
            emptyText={
              isEdit
                ? "Nenhuma unidade disponível (não pode ser ela mesma nem subordinada)."
                : "Nenhuma unidade cadastrada."
            }
            loading={false}
          />
          <p className="mt-1 flex items-start gap-1 text-xs text-foreground-subtle">
            <Building2 className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
            <span>
              Deixe em branco para criar uma unidade-raiz (topo do organograma).
              {isEdit && " Você não pode mover esta unidade para baixo de uma subordinada."}
            </span>
          </p>
        </div>
      </form>
    </Dialog>
  );
}

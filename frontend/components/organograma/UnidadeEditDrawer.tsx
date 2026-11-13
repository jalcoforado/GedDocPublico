"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Building2, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { Dialog } from "@/components/ui/dialog";
import { FormField, GradeCampos, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
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

/** Caminho dos ancestrais, da raiz até o pai: "PREF › SEMAS". */
function caminhoAte(no: OrganogramaNo, porId: Map<number, OrganogramaNo>): string {
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
 * Formulário de unidade de trabalho — o mesmo no Organograma e na lista de
 * Unidades, para a unidade ser cadastrada de um jeito só nas duas telas.
 */
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
  // Erro do nome só depois da tentativa (saiu do campo ou tentou salvar).
  const [nomeTocado, setNomeTocado] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const tiposQ = useQuery({
    queryKey: ["tipos-unidade"],
    queryFn: () => api.tiposUnidade(),
    staleTime: 5 * 60_000,
  });

  // Reset form quando abre/troca de mode
  useEffect(() => {
    if (!open || !mode) return;
    setErr(null);
    setNomeTocado(false);
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

  const porId = useMemo(() => new Map(allNos.map((n) => [n.id, n])), [allNos]);

  // Cada opção mostra onde a unidade fica ("PREF › SEMAS"): numa prefeitura
  // com dois "Departamento Administrativo", o nome sozinho não decide.
  const parentOptions: ComboboxOption[] = useMemo(() => {
    return allNos
      .filter((n) => !invalidParents.has(n.id))
      .map((n) => ({
        value: n.id,
        label: n.unidade_trabalho + (n.sigla ? ` (${n.sigla})` : ""),
        hint: caminhoAte(n, porId) || undefined,
      }))
      .sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
  }, [allNos, invalidParents, porId]);

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
      // A lista de Unidades mostra o nome do pai a partir desta consulta.
      qc.invalidateQueries({ queryKey: ["unidades-all"] });
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
      qc.invalidateQueries({ queryKey: ["unidades-all"] });
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
            <div className="flex items-start gap-2 rounded-md border border-warning/30 bg-warning-soft px-3 py-2 text-warning-soft-foreground">
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

  const erroNome = nome.trim() ? undefined : "Informe o nome da unidade.";

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (erroNome) {
      flushSync(() => setNomeTocado(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
    saveM.mutate();
  }

  if (!open || !mode) return null;

  const isEdit = mode.kind === "edit";
  const paiInicial = mode.kind === "create" && mode.parentId != null ? porId.get(mode.parentId) : undefined;

  const title = isEdit ? "Editar unidade" : paiInicial ? "Nova subunidade" : "Nova unidade";
  const description = isEdit
    ? mode.unidade.unidade_trabalho
    : paiInicial
      ? `Dentro de ${paiInicial.unidade_trabalho}.`
      : "Secretaria, setor ou equipamento onde os servidores trabalham.";

  // Consequência da escolha do pai, dita por extenso.
  const pai = parentId != null ? porId.get(parentId) : undefined;
  const dicaPai = pai
    ? `Fica dentro de ${[caminhoAte(pai, porId), pai.sigla || pai.unidade_trabalho].filter(Boolean).join(" › ")}.`
    : "Em branco, a unidade fica no topo do organograma.";

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      size="md"
      footer={
        <div className="flex w-full flex-wrap items-center justify-between gap-2">
          {isEdit && canDelete ? (
            <Button
              type="button"
              variant="danger-outline"
              onClick={handleDelete}
              loading={deleteM.isPending}
            >
              {!deleteM.isPending && <Trash2 className="h-4 w-4" aria-hidden="true" />}
              {deleteM.isPending ? "Excluindo…" : "Excluir"}
            </Button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" form="unidade-form" loading={saveM.isPending}>
              {saveM.isPending ? "Salvando…" : isEdit ? "Salvar alterações" : "Cadastrar unidade"}
            </Button>
          </div>
        </div>
      }
    >
      <form ref={formRef} id="unidade-form" onSubmit={submit} className="space-y-4" noValidate>
        {err && (
          <div
            role="alert"
            className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </div>
        )}

        <FormField label="Nome da unidade" required error={nomeTocado ? erroNome : undefined}>
          <Input
            id="u-nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            onBlur={() => setNomeTocado(true)}
            placeholder="Ex.: Secretaria de Planejamento e Gestão"
            autoFocus
          />
        </FormField>

        <GradeCampos>
          <FormField
            label="Sigla"
            opcional
            hint="Aparece nas listas e no organograma."
          >
            <Input
              id="u-sigla"
              value={sigla}
              onChange={(e) => setSigla(e.target.value.toUpperCase())}
              placeholder="Ex.: SEPLAG"
              maxLength={20}
              className="font-mono uppercase"
            />
          </FormField>

          <FormField label="Tipo" opcional>
            <Select
              id="u-tipo"
              value={tipoId ?? ""}
              onChange={(e) => setTipoId(e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Sem tipo</option>
              {tiposQ.data?.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.tipo_unidade_trabalho}
                  {t.codigo ? ` (${t.codigo})` : ""}
                </option>
              ))}
            </Select>
          </FormField>
        </GradeCampos>

        <FormField
          label="Unidade superior"
          opcional
          hint={
            <span className="flex items-start gap-1">
              <Building2 className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
              <span>
                {dicaPai}
                {isEdit && " Ela não pode ficar abaixo dela mesma nem de uma subordinada."}
              </span>
            </span>
          }
        >
          <Combobox
            id="u-pai"
            options={parentOptions}
            value={parentId}
            onChange={(v) => setParentId(typeof v === "number" ? v : null)}
            placeholder="Nenhuma — topo do organograma"
            searchPlaceholder="Buscar pelo nome ou pela sigla…"
            emptyText={
              isEdit
                ? "Nenhuma unidade disponível (não pode ser ela mesma nem subordinada)."
                : "Nenhuma unidade com esse nome."
            }
          />
        </FormField>
      </form>
    </Dialog>
  );
}

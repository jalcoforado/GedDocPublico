"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, Loader2, Pencil, Plus, Trash2, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { volumesApi, type VolumeDetail } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface Props {
  processoId: number;
}

export function ProcessoVolumes({ processoId }: Props) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const { can } = useAuth();
  const canInsert = can("processo", "atualizar");
  const canDelete = can("processo", "excluir");

  const [openForm, setOpenForm] = useState<"create" | { edit: VolumeDetail } | null>(
    null,
  );

  const q = useQuery({
    queryKey: ["volumes", processoId],
    queryFn: () => volumesApi.list(processoId),
  });

  const deleteM = useMutation({
    mutationFn: (id: number) => volumesApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["volumes", processoId] });
      toast.success("Volume excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function onDelete(v: VolumeDetail) {
    const ok = await confirm({
      title: `Excluir volume ${v.numero}`,
      message:
        "Esta operação remove o registro do volume. Os anexos do processo não são afetados.",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) deleteM.mutate(v.id);
  }

  const volumes = q.data ?? [];
  const proximoNumero =
    volumes.length === 0 ? 1 : Math.max(...volumes.map((v) => v.numero)) + 1;

  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
            aria-hidden="true"
          >
            <BookOpenText className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold tracking-tight">Volumes</h2>
            <p className="mt-0.5 text-xs text-foreground-muted">
              Subdivisão física quando o processo ultrapassa o limite de páginas
              por encadernação (~200 padrão CONARQ).
            </p>
          </div>
        </div>
        {canInsert && (
          <Button size="sm" variant="secondary" onClick={() => setOpenForm("create")}>
            <Plus className="mr-1 h-4 w-4" aria-hidden="true" />
            Novo volume
          </Button>
        )}
      </header>

      <div className="p-5">
        {q.isLoading && (
          <p className="text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" /> Carregando…
          </p>
        )}

        {!q.isLoading && volumes.length === 0 && (
          <p className="text-sm text-foreground-muted">
            Nenhum volume cadastrado. Adicione quando precisar subdividir o
            processo fisicamente.
          </p>
        )}

        {volumes.length > 0 && (
          <ol className="flex flex-wrap gap-3">
            {volumes.map((v) => (
              <VolumeSpine
                key={v.id}
                v={v}
                total={volumes.length}
                onEdit={canInsert ? () => setOpenForm({ edit: v }) : undefined}
                onDelete={canDelete ? () => onDelete(v) : undefined}
              />
            ))}
          </ol>
        )}
      </div>

      {openForm && (
        <VolumeForm
          processoId={processoId}
          editing={typeof openForm === "object" ? openForm.edit : null}
          numeroSugerido={proximoNumero}
          onClose={() => setOpenForm(null)}
          onSuccess={() => {
            qc.invalidateQueries({ queryKey: ["volumes", processoId] });
            setOpenForm(null);
          }}
        />
      )}
    </section>
  );
}

/** Lombada de livro estilizada — número grande à esquerda + dados à direita. */
function VolumeSpine({
  v,
  total,
  onEdit,
  onDelete,
}: {
  v: VolumeDetail;
  total: number;
  onEdit?: () => void;
  onDelete?: () => void;
}) {
  return (
    <li
      className={cn(
        "group relative flex w-56 overflow-hidden rounded-lg border border-border bg-surface-1",
        "transition-all duration-fast hover:border-brand/40 hover:shadow-sm",
      )}
    >
      {/* Lombada (faixa lateral colorida) */}
      <div
        aria-hidden="true"
        className="relative flex w-12 shrink-0 items-center justify-center bg-gradient-to-b from-brand to-brand/70"
      >
        <span className="rotate-180 font-mono text-lg font-bold tracking-tighter text-white [writing-mode:vertical-rl]">
          VOL {String(v.numero).padStart(2, "0")}
        </span>
      </div>

      {/* Conteúdo */}
      <div className="flex min-w-0 flex-1 flex-col justify-between p-3">
        <div>
          <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
            Volume {v.numero} de {total}
          </div>
          <div className="mt-1 font-mono text-sm text-foreground">
            {v.pagina_inicial != null && v.pagina_final != null
              ? `pp. ${v.pagina_inicial}–${v.pagina_final}`
              : "—"}
          </div>
          {v.observacao && (
            <p className="mt-1 line-clamp-2 text-xs text-foreground-muted">
              {v.observacao}
            </p>
          )}
        </div>
        <div className="mt-2 flex items-end justify-between">
          <span className="text-[10px] text-foreground-subtle">
            {v.usuario_nome ?? "—"}
          </span>
          <div className="flex opacity-0 transition-opacity group-hover:opacity-100">
            {onEdit && (
              <button
                type="button"
                onClick={onEdit}
                className="rounded p-1 text-foreground-muted hover:bg-surface-3 hover:text-foreground"
                aria-label="Editar volume"
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                onClick={onDelete}
                className="rounded p-1 text-foreground-muted hover:bg-danger/10 hover:text-danger"
                aria-label="Excluir volume"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      </div>
    </li>
  );
}

function VolumeForm({
  processoId,
  editing,
  numeroSugerido,
  onClose,
  onSuccess,
}: {
  processoId: number;
  editing: VolumeDetail | null;
  numeroSugerido: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const toast = useToast();
  const [numero, setNumero] = useState(editing?.numero ?? numeroSugerido);
  const [paginaInicial, setPaginaInicial] = useState<string>(
    editing?.pagina_inicial != null ? String(editing.pagina_inicial) : "",
  );
  const [paginaFinal, setPaginaFinal] = useState<string>(
    editing?.pagina_final != null ? String(editing.pagina_final) : "",
  );
  const [observacao, setObservacao] = useState(editing?.observacao ?? "");

  const saveM = useMutation({
    mutationFn: () => {
      const pi = paginaInicial.trim() === "" ? null : Number(paginaInicial);
      const pf = paginaFinal.trim() === "" ? null : Number(paginaFinal);
      if (editing) {
        return volumesApi.update(editing.id, {
          pagina_inicial: pi,
          pagina_final: pf,
          observacao: observacao || null,
        });
      }
      return volumesApi.create(processoId, {
        numero,
        pagina_inicial: pi,
        pagina_final: pf,
        observacao: observacao || null,
      });
    },
    onSuccess: () => {
      toast.success(editing ? "Volume atualizado." : "Volume criado.");
      onSuccess();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          saveM.mutate();
        }}
        className="w-full max-w-md space-y-3 rounded-xl border border-border bg-card p-5 shadow-xl animate-scale-in"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">
            {editing ? `Editar volume ${editing.numero}` : "Novo volume"}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-foreground-muted hover:bg-surface-2"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div>
            <Label htmlFor="vol-num">
              Número <span className="text-danger">*</span>
            </Label>
            <Input
              id="vol-num"
              type="number"
              value={numero}
              min={1}
              max={999}
              disabled={editing !== null}
              onChange={(e) => setNumero(Number(e.target.value) || 1)}
            />
          </div>
          <div>
            <Label htmlFor="vol-pi">Pág. inicial</Label>
            <Input
              id="vol-pi"
              type="number"
              value={paginaInicial}
              min={1}
              onChange={(e) => setPaginaInicial(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="vol-pf">Pág. final</Label>
            <Input
              id="vol-pf"
              type="number"
              value={paginaFinal}
              min={1}
              onChange={(e) => setPaginaFinal(e.target.value)}
            />
          </div>
        </div>

        <div>
          <Label htmlFor="vol-obs">Observação (opcional)</Label>
          <Textarea
            id="vol-obs"
            value={observacao}
            onChange={(e) => setObservacao(e.target.value)}
            rows={2}
            maxLength={500}
          />
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saveM.isPending}>
            {saveM.isPending && (
              <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
            )}
            {editing ? "Salvar" : "Criar"}
          </Button>
        </div>
      </form>
    </div>
  );
}

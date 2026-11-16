"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, FileText, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { RedigirDocumentoDialog } from "@/components/RedigirDocumentoDialog";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Carregando } from "@/components/ui/carregando";
import { useConfirm } from "@/components/ui/confirm";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { api, type MinutaStatus, type ProcessoDetail } from "@/lib/api";

const STATUS_LABEL: Record<MinutaStatus, string> = {
  rascunho: "Rascunho",
  finalizada: "Finalizada",
  cancelada: "Cancelada",
};

const STATUS_INTENT: Record<MinutaStatus, "warning" | "success" | "neutral"> = {
  rascunho: "warning",
  finalizada: "success",
  cancelada: "neutral",
};

export function MinutasProcesso({ processo }: { processo: ProcessoDetail }) {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editId, setEditId] = useState<number | undefined>(undefined);

  const minutasQ = useQuery({
    queryKey: ["minutas", processo.id],
    queryFn: () => api.minutas.list(processo.id),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.minutas.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["minutas", processo.id] });
      toast.success("Rascunho excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const finalizarM = useMutation({
    mutationFn: (id: number) => api.minutas.finalizar(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["minutas", processo.id] });
      // o anexo PDF gerado aparece na lista de anexos do processo
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      toast.success("Documento finalizado e anexado ao processo.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function finalizar(id: number) {
    if (
      await confirm({
        title: "Finalizar documento?",
        message:
          "Será gerado um PDF anexado ao processo. Depois de finalizado, o documento não pode mais ser editado (mas pode ser carimbado e assinado).",
        confirmLabel: "Finalizar",
      })
    ) {
      finalizarM.mutate(id);
    }
  }

  const minutas = minutasQ.data ?? [];

  function abrirNova() {
    setEditId(undefined);
    setDialogOpen(true);
  }

  function abrirEdicao(id: number) {
    setEditId(id);
    setDialogOpen(true);
  }

  async function excluir(id: number) {
    if (
      await confirm({
        title: "Excluir rascunho?",
        message: "O rascunho será removido. Esta ação não pode ser desfeita.",
        confirmLabel: "Excluir",
      })
    ) {
      removeM.mutate(id);
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-foreground-muted">
          {minutas.length} documento{minutas.length === 1 ? "" : "s"} redigido
          {minutas.length === 1 ? "" : "s"}
        </div>
        <Button onClick={abrirNova} disabled={!processo.ativo}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Redigir documento
        </Button>
      </div>

      {minutasQ.isLoading ? (
        <Carregando className="text-sm text-muted-foreground" />
      ) : minutas.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="Nenhum documento redigido"
          description="Use “Redigir documento” para criar a partir de um modelo ou em branco."
          className="p-6"
        />
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-card">
          {minutas.map((m) => (
            <li
              key={m.id}
              className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-foreground">
                  {m.titulo}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge intent={STATUS_INTENT[m.status]}>{STATUS_LABEL[m.status]}</Badge>
                  <span>v{m.versao}</span>
                  {m.origem === "google" && <span>· Google Docs</span>}
                </div>
              </div>
              {m.status === "rascunho" && (
                <AcoesDaLinha
                  acoes={[
                    { label: "Editar", icon: Pencil, onClick: () => abrirEdicao(m.id) },
                    {
                      label: "Finalizar",
                      icon: CheckCircle2,
                      onClick: () => finalizar(m.id),
                      disabled: finalizarM.isPending,
                    },
                    {
                      label: "Excluir",
                      icon: Trash2,
                      perigo: true,
                      onClick: () => excluir(m.id),
                      disabled: removeM.isPending,
                    },
                  ]}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      <RedigirDocumentoDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        processoId={processo.id}
        minutaId={editId}
        onSaved={() =>
          qc.invalidateQueries({ queryKey: ["minutas", processo.id] })
        }
      />
    </div>
  );
}

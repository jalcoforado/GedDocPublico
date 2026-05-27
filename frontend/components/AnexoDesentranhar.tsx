"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileMinus, Loader2, ScrollText, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  desentranhamentoApi,
  termoDesentranhamentoPdfUrl,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Props {
  processoId: number;
  anexoProcessoId: number;
  descricaoAnexo: string | null;
}

/** Botão "Desentranhar" + dialog severo. */
export function AnexoDesentranhar({
  processoId,
  anexoProcessoId,
  descricaoAnexo,
}: Props) {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);

  if (!can("processo", "excluir")) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-foreground-muted transition-colors hover:bg-danger/5 hover:text-danger"
        title="Desentranhar este documento do processo"
      >
        <FileMinus className="h-3 w-3" aria-hidden="true" />
        Desentranhar
      </button>
      {open && (
        <DesentranharDialog
          processoId={processoId}
          anexoProcessoId={anexoProcessoId}
          descricaoAnexo={descricaoAnexo}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

function DesentranharDialog({
  processoId,
  anexoProcessoId,
  descricaoAnexo,
  onClose,
}: Props & { onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [motivo, setMotivo] = useState("");
  const [autoridade, setAutoridade] = useState("");

  const mutateM = useMutation({
    mutationFn: () => {
      if (motivo.trim().length < 3 || autoridade.trim().length < 2) {
        return Promise.reject(
          new Error("Informe motivo (≥3 chars) e autoridade (≥2 chars)."),
        );
      }
      return desentranhamentoApi.desentranhar(processoId, anexoProcessoId, {
        motivo: motivo.trim(),
        autoridade: autoridade.trim(),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo", processoId] });
      toast.success("Anexo desentranhado. Termo disponível.", {
        action: {
          label: "Baixar termo",
          onClick: () => {
            window.open(
              termoDesentranhamentoPdfUrl(processoId, anexoProcessoId),
              "_blank",
            );
          },
        },
      });
      onClose();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutateM.mutate();
        }}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-danger/30 bg-card shadow-xl animate-scale-in"
      >
        {/* Header severo */}
        <header className="flex items-start gap-3 border-b border-danger/30 bg-danger/5 px-5 py-4">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-danger/10 text-danger"
            aria-hidden="true"
          >
            <AlertTriangle className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="text-sm font-semibold tracking-tight text-foreground">
              Desentranhar documento do processo
            </h3>
            <p className="mt-0.5 text-xs text-foreground-muted">
              Operação formal. Gera termo PDF que vai pro audit log e ao arquivo
              físico. O documento <strong>não é destruído</strong> — permanece
              arquivado em separado.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded p-1 text-foreground-muted hover:bg-surface-2"
            aria-label="Fechar"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="space-y-4 px-5 py-4">
          {descricaoAnexo && (
            <div className="rounded-md border border-border bg-surface-1 px-3 py-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
                Documento
              </div>
              <div className="mt-0.5 text-sm">{descricaoAnexo}</div>
            </div>
          )}

          <div>
            <Label htmlFor="desent-motivo">
              Motivo <span className="text-danger">*</span>
            </Label>
            <Textarea
              id="desent-motivo"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              rows={3}
              maxLength={1000}
              placeholder="Ex: documento juntado por engano, pertence a outro processo"
              autoFocus
            />
          </div>

          <div>
            <Label htmlFor="desent-aut">
              Autoridade <span className="text-danger">*</span>
            </Label>
            <Input
              id="desent-aut"
              value={autoridade}
              onChange={(e) => setAutoridade(e.target.value)}
              maxLength={300}
              placeholder="Ex: Diretora de Protocolo, Portaria 123/2026"
            />
            <p className="mt-1 text-[10px] text-foreground-muted">
              Cargo + ato administrativo que autoriza o desentranhamento.
              Aparece no termo PDF.
            </p>
          </div>
        </div>

        <footer className="flex items-center justify-between gap-2 border-t border-border bg-surface-1 px-5 py-3">
          <span className="flex items-center gap-1 text-[10px] text-foreground-muted">
            <ScrollText className="h-3 w-3" aria-hidden="true" />
            Audit + termo PDF gerados na ação
          </span>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={onClose}>
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={
                mutateM.isPending ||
                motivo.trim().length < 3 ||
                autoridade.trim().length < 2
              }
              className="bg-danger hover:bg-danger/90 text-danger-foreground"
            >
              {mutateM.isPending && (
                <Loader2 className="mr-1 h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              <FileMinus className="mr-1 h-4 w-4" aria-hidden="true" />
              Desentranhar
            </Button>
          </div>
        </footer>
      </form>
    </div>
  );
}

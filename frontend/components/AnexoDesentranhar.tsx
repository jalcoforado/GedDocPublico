"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileMinus, Loader2, ScrollText } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
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
  const formId = useId();
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
    <Dialog
      open
      onClose={onClose}
      title="Desentranhar documento do processo"
      footer={
        <>
          <span className="mr-auto flex items-center gap-1 self-center text-[10px] text-foreground-muted">
            <ScrollText className="h-3 w-3" aria-hidden="true" />
            Audit + termo PDF gerados na ação
          </span>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            type="submit"
            form={formId}
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
        </>
      }
    >
      <form
        id={formId}
        onSubmit={(e) => {
          e.preventDefault();
          mutateM.mutate();
        }}
        className="space-y-4"
      >
        {/* Aviso severo: operação formal com efeito em audit + arquivo físico */}
        <div className="flex items-start gap-3 rounded-md border border-danger/30 bg-danger/5 px-3 py-2.5">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-danger/10 text-danger"
            aria-hidden="true"
          >
            <AlertTriangle className="h-4 w-4" />
          </span>
          <p className="text-xs text-foreground-muted">
            Operação formal. Gera termo PDF que vai pro audit log e ao arquivo
            físico. O documento <strong>não é destruído</strong> — permanece
            arquivado em separado.
          </p>
        </div>

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
      </form>
    </Dialog>
  );
}

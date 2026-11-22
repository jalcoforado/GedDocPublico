"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/textarea";
import { api, type ProcessoDetail } from "@/lib/api";

/**
 * Cancelar recebimento feito por engano (SI-61, RF-02).
 *
 * Não é "recusar": recusar é dizer "não é meu" antes de receber. Aqui o
 * processo já foi recebido, e o cancelamento o devolve a esse ponto — de novo
 * aguardando recebimento na unidade —, de onde ela pode recusar. O diálogo diz
 * isso, porque é a diferença que confunde.
 */
export function CancelarRecebimentoDialog({
  open,
  onClose,
  processo,
}: {
  open: boolean;
  onClose: () => void;
  processo: ProcessoDetail;
}) {
  const qc = useQueryClient();
  const [justificativa, setJustificativa] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [tentou, setTentou] = useState(false);

  const cancelarM = useMutation({
    mutationFn: () => api.processos.cancelarRecebimento(processo.id, justificativa.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      qc.invalidateQueries({ queryKey: ["processos"] });
      setJustificativa("");
      fechar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  // O mesmo piso do schema (`min_length=5`, sem contar espaços).
  const valida = justificativa.trim().length >= 5;

  function fechar() {
    setTentou(false);
    setErr(null);
    onClose();
  }

  function confirmar() {
    setErr(null);
    setTentou(true);
    if (!valida) {
      document.getElementById("canc-receb-justificativa")?.focus();
      return;
    }
    cancelarM.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title="Cancelar recebimento"
      description="Use quando o processo foi recebido por engano. Ele volta a aguardar recebimento na sua unidade, e daí você pode recusá-lo. Quem enviou é avisado."
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Voltar
          </Button>
          <Button onClick={confirmar} loading={cancelarM.isPending}>
            {cancelarM.isPending ? "Cancelando…" : "Confirmar cancelamento"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FormField
          label="Justificativa"
          required
          hint="Fica no histórico do processo e vai no aviso para quem enviou."
          error={
            tentou && !valida
              ? "Escreva por que o recebimento está sendo cancelado, com pelo menos 5 letras."
              : undefined
          }
        >
          <Textarea
            id="canc-receb-justificativa"
            rows={3}
            maxLength={2000}
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            placeholder="Ex.: Recebido por engano; o processo é da Secretaria de Educação."
          />
        </FormField>

        {err && (
          <p
            role="alert"
            className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </p>
        )}
      </div>
    </Dialog>
  );
}

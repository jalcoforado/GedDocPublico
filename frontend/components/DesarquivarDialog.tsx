"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/textarea";
import { api, type ProcessoDetail } from "@/lib/api";

/**
 * Desarquivamento do processo (SI-60, RF-01).
 *
 * A justificativa é obrigatória e vira despacho na linha do tempo, ao lado do
 * arquivamento que está sendo desfeito — que continua lá, como histórico.
 * O diálogo avisa as duas consequências que não são óbvias: o processo volta
 * para a unidade onde foi arquivado, e o prazo do serviço recomeça a contar
 * (decisão do PO em 22/11/2026).
 */
export function DesarquivarDialog({
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

  const desarquivarM = useMutation({
    mutationFn: () => api.processos.desarquivar(processo.id, justificativa.trim()),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      qc.invalidateQueries({ queryKey: ["processos"] });
      setJustificativa("");
      fechar();
    },
    onError: (e: Error) => setErr(e.message),
  });

  // O mesmo piso do schema (`min_length=5`, sem contar espaços). O servidor
  // continua sendo a autoridade — isto só adianta o aviso.
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
      document.getElementById("desarq-justificativa")?.focus();
      return;
    }
    desarquivarM.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title={
        processo.numero_processo
          ? `Desarquivar processo ${processo.numero_processo}`
          : "Desarquivar processo"
      }
      description="O processo volta para a unidade onde foi arquivado, e o prazo do serviço recomeça a contar a partir de hoje."
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={confirmar} loading={desarquivarM.isPending}>
            {desarquivarM.isPending ? "Desarquivando…" : "Desarquivar processo"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FormField
          label="Justificativa"
          required
          hint="Fica no histórico do processo, ao lado do arquivamento."
          error={
            tentou && !valida
              ? "Escreva por que o processo está sendo desarquivado, com pelo menos 5 letras."
              : undefined
          }
        >
          <Textarea
            id="desarq-justificativa"
            rows={3}
            maxLength={2000}
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            placeholder="Ex.: Cidadão apresentou documento novo em 22/11."
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

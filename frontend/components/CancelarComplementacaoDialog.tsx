"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
import { Textarea } from "@/components/ui/textarea";

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: { motivo: string | null }) => void;
  submitting?: boolean;
}

export function CancelarComplementacaoDialog({
  open,
  onClose,
  onSubmit,
  submitting,
}: Props) {
  const [motivo, setMotivo] = useState("");

  useEffect(() => {
    if (open) setMotivo("");
  }, [open]);

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!submitting) onClose();
      }}
      title="Cancelar complementação"
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Voltar
          </Button>
          <Button
            variant="danger"
            loading={submitting}
            onClick={() =>
              onSubmit({ motivo: motivo.trim().length ? motivo.trim() : null })
            }
          >
            {submitting ? "Cancelando…" : "Confirmar cancelamento"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm">
          Esta complementação ficará registrada como{" "}
          <strong>cancelada</strong>. Você poderá abrir uma nova depois.
        </p>
        <FormField label="Motivo" opcional hint={`Fica no histórico. ${motivo.length}/500`}>
          <Textarea
            id="motivo-cancel"
            rows={3}
            maxLength={500}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Ex.: O cidadão entregou os documentos no balcão."
          />
        </FormField>
      </div>
    </Dialog>
  );
}

"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
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
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Voltar
          </Button>
          <Button
            variant="danger"
            disabled={submitting}
            onClick={() =>
              onSubmit({ motivo: motivo.trim().length ? motivo.trim() : null })
            }
          >
            {submitting ? "Cancelando..." : "Confirmar cancelamento"}
          </Button>
        </>
      }
    >
      <div className="space-y-3">
        <p className="text-sm">
          Esta complementação ficará registrada como{" "}
          <strong>cancelada</strong>. Você poderá abrir uma nova depois.
        </p>
        <div>
          <Label htmlFor="motivo-cancel">Motivo (opcional)</Label>
          <Textarea
            id="motivo-cancel"
            rows={3}
            maxLength={500}
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
            placeholder="Por que está cancelando?"
          />
          <p className="mt-1 text-xs text-foreground-muted">
            {motivo.length}/500
          </p>
        </div>
      </div>
    </Dialog>
  );
}

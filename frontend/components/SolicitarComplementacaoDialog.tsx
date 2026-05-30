"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ChecklistDocumentosResponse } from "@/lib/api";

interface Props {
  open: boolean;
  onClose: () => void;
  checklist: ChecklistDocumentosResponse | undefined;
  onSubmit: (data: { mensagem: string; documentos_solicitados: string[] }) => void;
  submitting?: boolean;
}

export function SolicitarComplementacaoDialog({
  open,
  onClose,
  checklist,
  onSubmit,
  submitting,
}: Props) {
  const [mensagem, setMensagem] = useState("");
  const [selecionadas, setSelecionadas] = useState<Set<string>>(new Set());

  // Pré-marca os itens NÃO enviados quando o dialog abre.
  useEffect(() => {
    if (!open) return;
    const naoEnviados = (checklist?.itens ?? [])
      .filter((i) => !i.enviado)
      .map((i) => i.key);
    setSelecionadas(new Set(naoEnviados));
    setMensagem("");
  }, [open, checklist]);

  const itens = checklist?.itens ?? [];
  const podeEnviar =
    mensagem.trim().length > 0 && selecionadas.size > 0 && !submitting;

  function toggle(key: string) {
    setSelecionadas((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!submitting) onClose();
      }}
      title="Solicitar complementação documental"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button
            disabled={!podeEnviar}
            onClick={() =>
              onSubmit({
                mensagem: mensagem.trim(),
                documentos_solicitados: Array.from(selecionadas),
              })
            }
          >
            {submitting ? "Enviando..." : "Enviar solicitação"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <div>
          <Label htmlFor="comp-msg">Mensagem ao cidadão</Label>
          <Textarea
            id="comp-msg"
            value={mensagem}
            onChange={(e) => setMensagem(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder="Descreva o que falta ou precisa ser corrigido."
          />
          <p className="mt-1 text-xs text-foreground-muted">
            {mensagem.length}/2000
          </p>
        </div>
        <div>
          <Label>Documentos solicitados</Label>
          {itens.length === 0 ? (
            <p className="mt-1 text-sm text-foreground-muted">
              Este processo não possui documentos exigidos configurados.
            </p>
          ) : (
            <ul className="mt-1 space-y-1">
              {itens.map((item) => (
                <li key={item.key} className="flex items-start gap-2">
                  <Checkbox
                    id={`comp-key-${item.key}`}
                    checked={selecionadas.has(item.key)}
                    onChange={() => toggle(item.key)}
                  />
                  <label
                    htmlFor={`comp-key-${item.key}`}
                    className="cursor-pointer text-sm"
                  >
                    <span className="font-medium">{item.nome}</span>
                    {item.enviado && (
                      <span className="ml-2 text-xs text-foreground-muted">
                        (já enviado)
                      </span>
                    )}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Dialog>
  );
}

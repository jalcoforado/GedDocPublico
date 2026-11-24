"use client";

import { AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog } from "@/components/ui/dialog";
import { FormField } from "@/components/ui/form-field";
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
  // Erro só depois de tentar enviar; o botão não fica cinza sem explicação.
  const [tentou, setTentou] = useState(false);

  // Pré-marca os itens NÃO enviados quando o dialog abre.
  useEffect(() => {
    if (!open) return;
    const naoEnviados = (checklist?.itens ?? [])
      .filter((i) => !i.enviado)
      .map((i) => i.key);
    setSelecionadas(new Set(naoEnviados));
    setMensagem("");
    setTentou(false);
  }, [open, checklist]);

  const itens = checklist?.itens ?? [];
  const faltaMensagem = mensagem.trim().length === 0;
  const faltaDocumento = selecionadas.size === 0;

  function toggle(key: string) {
    setSelecionadas((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function enviar() {
    setTentou(true);
    if (faltaMensagem) {
      document.getElementById("comp-msg")?.focus();
      return;
    }
    if (faltaDocumento) {
      document.querySelector<HTMLElement>('[id^="comp-key-"]')?.focus();
      return;
    }
    onSubmit({
      mensagem: mensagem.trim(),
      documentos_solicitados: Array.from(selecionadas),
    });
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!submitting) onClose();
      }}
      title="Solicitar complementação"
      description="O cidadão é avisado e vê a mensagem e a lista do que falta."
      size="md"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={submitting}>
            Cancelar
          </Button>
          <Button loading={submitting} onClick={enviar}>
            {submitting ? "Enviando…" : "Enviar solicitação"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <FormField
          label="Mensagem ao cidadão"
          required
          hint={`Diga o que falta ou o que precisa ser corrigido. ${mensagem.length}/2000`}
          error={
            tentou && faltaMensagem
              ? "Escreva a mensagem: é ela que explica ao cidadão o que fazer."
              : undefined
          }
        >
          <Textarea
            id="comp-msg"
            value={mensagem}
            onChange={(e) => setMensagem(e.target.value)}
            rows={4}
            maxLength={2000}
            placeholder="Ex.: A cópia do RG está ilegível. Envie uma foto nítida, frente e verso."
          />
        </FormField>
        <fieldset aria-describedby={tentou && faltaDocumento ? "comp-docs-erro" : undefined}>
          <legend className="mb-1 text-sm font-medium text-foreground">
            Documentos solicitados
            <span className="ml-0.5 text-danger" aria-hidden="true">
              *
            </span>
          </legend>
          {itens.length === 0 ? (
            <p className="text-sm text-foreground-muted">
              Este processo não possui documentos exigidos configurados.
            </p>
          ) : (
            <>
              <p className="mb-2 text-xs text-foreground-muted">
                Já vêm marcados os que o cidadão ainda não enviou.
              </p>
              <ul className="space-y-1.5">
                {itens.map((item) => (
                  <li key={item.key} className="flex items-start gap-2">
                    <Checkbox
                      id={`comp-key-${item.key}`}
                      checked={selecionadas.has(item.key)}
                      onChange={() => toggle(item.key)}
                      className="mt-0.5 h-4 w-4"
                    />
                    <label
                      htmlFor={`comp-key-${item.key}`}
                      className="cursor-pointer text-sm text-foreground"
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
            </>
          )}
          {tentou && faltaDocumento && (
            <p
              id="comp-docs-erro"
              className="mt-1.5 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground"
            >
              <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {itens.length === 0
                ? "Sem documentos exigidos no assunto, não há o que solicitar por aqui."
                : "Marque pelo menos um documento."}
            </p>
          )}
        </fieldset>
      </div>
    </Dialog>
  );
}

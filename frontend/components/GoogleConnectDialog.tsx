"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";

interface GoogleConnectDialogProps {
  open: boolean;
  onClose: () => void;
  minutaId: number;
  processoId: number;
  onSuccess?: () => void;
}

export function GoogleConnectDialog({
  open,
  onClose,
  minutaId,
  processoId,
  onSuccess,
}: GoogleConnectDialogProps) {
  const [isConnecting, setIsConnecting] = useState(false);

  function handleConnect() {
    setIsConnecting(true);
    const redirectUrl = `/api/v2/auth/google?minuta_id=${minutaId}&processo_id=${processoId}`;
    window.location.href = redirectUrl;
  }

  if (!open) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Conectar Google Docs"
      size="sm"
      footer={
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={handleConnect} disabled={isConnecting}>
            {isConnecting ? "Conectando…" : "Conectar Conta Google"}
          </Button>
        </div>
      }
    >
      {/* SI-32: o texto diz o que de fato acontece. O anterior afirmava que
          "a conta não é armazenada" — mas a autorização (token) fica guardada,
          cifrada, para o sistema abrir o documento depois. */}
      <div className="space-y-3 text-sm">
        <p>
          Você vai para a página do Google para autorizar o Aprimora a criar e editar documentos no
          seu Google Docs. Depois, volta para cá.
        </p>
        <ul className="list-disc space-y-1.5 pl-5 text-foreground-muted">
          <li>O Aprimora só enxerga os documentos que ele mesmo criar — não o resto do seu Drive.</li>
          <li>Sua senha do Google não passa pelo Aprimora.</li>
          <li>A autorização fica guardada, cifrada, para os documentos abrirem sem pedir de novo.</li>
          <li>
            Você pode cancelar quando quiser em{" "}
            <a
              href="https://myaccount.google.com/permissions"
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-brand hover:underline"
            >
              myaccount.google.com/permissions
            </a>
            .
          </li>
        </ul>
      </div>
    </Dialog>
  );
}

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
      <div className="space-y-4">
        <p>Autorize o acesso a sua conta Google Docs para redigir minutas com integração de documentos.</p>
        <div className="space-y-2">
          <p>✓ Você mantém controle total sobre suas credenciais.</p>
          <p>✓ Apenas leitura e criação de documentos autorizados.</p>
          <p>✓ Sua conta não é armazenada em nossos servidores.</p>
          <p>✓ Você pode revogar acesso a qualquer momento.</p>
        </div>
      </div>
    </Dialog>
  );
}

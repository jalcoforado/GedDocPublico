"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import {
  abrirJanelaGoogle,
  mensagemErroGoogle,
  ouvirConexaoGoogle,
  urlConexaoGoogle,
} from "@/lib/google-conexao";

interface GoogleConnectDialogProps {
  open: boolean;
  onClose: () => void;
  minutaId: number;
  processoId: number;
  /** A conta foi conectada (aviso da janela à parte). */
  onSuccess?: () => void;
  /** A aba voltou ao foco com a janela ainda pendente: vale reconferir o status. */
  onRecheck?: () => void;
}

export function GoogleConnectDialog({
  open,
  onClose,
  minutaId,
  processoId,
  onSuccess,
  onRecheck,
}: GoogleConnectDialogProps) {
  const [isConnecting, setIsConnecting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  // SI-32 — a autorização acontece numa janela à parte e esta aba NÃO sai do
  // lugar (antes, a volta do Google recarregava o processo e o diálogo de
  // redigir, com o que já tinha sido digitado, sumia). A janela avisa por
  // `BroadcastChannel` (ver `lib/google-conexao.ts`).
  useEffect(() => {
    if (!open) return;
    return ouvirConexaoGoogle((aviso) => {
      setIsConnecting(false);
      if (aviso.ok) {
        setErro(null);
        onSuccess?.();
      } else {
        setErro(mensagemErroGoogle(aviso.erro));
      }
    });
  }, [open, onSuccess]);

  // Rede de segurança: se o aviso não chegar (navegador sem o canal, janela
  // fechada no meio), ao voltar para esta aba o botão destrava e o status é
  // reconferido — conectado de fato, o diálogo de redigir segue sozinho.
  useEffect(() => {
    if (!open || !isConnecting) return;
    function aoVoltar() {
      setIsConnecting(false);
      onRecheck?.();
    }
    window.addEventListener("focus", aoVoltar);
    return () => window.removeEventListener("focus", aoVoltar);
  }, [open, isConnecting, onRecheck]);

  useEffect(() => {
    if (!open) {
      setErro(null);
      setIsConnecting(false);
    }
  }, [open]);

  function handleConnect() {
    setErro(null);
    setIsConnecting(true);
    if (!abrirJanelaGoogle(urlConexaoGoogle(minutaId, processoId, true))) {
      // Janela bloqueada pelo navegador: segue na mesma aba, como antes.
      window.location.href = urlConexaoGoogle(minutaId, processoId, false);
    }
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
            {isConnecting ? "Aguardando o Google…" : "Conectar Conta Google"}
          </Button>
        </div>
      }
    >
      {/* SI-32: o texto diz o que de fato acontece. O anterior afirmava que
          "a conta não é armazenada" — mas a autorização (token) fica guardada,
          cifrada, para o sistema abrir o documento depois. */}
      <div className="space-y-3 text-sm">
        <p>
          Uma janela do Google vai abrir para você autorizar o Aprimora a criar e editar documentos
          no seu Google Docs. Esta tela fica aberta, com o que você já preencheu.
        </p>
        {isConnecting && (
          <p className="text-foreground-muted" role="status">
            Conclua a autorização na janela do Google. Se ela não apareceu, verifique se o navegador
            bloqueou a janela.
          </p>
        )}
        {erro && (
          <div
            role="alert"
            className="rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-danger-soft-foreground"
          >
            {erro}
          </div>
        )}
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

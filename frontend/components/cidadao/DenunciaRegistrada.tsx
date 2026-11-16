"use client";

import { CheckCircle2, X } from "lucide-react";
import * as React from "react";

const CHAVE = "aprimora:cidadao:denuncia-registrada";

/** Recado para a lista de denúncias confirmar o envio (mesmo motivo de `ProtocoloRecebido`). */
export function marcarDenunciaRegistrada(): void {
  try {
    sessionStorage.setItem(CHAVE, "1");
  } catch {
    // Sem storage: fica só o toast.
  }
}

/**
 * Confirmação no topo de "Minhas denúncias" logo depois do envio: diz que
 * chegou e o que acontece agora. O toast sozinho sumia antes de ser lido.
 */
export function DenunciaRegistrada() {
  const [aberto, setAberto] = React.useState(false);

  React.useEffect(() => {
    try {
      if (sessionStorage.getItem(CHAVE)) {
        sessionStorage.removeItem(CHAVE);
        setAberto(true);
      }
    } catch {
      // idem
    }
  }, []);

  if (!aberto) return null;
  return (
    <section
      role="status"
      className="flex items-start gap-3 rounded-card border border-success/30 bg-success-soft/50 p-4 shadow-card"
    >
      <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-success-soft-foreground" aria-hidden="true" />
      <div className="min-w-0 flex-1 text-sm">
        <p className="text-base font-semibold text-foreground">Denúncia enviada. Obrigado por avisar.</p>
        <p className="mt-1 text-foreground-muted">
          A fiscalização vai apurar o que você contou. A situação aparece aqui na lista e muda de
          “Registrada” para “Em apuração” e, no fim, para o resultado.
        </p>
      </div>
      <button
        type="button"
        onClick={() => setAberto(false)}
        aria-label="Fechar aviso"
        className="-m-1 inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </section>
  );
}

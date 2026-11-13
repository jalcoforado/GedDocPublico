"use client";

import { Check, CheckCircle2, Copy } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";

const CHAVE = "aprimora:cidadao:protocolo-recebido";

/**
 * Marca o pedido recém-aberto para a tela de acompanhamento dar as boas-
 * vindas a ele. Quem abre o pedido continua indo para
 * `/cidadao/processos/<id>` (mesma rota de sempre); o recado viaja no
 * `sessionStorage` para não mudar a URL nem o fluxo — e some sozinho no
 * primeiro acesso, para não reaparecer a cada visita.
 */
export function marcarProtocoloRecebido(idProcesso: number): void {
  try {
    sessionStorage.setItem(CHAVE, String(idProcesso));
  } catch {
    // Sem storage (aba privada, bloqueio): o cidadão só não vê a faixa.
  }
}

function lerELimpar(idProcesso: number): boolean {
  try {
    if (sessionStorage.getItem(CHAVE) !== String(idProcesso)) return false;
    sessionStorage.removeItem(CHAVE);
    return true;
  } catch {
    return false;
  }
}

/**
 * Confirmação de pedido enviado: o número do protocolo em letra grande (é o
 * que a pessoa anota ou fotografa), o que acontece agora e como acompanhar.
 * O toast de antes sumia em 4 segundos levando o número junto.
 */
export function ProtocoloRecebido({ idProcesso, numero }: { idProcesso: number; numero: string }) {
  const [aberto, setAberto] = React.useState(false);
  const [copiado, setCopiado] = React.useState(false);
  const titulo = React.useRef<HTMLHeadingElement>(null);

  React.useEffect(() => {
    if (lerELimpar(idProcesso)) setAberto(true);
  }, [idProcesso]);

  // Leva o foco (e o leitor de tela) à confirmação assim que ela aparece.
  React.useEffect(() => {
    if (aberto) titulo.current?.focus();
  }, [aberto]);

  if (!aberto) return null;

  async function copiar() {
    try {
      await navigator.clipboard.writeText(numero);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 2500);
    } catch {
      // Sem permissão de área de transferência: o número continua à vista.
    }
  }

  return (
    <section
      aria-labelledby="protocolo-recebido-titulo"
      className="rounded-card border border-success/30 bg-success-soft/50 p-5 shadow-card sm:p-6"
    >
      <div className="flex items-start gap-3">
        <CheckCircle2 className="mt-0.5 h-7 w-7 shrink-0 text-success-soft-foreground" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <h2
            id="protocolo-recebido-titulo"
            ref={titulo}
            tabIndex={-1}
            className="text-lg font-semibold text-foreground focus:outline-none"
          >
            Pedido enviado! A prefeitura já recebeu.
          </h2>
          <p className="mt-1 text-sm text-foreground-muted">
            Anote ou tire um print do número abaixo. Ele identifica o seu pedido.
          </p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-border bg-card px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
          Número do protocolo
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="break-all font-mono text-2xl font-semibold tabular-nums text-foreground sm:text-3xl">
            {numero}
          </span>
          <Button type="button" variant="secondary" size="sm" onClick={copiar}>
            {copiado ? (
              <Check className="h-4 w-4" aria-hidden="true" />
            ) : (
              <Copy className="h-4 w-4" aria-hidden="true" />
            )}
            {copiado ? "Copiado" : "Copiar número"}
          </Button>
        </div>
      </div>

      <h3 className="mt-5 text-sm font-semibold text-foreground">E agora?</h3>
      <ol className="mt-2 space-y-2 text-sm text-foreground-muted">
        {[
          "Um servidor da prefeitura vai analisar o seu pedido.",
          "Se faltar algum documento ou informação, o pedido aparece aqui em “Próximos passos”, dizendo o que enviar.",
          "Para acompanhar, entre no portal quando quiser e abra “Meus processos”.",
        ].map((t, i) => (
          <li key={i} className="flex gap-3">
            <span
              aria-hidden="true"
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-card text-xs font-semibold text-foreground ring-1 ring-border"
            >
              {i + 1}
            </span>
            <span className="pt-0.5">{t}</span>
          </li>
        ))}
      </ol>

      <div className="mt-5">
        <Button type="button" variant="secondary" onClick={() => setAberto(false)}>
          Entendi
        </Button>
      </div>
    </section>
  );
}

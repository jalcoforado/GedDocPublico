"use client";

import { AlertCircle } from "lucide-react";

export interface ErroDeCampo {
  campoId: string;
  rotulo: string;
}

/**
 * Resumo no topo quando o envio esbarra em mais de um campo: diz quantos e
 * leva a cada um. Com um campo só, o foco já foi para ele e a mensagem está
 * embaixo dele — o resumo seria repetição.
 */
export function ResumoErros({ erros }: { erros: ErroDeCampo[] }) {
  if (erros.length < 2) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-foreground"
    >
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-semibold">Falta acertar {erros.length} campos:</p>
        <ul className="mt-1 space-y-0.5">
          {erros.map((e) => (
            <li key={e.campoId}>
              <a
                href={`#${e.campoId}`}
                onClick={(ev) => {
                  ev.preventDefault();
                  const el = document.getElementById(e.campoId);
                  el?.scrollIntoView({ behavior: "smooth", block: "center" });
                  el?.focus({ preventScroll: true });
                }}
                className="underline underline-offset-2 hover:no-underline"
              >
                {e.rotulo}
              </a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

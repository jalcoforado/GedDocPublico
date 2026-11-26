"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { avisarAbaDeOrigem, mensagemErroGoogle } from "@/lib/google-conexao";

/**
 * Onde a janela à parte da conexão com o Google termina (SI-32). Avisa a aba
 * de origem — que nunca saiu do lugar, com o diálogo de redigir aberto — e se
 * fecha. Se o navegador não deixar fechar, diz o que aconteceu e que já pode
 * fechar a janela. Fica fora de `app/(app)/` de propósito: numa janela
 * pequena, sem menu nem cabeçalho.
 */
export default function GoogleConectadoPage() {
  const [erro, setErro] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    // Lido de window.location (e não de useSearchParams) para não exigir
    // fronteira de Suspense — mesmo motivo da tela de login.
    const codigo = new URLSearchParams(window.location.search).get("erro");
    setErro(codigo);
    avisarAbaDeOrigem({ tipo: "google-conexao", ok: !codigo, erro: codigo });
    // Um instante para a mensagem sair antes de a janela fechar.
    const t = window.setTimeout(() => window.close(), 400);
    return () => window.clearTimeout(t);
  }, []);

  if (erro === undefined) return null;
  const ok = !erro;

  return (
    <main className="flex min-h-dvh items-center justify-center bg-background p-6">
      <div className="max-w-sm space-y-3 text-center">
        {ok ? (
          <CheckCircle2 className="mx-auto h-10 w-10 text-success" aria-hidden="true" />
        ) : (
          <XCircle className="mx-auto h-10 w-10 text-danger" aria-hidden="true" />
        )}
        <h1 className="font-display text-xl font-semibold text-foreground">
          {ok ? "Conta Google conectada" : "Não foi possível conectar"}
        </h1>
        <p className="text-sm text-foreground-muted">
          {ok
            ? "Pode fechar esta janela e voltar ao Aprimora: o documento continua de onde você parou."
            : `${mensagemErroGoogle(erro)} Pode fechar esta janela.`}
        </p>
        <button
          type="button"
          onClick={() => window.close()}
          className="mt-2 inline-flex h-10 items-center justify-center rounded-full border border-border-strong px-5 text-sm font-medium text-foreground transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Fechar janela
        </button>
      </div>
    </main>
  );
}

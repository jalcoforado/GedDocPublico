"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { MENSAGEM_ERRO_GOOGLE } from "@/lib/google-conexao";

// Mensagens compartilhadas com a janela à parte da conexão (`lib/google-conexao.ts`).
const ERROR_MESSAGES = MENSAGEM_ERRO_GOOGLE;

/** Segundos até voltar sozinho — o bastante para ler a mensagem. */
const ESPERA = 8;

export default function MinutaErrorPage() {
  const router = useRouter();
  const { error: showToast } = useToast();
  const params = useSearchParams();
  const [countdown, setCountdown] = useState(ESPERA);

  const errorCode = params.get("error");
  const errorMessage =
    ERROR_MESSAGES[errorCode || ""] || "Ocorreu um erro desconhecido.";
  // SI-32: volta para o processo de onde a conexão partiu, não para a lista.
  const processo = Number(params.get("processo"));
  const destino =
    Number.isInteger(processo) && processo > 0
      ? `/m/protocolo/processos/${processo}?tab=documentos`
      : "/m/protocolo/processos";
  const rotuloVolta = destino === "/m/protocolo/processos" ? "Voltar aos processos" : "Voltar ao processo";

  useEffect(() => {
    if (errorCode) {
      showToast(ERROR_MESSAGES[errorCode] || "Ocorreu um erro desconhecido.");
    }
  }, [errorCode, showToast]);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);
    const redirectTimer = setTimeout(() => {
      router.push(destino);
    }, ESPERA * 1000);
    return () => {
      clearInterval(timer);
      clearTimeout(redirectTimer);
    };
  }, [router, destino]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="text-center space-y-4 max-w-md">
        <h1 className="text-3xl font-bold text-foreground">
          Erro ao conectar Google Docs
        </h1>
        <p className="text-base text-foreground-muted">{errorMessage}</p>
        <p className="text-sm text-foreground-muted/70">
          Voltando em {countdown} segundo{countdown !== 1 ? "s" : ""}…
        </p>
      </div>
      <Button onClick={() => router.push(destino)} size="md">
        {rotuloVolta}
      </Button>
    </div>
  );
}

"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

const ERROR_MESSAGES: Record<string, string> = {
  access_denied: "Você rejeitou o acesso ao Google Docs. Tente novamente.",
  state_expired: "Sessão expirou. Tente conectar novamente.",
  google_api_error: "Erro ao conectar com Google. Tente novamente.",
  invalid_state: "Requisição inválida. Tente novamente.",
};

export default function MinutaErrorPage() {
  const router = useRouter();
  const { error: showToast } = useToast();
  const params = useSearchParams();
  const [countdown, setCountdown] = useState(3);

  const errorCode = params.get("error");
  const errorMessage =
    ERROR_MESSAGES[errorCode || ""] || "Ocorreu um erro desconhecido.";

  useEffect(() => {
    // Show error toast on mount
    if (errorCode) {
      showToast(ERROR_MESSAGES[errorCode] || "Ocorreu um erro desconhecido.");
    }
  }, [errorCode, showToast]);

  useEffect(() => {
    // Auto-redirect after 3 seconds
    const timer = setInterval(() => {
      setCountdown((prev) => prev - 1);
    }, 1000);

    const redirectTimer = setTimeout(() => {
      router.push("/processos");
    }, 3000);

    return () => {
      clearInterval(timer);
      clearTimeout(redirectTimer);
    };
  }, [router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="text-center space-y-4 max-w-md">
        <h1 className="text-3xl font-bold text-foreground">
          Erro ao conectar Google Docs
        </h1>
        <p className="text-base text-foreground-muted">{errorMessage}</p>
        <p className="text-sm text-foreground-muted/70">
          Redirecionando em {countdown} segundo{countdown !== 1 ? "s" : ""}…
        </p>
      </div>
      <Button onClick={() => router.push("/processos")} size="md">
        Voltar aos processos
      </Button>
    </div>
  );
}

"use client";

import { CheckCircle2, Link2 as LinkIcon } from "lucide-react";
import Link from "next/link";

import { AssinaturaAprimora } from "@/components/AssinaturaAprimora";
import { BOTAO_LOGIN } from "@/components/login/comum";
import { MarcaDoMunicipio } from "@/components/MarcaDoMunicipio";
import { cn } from "@/lib/utils";

/**
 * Moldura das telas abertas por link de e-mail (redefinir senha, convite,
 * confirmar e-mail): a marca do município, um título e o conteúdo, no mesmo
 * tom do login — a pessoa chega do e-mail e reconhece onde está.
 */
export function TelaDeConta({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <main className="flex min-h-dvh flex-col bg-background p-6 sm:p-12">
      <div className="flex flex-1 items-center justify-center">
        <div className="w-full max-w-sm motion-safe:animate-slide-up">
          <div className="flex flex-col items-center text-center">
            <MarcaDoMunicipio className="h-16" />
            <h1 className="mt-8 text-2xl font-normal text-foreground-muted">{titulo}</h1>
          </div>
          <div className="mt-6">{children}</div>
        </div>
      </div>
      <AssinaturaAprimora className="pt-8" />
    </main>
  );
}

/** Lê o `?token=` do link. Fora do React de propósito: estas telas só precisam
 * do valor uma vez, e `useSearchParams` exigiria uma fronteira de Suspense. */
export function tokenDaUrl(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("token") ?? "";
}

/** Fim do fluxo: o que aconteceu e o botão para o login certo. */
export function Concluido({
  mensagem,
  tipo,
}: {
  mensagem: string;
  tipo: "servidor" | "cidadao";
}) {
  return (
    <div className="space-y-5 text-center motion-safe:animate-slide-up">
      <span className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-full bg-success-soft text-success-soft-foreground">
        <CheckCircle2 className="h-7 w-7" aria-hidden="true" />
      </span>
      <p role="status" className="text-sm text-foreground-muted">
        {mensagem}
      </p>
      <Link
        href={tipo === "cidadao" ? "/cidadao/login" : "/login"}
        className={cn(BOTAO_LOGIN, "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow-md")}
      >
        Ir para o login
      </Link>
    </div>
  );
}

/** Link inválido, expirado ou já usado — e o caminho para pedir outro. */
export function LinkInvalido({ mensagem }: { mensagem: string }) {
  return (
    <div className="space-y-5 text-center motion-safe:animate-slide-up">
      <span className="mx-auto inline-flex h-14 w-14 items-center justify-center rounded-full bg-warning-soft text-warning-soft-foreground">
        <LinkIcon className="h-6 w-6" aria-hidden="true" />
      </span>
      <p role="alert" className="text-sm text-foreground-muted">
        {mensagem}
      </p>
      <Link
        href="/login"
        className="inline-flex rounded px-2 py-1 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
      >
        Voltar ao login e pedir um link novo
      </Link>
    </div>
  );
}

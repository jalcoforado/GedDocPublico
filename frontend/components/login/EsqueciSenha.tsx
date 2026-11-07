"use client";

import { ArrowLeft, MailCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BOTAO_LOGIN, CAMPO_LOGIN } from "@/components/login/comum";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * "Não lembro a senha" do servidor: pede o link de nova senha para o e-mail
 * da conta. A resposta é a mesma exista a conta ou não (o backend não conta
 * quem está cadastrado), então a tela também só diz "se houver, enviamos".
 */
export function EsqueciSenha({
  emailInicial,
  onVoltar,
}: {
  emailInicial: string;
  onVoltar: () => void;
}) {
  const [email, setEmail] = useState(emailInicial);
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      setEnviado((await api.conta.esqueciSenha(email.trim())).detail);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível enviar agora.");
    } finally {
      setEnviando(false);
    }
  }

  const voltar = (
    <button
      type="button"
      onClick={onVoltar}
      className="inline-flex items-center gap-1 rounded px-2 py-1 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Voltar ao login
    </button>
  );

  if (enviado) {
    return (
      <div className="mt-5 space-y-4 motion-safe:animate-slide-up">
        <div role="status" className="flex items-start gap-3 rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
          <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden="true" />
          <p>{enviado} O link vale por 1 hora.</p>
        </div>
        {voltar}
      </div>
    );
  }

  return (
    <form onSubmit={enviar} className="mt-5 space-y-4 motion-safe:animate-slide-up" noValidate>
      <p className="px-2 text-sm text-foreground-muted">
        Informe o e-mail da sua conta. Enviaremos um link para você criar uma nova senha.
      </p>
      <div>
        <label htmlFor="email-esqueci" className="sr-only">
          E-mail
        </label>
        <input
          id="email-esqueci"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="username"
          inputMode="email"
          placeholder="E-mail"
          required
          autoFocus
          className={CAMPO_LOGIN}
        />
      </div>
      {erro && (
        <div role="alert" className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground">
          {erro}
        </div>
      )}
      <button
        type="submit"
        disabled={enviando || !email.includes("@")}
        className={cn(BOTAO_LOGIN, "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow-md")}
      >
        {enviando ? "Enviando..." : "Enviar link"}
      </button>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {voltar}
        <Link
          href="/cidadao/login?esqueci=1"
          className="rounded px-2 py-1 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          Sou solicitante (cidadão)
        </Link>
      </div>
    </form>
  );
}

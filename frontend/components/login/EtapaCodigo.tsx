"use client";

import { ArrowLeft, MailCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { BOTAO_LOGIN, CAMPO_LOGIN } from "@/components/login/comum";
import { type LoginResponse, api } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Espera entre dois pedidos de código — o backend recusa antes disso. */
const ESPERA_REENVIO = 60;

/**
 * Segundo passo do login do servidor: o código de 6 dígitos que chegou por
 * e-mail (2FA, migration 0136). Sem o código não há sessão — o passo da
 * senha só devolveu um `desafio`.
 */
export function EtapaCodigo({
  desafio: desafioInicial,
  emailMascarado,
  onEntrou,
  onVoltar,
}: {
  desafio: string;
  emailMascarado: string | null;
  onEntrou: (r: LoginResponse) => void;
  onVoltar: () => void;
}) {
  const [desafio, setDesafio] = useState(desafioInicial);
  const [codigo, setCodigo] = useState("");
  const [lembrar, setLembrar] = useState(true);
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [espera, setEspera] = useState(ESPERA_REENVIO);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => campo.current?.focus(), []);
  useEffect(() => {
    if (espera <= 0) return;
    const t = setTimeout(() => setEspera((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [espera]);

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      onEntrou(await api.conta.login2fa(desafio, codigo, lembrar));
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível conferir o código.");
      setCodigo("");
      campo.current?.focus();
    } finally {
      setEnviando(false);
    }
  }

  async function reenviar() {
    setErro(null);
    setAviso(null);
    try {
      const r = await api.conta.reenviarCodigo(desafio);
      if (r.desafio) setDesafio(r.desafio);
      setAviso("Enviamos um código novo. O anterior deixou de valer.");
      setEspera(ESPERA_REENVIO);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível reenviar o código.");
    }
  }

  return (
    <form onSubmit={confirmar} className="mt-5 space-y-4 motion-safe:animate-slide-up" noValidate>
      <div className="flex items-start gap-3 rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
        <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand" aria-hidden="true" />
        <p>
          Enviamos um código de 6 dígitos para{" "}
          <strong className="font-medium text-foreground">{emailMascarado ?? "o seu e-mail"}</strong>.
          Ele vale por 10 minutos.
        </p>
      </div>

      <div>
        <label htmlFor="codigo" className="sr-only">
          Código de verificação
        </label>
        <input
          ref={campo}
          id="codigo"
          value={codigo}
          onChange={(e) => setCodigo(e.target.value.replace(/\D/g, "").slice(0, 6))}
          inputMode="numeric"
          autoComplete="one-time-code"
          placeholder="000000"
          maxLength={6}
          required
          className={cn(CAMPO_LOGIN, "text-center font-mono text-2xl tracking-[0.5em] placeholder:tracking-[0.5em]")}
        />
      </div>

      <label className="flex cursor-pointer items-center gap-2 px-4 text-sm text-foreground-muted">
        <input
          type="checkbox"
          checked={lembrar}
          onChange={(e) => setLembrar(e.target.checked)}
          className="h-4 w-4 rounded border-border-strong accent-brand"
        />
        Lembrar este computador por 30 dias
      </label>

      {erro && (
        <div
          role="alert"
          className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground"
        >
          {erro}
        </div>
      )}
      {aviso && (
        <p role="status" className="px-4 text-sm text-success-soft-foreground">
          {aviso}
        </p>
      )}

      <button
        type="submit"
        disabled={enviando || codigo.length !== 6}
        className={cn(BOTAO_LOGIN, "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow-md")}
      >
        {enviando ? "Conferindo..." : "Entrar"}
      </button>

      <div className="flex items-center justify-between px-2 text-sm">
        <button
          type="button"
          onClick={onVoltar}
          className="inline-flex items-center gap-1 rounded px-2 py-1 text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Voltar
        </button>
        <button
          type="button"
          onClick={reenviar}
          disabled={espera > 0}
          className="rounded px-2 py-1 text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-transparent"
        >
          {espera > 0 ? `Reenviar código em ${espera}s` : "Reenviar código"}
        </button>
      </div>
    </form>
  );
}

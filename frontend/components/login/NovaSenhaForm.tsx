"use client";

import { useState } from "react";

import { BOTAO_LOGIN, CAMPO_SENHA_LOGIN } from "@/components/login/comum";
import { PasswordInput } from "@/components/ui/password-input";
import { cn } from "@/lib/utils";

/** Mesmo piso do backend (`auth/password.py::SENHA_MINIMA`). */
export const SENHA_MINIMA = 8;

/**
 * Escolher a senha (redefinição ou aceite de convite): senha + confirmação,
 * conferidas aqui antes de ir ao servidor.
 */
export function NovaSenhaForm({
  rotuloBotao,
  onSalvar,
}: {
  rotuloBotao: string;
  onSalvar: (senha: string) => Promise<void>;
}) {
  const [senha, setSenha] = useState("");
  const [confirma, setConfirma] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const curta = senha.length > 0 && senha.length < SENHA_MINIMA;
  const diferente = confirma.length > 0 && confirma !== senha;

  async function salvar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await onSalvar(senha);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível salvar a senha.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={salvar} className="space-y-3.5" noValidate>
      <div>
        <label htmlFor="nova-senha" className="sr-only">
          Nova senha
        </label>
        <PasswordInput
          id="nova-senha"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          autoComplete="new-password"
          placeholder="Nova senha"
          autoFocus
          className={CAMPO_SENHA_LOGIN}
        />
        <p className={cn("mt-1.5 px-4 text-xs", curta ? "text-danger-soft-foreground" : "text-foreground-subtle")}>
          Pelo menos {SENHA_MINIMA} caracteres.
        </p>
      </div>
      <div>
        <label htmlFor="confirma-senha" className="sr-only">
          Repita a nova senha
        </label>
        <PasswordInput
          id="confirma-senha"
          value={confirma}
          onChange={(e) => setConfirma(e.target.value)}
          autoComplete="new-password"
          placeholder="Repita a nova senha"
          className={CAMPO_SENHA_LOGIN}
        />
        {diferente && (
          <p className="mt-1.5 px-4 text-xs text-danger-soft-foreground">As duas senhas não são iguais.</p>
        )}
      </div>
      {erro && (
        <div role="alert" className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground">
          {erro}
        </div>
      )}
      <button
        type="submit"
        disabled={enviando || senha.length < SENHA_MINIMA || senha !== confirma}
        className={cn(BOTAO_LOGIN, "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow-md")}
      >
        {enviando ? "Salvando..." : rotuloBotao}
      </button>
    </form>
  );
}

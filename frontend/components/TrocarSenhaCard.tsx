"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, Circle } from "lucide-react";
import { useRef, useState } from "react";
import { flushSync } from "react-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { PasswordInput } from "@/components/ui/password-input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { SENHA_MINIMA } from "@/lib/senha";
import { cn } from "@/lib/utils";

interface TrocarSenhaCardProps {
  /** SEC-1 Commit 5 — callback executado após a troca bem-sucedida.
   * Útil em fluxos onde a troca de senha é pré-requisito (ex:
   * /alterar-senha-obrigatoria, que redireciona para /home depois). */
  onSuccess?: () => void;
  /** Mensagem customizada do toast de sucesso. Padrão: foco em assinatura. */
  successMessage?: string;
}

type Campo = "atual" | "nova" | "confirma";

/** Um item da lista de regras, marcado ao vivo conforme a pessoa digita. */
function Regra({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  const Icone = ok ? CheckCircle2 : Circle;
  return (
    <li className={cn("flex items-center gap-1.5", ok ? "text-success-soft-foreground" : "text-foreground-muted")}>
      <Icone className={cn("h-3.5 w-3.5 shrink-0", ok ? "text-success" : "text-foreground-subtle")} aria-hidden="true" />
      {children}
      <span className="sr-only">{ok ? " — atendida" : " — pendente"}</span>
    </li>
  );
}

export function TrocarSenhaCard({
  onSuccess,
  successMessage,
}: TrocarSenhaCardProps = {}) {
  const toast = useToast();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const [err, setErr] = useState<string | null>(null);
  // Erros só depois da tentativa: campo visitado ou envio tentado.
  const [tocados, setTocados] = useState<Set<Campo>>(new Set());
  const [tentou, setTentou] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const m = useMutation({
    mutationFn: () => api.alterarSenha(atual, nova),
    onSuccess: () => {
      toast.success(
        successMessage ?? "Senha alterada. Você já pode assinar normalmente.",
      );
      setAtual("");
      setNova("");
      setConfirma("");
      setErr(null);
      setTocados(new Set());
      setTentou(false);
      onSuccess?.();
    },
    onError: (e: Error) => setErr(e.message),
  });

  // As regras que a tela conhece. A de tamanho é cópia de conveniência do
  // backend (`lib/senha.ts`); a barreira real continua sendo o 422 dele.
  const tamanhoOk = nova.length >= SENHA_MINIMA;
  const confereOk = nova !== "" && nova === confirma;

  const erros: Partial<Record<Campo, string>> = {};
  if (!atual) erros.atual = "Informe a senha que você usa hoje.";
  if (!nova) erros.nova = "Escolha a nova senha.";
  else if (!tamanhoOk)
    erros.nova = `A nova senha deve ter ao menos ${SENHA_MINIMA} caracteres.`;
  if (!confirma) erros.confirma = "Digite a nova senha mais uma vez.";
  else if (nova !== confirma) erros.confirma = "A confirmação não confere com a nova senha.";
  const erroVisivel = (c: Campo) => (tentou || tocados.has(c) ? erros[c] : undefined);
  const tocar = (c: Campo) => () => setTocados((s) => (s.has(c) ? s : new Set(s).add(c)));

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (Object.keys(erros).length > 0) {
      flushSync(() => setTentou(true));
      focarPrimeiroInvalido(formRef.current ?? document);
      return;
    }
    m.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trocar senha</CardTitle>
        <CardDescription>
          Atualize sua senha para o padrão atual de segurança. É necessário para assinar
          documentos.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form ref={formRef} onSubmit={submit} noValidate className="max-w-sm space-y-4">
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
          <FormField label="Senha atual" required error={erroVisivel("atual")}>
            <PasswordInput
              id="senha-atual"
              autoComplete="current-password"
              value={atual}
              onChange={(e) => setAtual(e.target.value)}
              onBlur={tocar("atual")}
            />
          </FormField>
          <FormField label="Nova senha" required error={erroVisivel("nova")}>
            <PasswordInput
              id="senha-nova"
              autoComplete="new-password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              onBlur={tocar("nova")}
              aria-describedby="senha-regras"
            />
          </FormField>
          <FormField label="Confirmar nova senha" required error={erroVisivel("confirma")}>
            <PasswordInput
              id="senha-confirma"
              autoComplete="new-password"
              value={confirma}
              onChange={(e) => setConfirma(e.target.value)}
              onBlur={tocar("confirma")}
            />
          </FormField>
          {/* Lista viva: cada regra se marca enquanto a pessoa digita, em vez
              de ela descobrir a regra só no erro. */}
          <ul
            id="senha-regras"
            aria-label="Regras da nova senha"
            className="space-y-1 rounded-lg border border-border bg-surface-1 px-3 py-2 text-xs"
          >
            <Regra ok={tamanhoOk}>Pelo menos {SENHA_MINIMA} caracteres</Regra>
            <Regra ok={confereOk}>A confirmação é igual à nova senha</Regra>
          </ul>
          <Button type="submit" loading={m.isPending}>
            {m.isPending ? "Salvando…" : "Alterar senha"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

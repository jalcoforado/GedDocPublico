"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

export function TrocarSenhaCard() {
  const toast = useToast();
  const [atual, setAtual] = useState("");
  const [nova, setNova] = useState("");
  const [confirma, setConfirma] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () => api.alterarSenha(atual, nova),
    onSuccess: () => {
      toast.success("Senha alterada. Você já pode assinar normalmente.");
      setAtual("");
      setNova("");
      setConfirma("");
      setErr(null);
    },
    onError: (e: Error) => setErr(e.message),
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (nova.length < 6) return setErr("A nova senha deve ter ao menos 6 caracteres.");
    if (nova !== confirma) return setErr("A confirmação não confere com a nova senha.");
    m.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Segurança</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">
          Atualize sua senha para o padrão atual de segurança. É necessário para
          assinar documentos.
        </p>
        <form onSubmit={submit} className="max-w-sm space-y-3">
          <div>
            <Label htmlFor="senha-atual" required>
              Senha atual
            </Label>
            <PasswordInput
              id="senha-atual"
              autoComplete="current-password"
              value={atual}
              onChange={(e) => setAtual(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="senha-nova" required>
              Nova senha
            </Label>
            <PasswordInput
              id="senha-nova"
              autoComplete="new-password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              required
            />
          </div>
          <div>
            <Label htmlFor="senha-confirma" required>
              Confirmar nova senha
            </Label>
            <PasswordInput
              id="senha-confirma"
              autoComplete="new-password"
              value={confirma}
              onChange={(e) => setConfirma(e.target.value)}
              required
            />
          </div>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
          <Button type="submit" disabled={m.isPending}>
            {m.isPending ? "Salvando..." : "Alterar senha"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

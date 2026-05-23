"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { api } from "@/lib/api";

const DEV = process.env.NODE_ENV !== "production";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState(DEV ? "admin@local.test" : "");
  const [senha, setSenha] = useState(DEV ? "admin123" : "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.login(email, senha);
      router.push("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao autenticar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-gradient-to-br from-aprimora to-aprimora-light p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Aprimora</CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Sistema de gestão de processos
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            <div>
              <Label htmlFor="email" required>
                E-mail
              </Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                inputMode="email"
                required
              />
            </div>
            <div>
              <Label htmlFor="senha" required>
                Senha
              </Label>
              <PasswordInput
                id="senha"
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                autoComplete="current-password"
                required
              />
            </div>
            {error && (
              <div
                role="alert"
                className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
              >
                {error}
              </div>
            )}
            <Button type="submit" disabled={loading} size="lg" className="w-full">
              {loading ? "Entrando..." : "Entrar"}
            </Button>
            {DEV && (
              <p className="text-center text-xs text-muted-foreground">
                Dev: credenciais pré-preenchidas
              </p>
            )}
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

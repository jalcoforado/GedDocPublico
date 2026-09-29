"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { api, govbrLoginUrl } from "@/lib/api";

const DESTINO = "/cidadao/processos";

/**
 * Por que o login gov.br voltou para cá (`?govbr=<motivo>`, posto pelo backend
 * em `auth_govbr._erro`). Só rótulos conhecidos viram texto — o valor da URL
 * nunca é exibido.
 */
const MOTIVO_GOVBR: Record<string, string> = {
  cancelado: "O login pelo gov.br foi cancelado. Tente de novo ou entre com CPF e senha.",
  inativo: "Seu cadastro está inativo. Procure o atendimento da prefeitura.",
  indisponivel: "O login pelo gov.br está indisponível no momento. Entre com CPF e senha.",
  falhou: "Não foi possível concluir o login pelo gov.br. Tente de novo.",
};

export default function CidadaoLoginPage() {
  const router = useRouter();
  const [cpf, setCpf] = useState("");
  const [senha, setSenha] = useState("");
  const [err, setErr] = useState<string | null>(null);

  // Lido de window.location (e não de useSearchParams) para não exigir
  // fronteira de Suspense — mesmo motivo do login dos servidores.
  useEffect(() => {
    const motivo = new URLSearchParams(window.location.search).get("govbr");
    if (motivo && motivo in MOTIVO_GOVBR) setErr(MOTIVO_GOVBR[motivo]);
  }, []);

  const govbrQ = useQuery({
    queryKey: ["govbr-disponivel"],
    queryFn: () => api.cidadao.govbrDisponivel(),
    staleTime: 5 * 60_000,
  });

  const m = useMutation({
    mutationFn: () => api.cidadao.login(cpf, senha),
    onSuccess: () => router.push(DESTINO),
    onError: (e: Error) => setErr(e.message),
  });

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <CardHeader>
          <CardTitle>Entrar</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setErr(null);
              m.mutate();
            }}
            className="space-y-3"
            noValidate
          >
            <div>
              <Label htmlFor="cpf" required>
                CPF ou CNPJ
              </Label>
              <Input
                id="cpf"
                value={cpf}
                onChange={(e) => setCpf(e.target.value)}
                placeholder="Apenas números ou com pontuação"
                autoComplete="username"
                inputMode="numeric"
                required
                autoFocus
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
            {err && (
              <div
                role="alert"
                className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
              >
                {err}
              </div>
            )}
            <Button type="submit" disabled={m.isPending} size="lg" className="w-full">
              {m.isPending ? "Entrando..." : "Entrar"}
            </Button>
          </form>
          {govbrQ.data?.disponivel && (
            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
                ou
                <span className="h-px flex-1 bg-border" aria-hidden="true" />
              </div>
              <a
                href={govbrLoginUrl(DESTINO)}
                className="flex h-11 w-full items-center justify-center rounded-md border border-border bg-card text-sm font-medium text-foreground hover:bg-muted"
              >
                Entrar com gov.br
              </a>
            </div>
          )}
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Ainda não tem cadastro?{" "}
            <Link
              href="/cidadao/cadastrar"
              className="font-medium text-primary hover:underline"
            >
              Cadastre-se
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

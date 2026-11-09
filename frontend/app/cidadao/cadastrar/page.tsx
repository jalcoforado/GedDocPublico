"use client";

import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { api } from "@/lib/api";
import { SENHA_MINIMA } from "@/lib/senha";

export default function CidadaoCadastrarPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    cpf_cnpj: "",
    nome: "",
    email: "",
    senha: "",
    telefone: "",
    telefone_whatsapp: false,
  });
  const [err, setErr] = useState<string | null>(null);

  const cadastrar = useMutation({
    mutationFn: () =>
      api.cidadao.cadastrar({
        cpf_cnpj: form.cpf_cnpj,
        nome: form.nome,
        email: form.email,
        senha: form.senha,
        telefone: form.telefone || undefined,
        telefone_whatsapp: form.telefone_whatsapp,
      }),
    // 0137 — com a conta por e-mail ligada, o cadastro só entra depois de o
    // e-mail ser confirmado: a tela pede para abrir o link. Desligada, ele já
    // nasce confirmado e entra direto, como antes.
    onSuccess: async (me) => {
      if (!me.email_verificado_em) {
        setCadastrado(true);
        return;
      }
      try {
        await api.cidadao.login(form.cpf_cnpj, form.senha);
        router.push("/cidadao/processos");
      } catch {
        router.push("/cidadao/login");
      }
    },
    onError: (e: Error) => setErr(e.message),
  });
  const [cadastrado, setCadastrado] = useState(false);
  const [reenvio, setReenvio] = useState<string | null>(null);

  if (cadastrado) {
    return (
      <div className="mx-auto max-w-md">
        <Card>
          <CardHeader>
            <CardTitle>Confirme o seu e-mail</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-foreground-muted">
            <div className="flex items-start gap-3 rounded-md border border-border bg-surface-2 px-4 py-3">
              <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand" aria-hidden="true" />
              <p>
                Enviamos um link para <strong className="font-medium text-foreground">{form.email}</strong>.
                Abra-o para ativar o cadastro — depois disso você já pode entrar.
              </p>
            </div>
            <p>Não chegou? Confira o spam ou peça outro link (um por minuto).</p>
            {reenvio && <p role="status" className="text-success-soft-foreground">{reenvio}</p>}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                onClick={async () => setReenvio((await api.cidadao.reenviarConfirmacao(form.cpf_cnpj)).detail)}
              >
                Reenviar link
              </Button>
              <Button asChild>
                <Link href="/cidadao/login">Ir para o login</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <CardHeader>
          <CardTitle>Criar conta</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setErr(null);
              cadastrar.mutate();
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
                value={form.cpf_cnpj}
                onChange={(e) => setForm({ ...form, cpf_cnpj: e.target.value })}
                autoComplete="username"
                inputMode="numeric"
                required
              />
            </div>
            <div>
              <Label htmlFor="nome" required>
                Nome completo
              </Label>
              <Input
                id="nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                autoComplete="name"
                required
                minLength={2}
              />
            </div>
            <div>
              <Label htmlFor="email" required>
                E-mail
              </Label>
              <Input
                id="email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                autoComplete="email"
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
                value={form.senha}
                onChange={(e) => setForm({ ...form, senha: e.target.value })}
                autoComplete="new-password"
                required
                minLength={SENHA_MINIMA}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Mínimo {SENHA_MINIMA} caracteres.
              </p>
            </div>
            <div>
              <Label htmlFor="tel">Telefone (opcional)</Label>
              <Input
                id="tel"
                type="tel"
                value={form.telefone}
                onChange={(e) => setForm({ ...form, telefone: e.target.value })}
                autoComplete="tel"
                inputMode="tel"
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.telefone_whatsapp}
                onChange={(e) =>
                  setForm({ ...form, telefone_whatsapp: e.target.checked })
                }
              />
              Telefone tem WhatsApp
            </label>
            {err && (
              <div
                role="alert"
                className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
              >
                {err}
              </div>
            )}
            <Button
              type="submit"
              disabled={cadastrar.isPending}
              size="lg"
              className="w-full"
            >
              {cadastrar.isPending ? "Cadastrando..." : "Criar conta"}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Já tem conta?{" "}
            <Link
              href="/cidadao/login"
              className="font-medium text-primary hover:underline"
            >
              Entrar
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

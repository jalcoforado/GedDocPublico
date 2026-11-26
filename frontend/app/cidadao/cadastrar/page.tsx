"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Circle, MailCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { mascararDocumento, erroDoDocumento } from "@/components/cidadao/documento";
import { ResumoErros } from "@/components/cidadao/ResumoErros";
import { useErrosDepoisDaTentativa } from "@/components/cidadao/useErrosDepoisDaTentativa";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { api } from "@/lib/api";
import { aplicarMascara, emailValido, soDigitos } from "@/lib/mascaras";
import { SENHA_MINIMA } from "@/lib/senha";
import { cn } from "@/lib/utils";

type Campo = "nome" | "cpf_cnpj" | "email" | "telefone" | "senha";

const ROTULO: Record<Campo, string> = {
  nome: "Nome completo",
  cpf_cnpj: "CPF ou CNPJ",
  email: "E-mail",
  telefone: "Telefone",
  senha: "Senha",
};

export default function CidadaoCadastrarPage() {
  const router = useRouter();
  const formRef = useRef<HTMLFormElement>(null);
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
    // O backend guarda e procura o documento só com os números; a máscara é
    // só da tela (e o CNPJ pontuado passaria do limite de 14 caracteres).
    mutationFn: () =>
      api.cidadao.cadastrar({
        cpf_cnpj: soDigitos(form.cpf_cnpj),
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
        await api.cidadao.login(soDigitos(form.cpf_cnpj), form.senha);
        router.push("/cidadao/processos");
      } catch {
        router.push("/cidadao/login");
      }
    },
    onError: (e: Error) => setErr(e.message),
  });
  const [cadastrado, setCadastrado] = useState(false);
  const [reenvio, setReenvio] = useState<string | null>(null);
  const [reenviando, setReenviando] = useState(false);

  const senhaOk = form.senha.length >= SENHA_MINIMA;
  const telefoneDigitos = soDigitos(form.telefone).length;
  const erros: Record<Campo, string | null> = {
    nome: form.nome.trim().length < 2 ? "Digite o seu nome completo." : null,
    cpf_cnpj: erroDoDocumento(form.cpf_cnpj, true),
    email: !form.email.trim()
      ? "Digite o seu e-mail. É para ele que mandamos os avisos."
      : !emailValido(form.email)
        ? "Confira o e-mail: ele precisa ter @ e terminar como em maria@gmail.com."
        : null,
    telefone:
      telefoneDigitos > 0 && !aplicarMascara("telefone", form.telefone).completo
        ? "Telefone incompleto. Digite o DDD e o número, como (85) 99999-8888."
        : null,
    senha: senhaOk ? null : `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`,
  };
  const v = useErrosDepoisDaTentativa(erros);
  const errosVisiveis = (Object.keys(erros) as Campo[])
    .filter((c) => v.erro(c))
    .map((c) => ({ campoId: `cad-${c}`, rotulo: ROTULO[c] }));

  if (cadastrado) {
    return (
      <div className="mx-auto max-w-md">
        <Card>
          <CardHeader>
            <MailCheck className="h-8 w-8 text-brand" aria-hidden="true" />
            <h1 className="mt-2 text-xl font-semibold tracking-tight text-titulo">Falta só confirmar o seu e-mail</h1>
            <CardDescription>
              Enviamos um link para <strong className="font-medium text-foreground">{form.email}</strong>.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-foreground-muted">
            <ol className="space-y-2">
              {[
                "Abra o seu e-mail (no celular ou no computador).",
                "Procure a mensagem da prefeitura e toque no link.",
                "Pronto: volte aqui e entre com o seu CPF e a senha.",
              ].map((t, i) => (
                <li key={i} className="flex gap-3">
                  <span
                    aria-hidden="true"
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-foreground"
                  >
                    {i + 1}
                  </span>
                  <span className="pt-0.5">{t}</span>
                </li>
              ))}
            </ol>
            <p>Não chegou? Olhe também a caixa de spam. Se não estiver lá, peça outro link (um por minuto).</p>
            {reenvio && (
              <p role="status" className="text-success-soft-foreground">
                {reenvio}
              </p>
            )}
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button
                variant="secondary"
                loading={reenviando}
                onClick={async () => {
                  setReenviando(true);
                  try {
                    setReenvio((await api.cidadao.reenviarConfirmacao(soDigitos(form.cpf_cnpj))).detail);
                  } finally {
                    setReenviando(false);
                  }
                }}
              >
                Mandar o link de novo
              </Button>
              <Button asChild>
                <Link href="/cidadao/login">Ir para a tela de entrar</Link>
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
          <h1 className="text-xl font-semibold tracking-tight text-titulo">Criar sua conta</h1>
          <CardDescription>
            Com a conta você faz pedidos à prefeitura pela internet e acompanha cada um deles.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form
            ref={formRef}
            onSubmit={(e) => {
              e.preventDefault();
              setErr(null);
              if (!v.tentar()) {
                setTimeout(() => focarPrimeiroInvalido(formRef.current ?? document), 0);
                return;
              }
              cadastrar.mutate();
            }}
            className="space-y-4"
            noValidate
          >
            <ResumoErros erros={errosVisiveis} />

            <FormField label="Nome completo" required error={v.erro("nome")}>
              <Input
                id="cad-nome"
                value={form.nome}
                onChange={(e) => setForm({ ...form, nome: e.target.value })}
                onBlur={v.sair("nome")}
                autoComplete="name"
                autoCapitalize="words"
                placeholder="Ex.: Maria da Silva Souza"
              />
            </FormField>

            <FormField
              label="CPF ou CNPJ"
              required
              error={v.erro("cpf_cnpj")}
              hint="Digite só os números — os pontos entram sozinhos. Use o CNPJ se for empresa."
            >
              <Input
                id="cad-cpf_cnpj"
                value={form.cpf_cnpj}
                onChange={(e) => setForm({ ...form, cpf_cnpj: mascararDocumento(e.target.value) })}
                onBlur={v.sair("cpf_cnpj")}
                autoComplete="username"
                inputMode="numeric"
                placeholder="Ex.: 123.456.789-09"
                className="tabular-nums"
              />
            </FormField>

            <FormField
              label="E-mail"
              required
              error={v.erro("email")}
              hint="Usamos para avisar do andamento e para recuperar a senha."
            >
              <Input
                id="cad-email"
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                onBlur={v.sair("email")}
                autoComplete="email"
                inputMode="email"
                autoCapitalize="none"
                placeholder="Ex.: maria@gmail.com"
              />
            </FormField>

            <div className="space-y-2">
              <FormField
                label="Telefone"
                opcional
                error={v.erro("telefone")}
                hint="Com DDD. Se a prefeitura precisar falar com você."
              >
                <Input
                  id="cad-telefone"
                  type="tel"
                  value={form.telefone}
                  onChange={(e) => setForm({ ...form, telefone: aplicarMascara("telefone", e.target.value).valor })}
                  onBlur={v.sair("telefone")}
                  autoComplete="tel-national"
                  inputMode="tel"
                  placeholder="Ex.: (85) 99999-8888"
                  className="tabular-nums"
                />
              </FormField>
              <label className="flex min-h-11 cursor-pointer items-center gap-3 text-sm text-foreground">
                <Checkbox
                  checked={form.telefone_whatsapp}
                  onChange={(e) => setForm({ ...form, telefone_whatsapp: e.target.checked })}
                />
                Este número tem WhatsApp
              </label>
            </div>

            <FormField
              label="Crie uma senha"
              required
              error={v.erro("senha")}
              hint={
                <span
                  className={cn(
                    "inline-flex items-center gap-1.5",
                    senhaOk && "font-medium text-success-soft-foreground",
                  )}
                >
                  {senhaOk ? (
                    <Check className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <Circle className="h-3 w-3" aria-hidden="true" />
                  )}
                  Pelo menos {SENHA_MINIMA} caracteres
                </span>
              }
            >
              <PasswordInput
                id="cad-senha"
                value={form.senha}
                onChange={(e) => setForm({ ...form, senha: e.target.value })}
                onBlur={v.sair("senha")}
                autoComplete="new-password"
              />
            </FormField>

            {err && <Alert intent="danger">{err}</Alert>}

            <Button type="submit" loading={cadastrar.isPending} size="lg" className="w-full">
              {cadastrar.isPending ? "Criando a conta…" : "Criar conta"}
            </Button>
          </form>
          <p className="mt-5 text-center text-sm text-foreground-muted">
            Já tem conta?{" "}
            <Link href="/cidadao/login" className="font-medium text-primary underline-offset-2 hover:underline">
              Entrar
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

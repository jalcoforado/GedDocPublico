"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  AtalhosPublicos,
  BOTAO_LOGIN,
  CAMPO_LOGIN,
  CAMPO_SENHA_LOGIN,
} from "@/components/login/comum";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { cn } from "@/lib/utils";
import { ApiError, api, govbrLoginUrl } from "@/lib/api";

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

  // 403 no login = senha certa, e-mail do cadastro ainda não confirmado
  // (0136): a tela oferece o reenvio do link em vez de só mostrar o erro.
  const [naoConfirmado, setNaoConfirmado] = useState(false);
  const [esqueci, setEsqueci] = useState(false);
  const [aviso, setAviso] = useState<string | null>(null);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("esqueci")) setEsqueci(true);
  }, []);

  const m = useMutation({
    mutationFn: () => api.cidadao.login(cpf, senha),
    onSuccess: () => router.push(DESTINO),
    onError: (e: Error) => {
      setNaoConfirmado(e instanceof ApiError && e.status === 403);
      setErr(e.message);
    },
  });

  const pedirLink = useMutation({
    mutationFn: () => (esqueci ? api.cidadao.esqueciSenha(cpf) : api.cidadao.reenviarConfirmacao(cpf)),
    onSuccess: (r) => {
      setErr(null);
      setAviso(r.detail);
    },
    onError: (e: Error) => setErr(e.message),
  });

  if (esqueci) {
    return (
      <div className="mx-auto w-full max-w-sm pt-4 motion-safe:animate-slide-up">
        <h1 className="text-center text-2xl font-normal text-foreground-muted">Nova senha</h1>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setAviso(null);
            pedirLink.mutate();
          }}
          className="mt-6 space-y-4"
          noValidate
        >
          <p className="px-2 text-sm text-foreground-muted">
            Informe o CPF ou CNPJ do cadastro. Enviaremos um link para o e-mail cadastrado.
          </p>
          <div>
            <Label htmlFor="cpf-esqueci" required className="px-2">
              CPF ou CNPJ
            </Label>
            <input
              id="cpf-esqueci"
              value={cpf}
              onChange={(e) => setCpf(e.target.value)}
              inputMode="numeric"
              autoComplete="username"
              autoFocus
              className={CAMPO_LOGIN}
            />
          </div>
          {aviso && (
            <p role="status" className="rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
              {aviso} O link vale por 1 hora.
            </p>
          )}
          {err && (
            <div role="alert" className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
          <button
            type="submit"
            disabled={pedirLink.isPending || cpf.replace(/\D/g, "").length < 11}
            className={cn(BOTAO_LOGIN, "bg-primary text-primary-foreground shadow-sm hover:opacity-90 hover:shadow-md")}
          >
            {pedirLink.isPending ? "Enviando..." : "Enviar link"}
          </button>
          <button
            type="button"
            onClick={() => {
              setEsqueci(false);
              setAviso(null);
              setErr(null);
            }}
            className="rounded px-2 py-1 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
          >
            Voltar ao login
          </button>
        </form>
      </div>
    );
  }

  // Mesma linguagem do login do servidor (campos e botões em pílula, título
  // leve), sem o cartão. Os rótulos ficam VISÍVEIS aqui, ao contrário de lá:
  // o público desta tela é qualquer cidadão, e texto de preenchimento some
  // quando se começa a digitar.
  return (
    <div className="mx-auto w-full max-w-sm pt-4 motion-safe:animate-slide-up">
      <h1 className="text-center text-2xl font-normal text-foreground-muted">Entrar</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setErr(null);
          m.mutate();
        }}
        className="mt-6 space-y-4"
        noValidate
      >
        <div>
          <Label htmlFor="cpf" required className="px-2">
            CPF ou CNPJ
          </Label>
          <input
            id="cpf"
            value={cpf}
            onChange={(e) => setCpf(e.target.value)}
            placeholder="Apenas números ou com pontuação"
            autoComplete="username"
            inputMode="numeric"
            required
            autoFocus
            className={CAMPO_LOGIN}
          />
        </div>
        <div>
          <Label htmlFor="senha" required className="px-2">
            Senha
          </Label>
          <PasswordInput
            id="senha"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
            className={CAMPO_SENHA_LOGIN}
          />
        </div>
        <div className="flex justify-end px-2">
          <button
            type="button"
            onClick={() => {
              setErr(null);
              setEsqueci(true);
            }}
            className="-mx-1.5 rounded px-1.5 py-0.5 text-sm text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground"
          >
            Esqueci minha senha
          </button>
        </div>
        {err && (
          <div
            role="alert"
            className="rounded-2xl border border-danger/30 bg-danger-soft px-4 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
            {naoConfirmado && (
              <button
                type="button"
                onClick={() => pedirLink.mutate()}
                disabled={pedirLink.isPending}
                className="mt-2 block font-medium underline underline-offset-2"
              >
                Reenviar o e-mail de confirmação
              </button>
            )}
          </div>
        )}
        {aviso && !err && (
          <p role="status" className="rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
            {aviso}
          </p>
        )}
        <button
          type="submit"
          disabled={m.isPending}
          className={cn(
            BOTAO_LOGIN,
            "bg-primary text-primary-foreground shadow-sm hover:opacity-90 hover:shadow-md",
          )}
        >
          {m.isPending ? "Entrando..." : "Entrar"}
        </button>
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
            className={cn(
              BOTAO_LOGIN,
              "border border-border-strong text-foreground hover:bg-muted",
            )}
          >
            Entrar com gov.br
          </a>
        </div>
      )}

      <p className="mt-6 px-2 text-sm text-foreground-muted">
        Ainda não tem cadastro?{" "}
        <Link
          href="/cidadao/cadastrar"
          className="font-semibold text-primary underline-offset-2 hover:underline"
        >
          Cadastre-se
        </Link>
      </p>

      <AtalhosPublicos className="mt-8" />
    </div>
  );
}

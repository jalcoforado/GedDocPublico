"use client";

import { googleLoginUrl } from "@/lib/api";
import { destinoDaQuery } from "@/lib/destino-login";
import { cn } from "@/lib/utils";

import { BOTAO_LOGIN } from "./comum";

/**
 * Por que o login com o Google voltou para a tela de login (`?google=<motivo>`,
 * posto pelo backend em `auth_google_login._voltar_ao_login`). Só rótulos
 * conhecidos viram texto — o valor da URL nunca é exibido.
 */
export const MOTIVO_GOOGLE: Record<string, string> = {
  cancelado: "O login com o Google foi cancelado. Tente de novo ou entre com e-mail e senha.",
  sem_conta:
    "Esta conta Google não é de um usuário desta prefeitura. Entre com e-mail e senha ou peça acesso ao administrador.",
  nao_ativada: "Conta ainda não ativada. Abra o link do convite que enviamos para o seu e-mail.",
  email_nao_verificado:
    "O e-mail desta conta Google não foi confirmado no Google. Entre com e-mail e senha.",
  expirou: "O login com o Google demorou demais. Tente de novo.",
  indisponivel: "O login com o Google não está disponível. Entre com e-mail e senha.",
  falhou: "Não foi possível concluir o login com o Google. Tente de novo.",
};

/** Lê o `?google=` da URL e devolve a mensagem, ou `null`. */
export function mensagemDoGoogle(search: string): string | null {
  const motivo = new URLSearchParams(search).get("google");
  return motivo && motivo in MOTIVO_GOOGLE ? MOTIVO_GOOGLE[motivo] : null;
}

/**
 * "Entrar com o Google" do servidor municipal. Só aparece quando o servidor
 * tem client ID/secret do Google (`branding.login_google`). O Google diz QUEM
 * é; entra só quem já é usuário ativo da prefeitura com aquele e-mail.
 *
 * Navegação de topo (não fetch): o navegador vai ao Google e volta. O `next`
 * é lido no clique, de `window.location`, pelo mesmo motivo da tela de login
 * (sem fronteira de Suspense).
 */
export function EntrarComGoogle({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center gap-3 px-4 text-xs text-foreground-muted">
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
        ou
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </div>
      <button
        type="button"
        onClick={() => window.location.assign(googleLoginUrl(destinoDaQuery(window.location.search)))}
        className={cn(
          BOTAO_LOGIN,
          "border border-border-strong bg-background text-foreground hover:bg-muted",
        )}
      >
        {/* O "G" em cores é exigência da marca do Google; fica em public/
            porque as cores são dela, não do tema. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/google-g.svg" alt="" width={18} height={18} className="h-[18px] w-[18px]" />
        Entrar com o Google
      </button>
    </div>
  );
}

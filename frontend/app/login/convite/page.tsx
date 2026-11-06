"use client";

import { useEffect, useState } from "react";

import { NovaSenhaForm } from "@/components/login/NovaSenhaForm";
import { Concluido, LinkInvalido, TelaDeConta, tokenDaUrl } from "@/components/login/TelaDeConta";
import { Carregando } from "@/components/ui/carregando";
import { ApiError, api } from "@/lib/api";

/**
 * `/login/convite?token=…` — o servidor convidado ativa a conta: confirma o
 * e-mail (por ter aberto o link) e escolhe a própria senha. O administrador
 * que criou a conta nunca conhece essa senha.
 */
export default function ConvitePage() {
  const [token, setToken] = useState("");
  const [conta, setConta] = useState<{ nome: string; email: string } | null>(null);
  const [ativada, setAtivada] = useState(false);
  const [invalido, setInvalido] = useState<string | null>(null);

  useEffect(() => {
    const t = tokenDaUrl();
    setToken(t);
    if (!t) {
      setInvalido("Este endereço está incompleto. Abra o link exatamente como chegou no e-mail.");
      return;
    }
    api.conta
      .conviteInfo(t)
      .then(setConta)
      .catch((err) => setInvalido(err instanceof Error ? err.message : "Convite inválido."));
  }, []);

  return (
    <TelaDeConta titulo={ativada ? "Conta ativada" : "Ativar a sua conta"}>
      {invalido ? (
        <LinkInvalido mensagem={invalido} />
      ) : ativada ? (
        <Concluido mensagem="Tudo certo. Entre com o seu e-mail e a senha que você acabou de criar." tipo="servidor" />
      ) : !conta ? (
        <Carregando />
      ) : (
        <div className="space-y-5">
          <div className="rounded-2xl border border-border bg-surface-1 px-4 py-3 text-sm text-foreground-muted">
            Olá, <strong className="font-medium text-foreground">{conta.nome}</strong>. Escolha a senha
            que você vai usar para entrar como{" "}
            <strong className="font-medium text-foreground">{conta.email}</strong>.
          </div>
          <NovaSenhaForm
            rotuloBotao="Ativar conta"
            onSalvar={async (senha) => {
              try {
                await api.conta.aceitarConvite(token, senha);
                setAtivada(true);
              } catch (err) {
                if (err instanceof ApiError && err.status === 400) setInvalido(err.message);
                else throw err;
              }
            }}
          />
        </div>
      )}
    </TelaDeConta>
  );
}

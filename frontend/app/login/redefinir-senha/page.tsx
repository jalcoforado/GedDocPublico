"use client";

import { useEffect, useState } from "react";

import { NovaSenhaForm } from "@/components/login/NovaSenhaForm";
import { Concluido, LinkInvalido, TelaDeConta, tokenDaUrl } from "@/components/login/TelaDeConta";
import { ApiError, type ContaConfirmada, api } from "@/lib/api";

/**
 * `/login/redefinir-senha?token=…` — aberta pelo link do "Não lembro a senha"
 * (servidor ou cidadão). O link vale 1 hora e uma vez só.
 */
export default function RedefinirSenhaPage() {
  const [token, setToken] = useState("");
  const [feito, setFeito] = useState<ContaConfirmada | null>(null);
  const [invalido, setInvalido] = useState<string | null>(null);

  useEffect(() => {
    const t = tokenDaUrl();
    if (!t) setInvalido("Este endereço está incompleto. Abra o link exatamente como chegou no e-mail.");
    setToken(t);
  }, []);

  return (
    <TelaDeConta titulo="Criar nova senha">
      {invalido ? (
        <LinkInvalido mensagem={invalido} />
      ) : feito ? (
        <Concluido mensagem="Pronto: a sua senha foi alterada. Entre com ela agora." tipo={feito.tipo} />
      ) : (
        <NovaSenhaForm
          rotuloBotao="Salvar nova senha"
          onSalvar={async (senha) => {
            try {
              setFeito(await api.conta.redefinirSenha(token, senha));
            } catch (err) {
              // Link vencido/usado não se resolve tentando de novo aqui.
              if (err instanceof ApiError && err.status === 400) setInvalido(err.message);
              else throw err;
            }
          }}
        />
      )}
    </TelaDeConta>
  );
}

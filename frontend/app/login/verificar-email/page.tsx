"use client";

import { useEffect, useRef, useState } from "react";

import { Concluido, LinkInvalido, TelaDeConta, tokenDaUrl } from "@/components/login/TelaDeConta";
import { Carregando } from "@/components/ui/carregando";
import { type ContaConfirmada, api } from "@/lib/api";

/**
 * `/login/verificar-email?token=…` — o cidadão confirma o e-mail do
 * cadastro. Basta abrir: a confirmação acontece ao carregar.
 */
export default function VerificarEmailPage() {
  const [feito, setFeito] = useState<ContaConfirmada | null>(null);
  const [invalido, setInvalido] = useState<string | null>(null);
  // O link é de uso único: o StrictMode (dev) roda o efeito duas vezes, e a
  // segunda chamada recusaria o link já consumido pela primeira.
  const disparou = useRef(false);

  useEffect(() => {
    if (disparou.current) return;
    disparou.current = true;
    const t = tokenDaUrl();
    if (!t) {
      setInvalido("Este endereço está incompleto. Abra o link exatamente como chegou no e-mail.");
      return;
    }
    api.conta
      .verificarEmail(t)
      .then(setFeito)
      .catch((err) => setInvalido(err instanceof Error ? err.message : "Link inválido."));
  }, []);

  return (
    <TelaDeConta titulo="Confirmação de e-mail">
      {invalido ? (
        <LinkInvalido mensagem={invalido} />
      ) : feito ? (
        <Concluido mensagem="E-mail confirmado. O seu cadastro está ativo." tipo={feito.tipo} />
      ) : (
        <Carregando />
      )}
    </TelaDeConta>
  );
}

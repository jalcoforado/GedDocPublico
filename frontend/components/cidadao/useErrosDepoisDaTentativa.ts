"use client";

import { useCallback, useState } from "react";

/**
 * Erro só depois da tentativa (padrão de formulário, regra 4): o erro de um
 * campo aparece quando a pessoa sai dele (`onBlur`) ou quando tenta enviar —
 * nunca ao abrir a tela, nem enquanto ela ainda está digitando a primeira vez.
 *
 * `erros` é recalculado a cada render pela tela (mapa campo → mensagem ou
 * `null`); o hook só decide QUAIS mostrar.
 */
export function useErrosDepoisDaTentativa<K extends string>(erros: Record<K, string | null>) {
  const [tocados, setTocados] = useState<Partial<Record<K, true>>>({});
  const [tentou, setTentou] = useState(false);

  const erro = (campo: K): string | undefined =>
    (tentou || tocados[campo]) && erros[campo] ? (erros[campo] as string) : undefined;

  const sair = useCallback((campo: K) => () => setTocados((t) => (t[campo] ? t : { ...t, [campo]: true })), []);

  /** Marca a tentativa de envio; devolve `true` se está tudo certo. */
  const tentar = (campos?: K[]): boolean => {
    if (campos) {
      setTocados((t) => ({ ...t, ...Object.fromEntries(campos.map((c) => [c, true])) }));
      return campos.every((c) => !erros[c]);
    }
    setTentou(true);
    return Object.values(erros).every((e) => !e);
  };

  return { erro, sair, tentar, tentou };
}

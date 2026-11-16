"use client";

import { useCallback, useState } from "react";

/**
 * Validação dos diálogos de Pagamentos no padrão de formulário: o erro de um
 * campo só aparece depois que a pessoa sai dele (`tocar`) ou tenta enviar
 * (`conferir`) — nunca ao abrir. Ao enviar com erro, o foco vai ao primeiro
 * campo inválido, na ordem de `ids`.
 *
 * Os erros são recalculados a cada render a partir do formulário (`erros`),
 * então somem sozinhos quando o campo é corrigido.
 *
 * Uso:
 *   const v = useValidacaoCampos(erros, { valor: "mov-valor", motivo: "mov-motivo" });
 *   <FormField error={v.erro("valor")}><Input id="mov-valor" onBlur={v.tocar("valor")} …/></FormField>
 *   function salvar() { if (v.conferir()) mutate(); }
 *   // ao abrir o diálogo de novo: v.reiniciar()
 */
export function useValidacaoCampos<C extends string>(
  erros: Partial<Record<C, string | null | undefined | false>>,
  ids: Record<C, string>,
) {
  const [tocados, setTocados] = useState<ReadonlySet<C>>(() => new Set());
  const [tentou, setTentou] = useState(false);

  const erro = (campo: C): string | undefined => {
    const msg = erros[campo];
    return msg && (tentou || tocados.has(campo)) ? msg : undefined;
  };

  const tocar = (campo: C) => () =>
    setTocados((prev) => (prev.has(campo) ? prev : new Set(prev).add(campo)));

  /** Marca a tentativa; se houver erro, foca o primeiro e devolve `false`. */
  const conferir = (): boolean => {
    setTentou(true);
    const primeiro = (Object.keys(ids) as C[]).find((c) => erros[c]);
    if (!primeiro) return true;
    document.getElementById(ids[primeiro])?.focus();
    return false;
  };

  const reiniciar = useCallback(() => {
    setTocados(new Set());
    setTentou(false);
  }, []);

  return { erro, tocar, conferir, reiniciar };
}

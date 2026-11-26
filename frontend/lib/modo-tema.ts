"use client";

import { useEffect, useState } from "react";

import type { ModoTema } from "@/lib/tema-cores";

const modoAtual = (): ModoTema =>
  document.documentElement.classList.contains("dark") ? "dark" : "light";

/**
 * Modo claro/escuro lido do `<html>`, que é onde o `ThemeProvider` o grava.
 *
 * Existe ao lado de `useTheme()` porque aquele exige o provider e lança fora
 * dele. Quem só precisa SABER o modo — a paleta do município, a
 * pré-visualização de cores — não deveria quebrar por ser renderizado sem ele,
 * como acontece em teste de tela isolada.
 */
export function useModoTema(): ModoTema {
  const [modo, setModo] = useState<ModoTema>("light");

  useEffect(() => {
    setModo(modoAtual());
    const observador = new MutationObserver(() => setModo(modoAtual()));
    observador.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observador.disconnect();
  }, []);

  return modo;
}

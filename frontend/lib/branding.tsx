"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, type BrandingResponse } from "@/lib/api";
import { aplicarFonte, aplicarTema, derivarTema, guardarTema } from "@/lib/tema-cores";
import { useModoTema } from "@/lib/modo-tema";

const BrandingContext = createContext<BrandingResponse | null>(null);
const RecarregarContext = createContext<() => void>(() => {});

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingResponse | null>(null);
  const theme = useModoTema();

  const carregar = useCallback(() => {
    api
      .branding()
      .then((b) => {
        setBranding(b);
        // Atualiza título da aba
        if (typeof document !== "undefined" && b.nome) {
          document.title = b.nome;
        }
      })
      .catch(() => {
        // Falha silenciosa — site cai no branding default ("Aprimora")
      });
  }, []);

  useEffect(carregar, [carregar]);

  // Tema do município: deriva a paleta das cores do tenant e a aplica no
  // `<html>`, sobrepondo os tokens do `globals.css`. Reaplica ao trocar
  // claro/escuro, porque a derivação muda com o modo. O cache alimenta o
  // script de `<head>`, que evita o piscar do verde padrão na carga seguinte.
  useEffect(() => {
    if (!branding) return;
    aplicarTema(document.documentElement, derivarTema(branding, theme));
    aplicarFonte(document.documentElement, branding.fonte_titulos);
    guardarTema(branding);
  }, [branding, theme]);

  return (
    <BrandingContext.Provider value={branding}>
      <RecarregarContext.Provider value={carregar}>{children}</RecarregarContext.Provider>
    </BrandingContext.Provider>
  );
}

export function useBranding(): BrandingResponse | null {
  return useContext(BrandingContext);
}

/** Relê o branding do servidor — para quem acabou de alterá-lo (Configurações). */
export function useRecarregarBranding(): () => void {
  return useContext(RecarregarContext);
}

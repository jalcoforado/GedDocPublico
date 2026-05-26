"use client";

import { createContext, useContext, useEffect, useState } from "react";

import { api, type BrandingResponse } from "@/lib/api";

const BrandingContext = createContext<BrandingResponse | null>(null);

export function BrandingProvider({ children }: { children: React.ReactNode }) {
  const [branding, setBranding] = useState<BrandingResponse | null>(null);

  useEffect(() => {
    api
      .branding()
      .then((b) => {
        setBranding(b);
        // Aplica cor primária como CSS variable (consumida em globals.css/tailwind)
        if (b.cor_primaria) {
          document.documentElement.style.setProperty("--brand-primary", b.cor_primaria);
        }
        // Atualiza título da aba
        if (typeof document !== "undefined" && b.nome) {
          document.title = b.nome;
        }
      })
      .catch(() => {
        // Falha silenciosa — site cai no branding default ("Aprimora")
      });
  }, []);

  return <BrandingContext.Provider value={branding}>{children}</BrandingContext.Provider>;
}

export function useBranding(): BrandingResponse | null {
  return useContext(BrandingContext);
}

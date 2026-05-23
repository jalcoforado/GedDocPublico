"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";

import { api, type CidadaoMe } from "@/lib/api";

interface CidadaoAuthContextValue {
  cidadao: CidadaoMe | null;
  loading: boolean;
  logout: () => void;
}

const Ctx = createContext<CidadaoAuthContextValue | null>(null);

export function CidadaoAuthProvider({
  children,
  requireAuth = true,
}: {
  children: React.ReactNode;
  requireAuth?: boolean;
}) {
  const router = useRouter();
  const [cidadao, setCidadao] = useState<CidadaoMe | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Cookie HttpOnly: tenta /me; se 401, não há sessão.
    api.cidadao
      .me()
      .then(setCidadao)
      .catch(() => {
        if (requireAuth) router.replace("/cidadao/login");
      })
      .finally(() => setLoading(false));
  }, [router, requireAuth]);

  function logout() {
    api.cidadao.logout().finally(() => {
      setCidadao(null);
      router.push("/cidadao/login");
    });
  }

  return (
    <Ctx.Provider value={{ cidadao, loading, logout }}>{children}</Ctx.Provider>
  );
}

export function useCidadao(): CidadaoAuthContextValue {
  const ctx = useContext(Ctx);
  if (!ctx)
    throw new Error("useCidadao deve ser usado dentro de <CidadaoAuthProvider>");
  return ctx;
}

/**
 * Hook para páginas INTERNAS do portal cidadão (`/cidadao/processos`, `/cidadao/abrir`, etc).
 * Redireciona pra `/cidadao/login` se não houver sessão.
 *
 * Difere de `useCidadao()` por causar redirect efetivo — usar `useCidadao()`
 * em páginas públicas (login/cadastrar/landing) que só querem ler o estado.
 */
export function useRequireCidadao(): CidadaoAuthContextValue {
  const router = useRouter();
  const ctx = useCidadao();
  useEffect(() => {
    if (!ctx.loading && !ctx.cidadao) {
      router.replace("/cidadao/login");
    }
  }, [ctx.loading, ctx.cidadao, router]);
  return ctx;
}

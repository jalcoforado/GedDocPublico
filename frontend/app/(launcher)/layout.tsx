"use client";

import { useQuery } from "@tanstack/react-query";
import { LogOut, Shield } from "lucide-react";
import Link from "next/link";

import { api } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Providers } from "@/lib/providers";

/**
 * Barra de saída sempre visível no launcher. Sem ela, um usuário sem nenhum
 * módulo (lista vazia) ou com falha de rede na `/modulos/me` ficava preso
 * numa tela sem Sidebar/Header e sem NENHUM jeito de sair pela interface — e
 * um platform admin sem transação no tenant perdia o link "Plataforma" que
 * via em `/home` antes desta fatia (ver Sidebar.tsx, mesmo critério
 * `admin-me`/`is_platform_admin`).
 */
function BarraDeSaida() {
  const { logout } = useAuth();
  const adminMeQ = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => api.admin.me(),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const isPlatformAdmin = adminMeQ.data?.is_platform_admin ?? false;

  return (
    <div className="absolute right-4 top-4 flex items-center gap-2">
      {isPlatformAdmin && (
        <Link
          href="/admin/tenants"
          className="
            inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium
            text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground
          "
        >
          <Shield className="h-4 w-4" aria-hidden="true" />
          Plataforma
        </Link>
      )}
      <button
        type="button"
        onClick={() => logout()}
        className="
          inline-flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium
          text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground
        "
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
        Sair
      </button>
    </div>
  );
}

/**
 * Layout do launcher (`/modulos`). Autenticado como o `(app)`, mas SEM
 * Sidebar nem Header de módulo — mostrar o menu de um módulo numa tela cuja
 * função é escolher o módulo seria circular. Mantém, porém, uma saída
 * sempre disponível (ver `BarraDeSaida`).
 */
function Shell({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-foreground-muted">
        Carregando...
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="relative min-h-dvh bg-background">
      <BarraDeSaida />
      <main className="flex min-h-dvh flex-col items-center justify-center p-6">
        {children}
      </main>
    </div>
  );
}

export default function LauncherLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AuthProvider>
        <Shell>{children}</Shell>
      </AuthProvider>
    </Providers>
  );
}

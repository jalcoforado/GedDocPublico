"use client";

import { useQuery } from "@tanstack/react-query";
import { Home as HomeIcon, LogOut, Shield } from "lucide-react";
import Link from "next/link";

import { AssinaturaAprimora } from "@/components/AssinaturaAprimora";
import { MarcaDoMunicipio } from "@/components/MarcaDoMunicipio";
import { api } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { Providers } from "@/lib/providers";

/**
 * Cabeçalho do launcher — mesma faixa do `Header` do sistema (layout de
 * referência: protótipo Figma "Sistema - Aprimora"), mas PRÓPRIO, e de
 * propósito: o `Header` monta busca, sino e troca de módulo, cada um com a
 * sua chamada de API. Aqui a saída tem de aparecer mesmo com usuário sem
 * nenhum módulo ou com a `/modulos/me` fora do ar — sem ela a pessoa ficava
 * presa numa tela sem jeito de sair, e um platform admin sem transação no
 * tenant perdia o link "Plataforma" (mesmo critério `admin-me` do Sidebar).
 * Por isso este cabeçalho só depende do que já está em memória.
 */
function CabecalhoDoLauncher() {
  const { logout, user } = useAuth();
  const adminMeQ = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => api.admin.me(),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const isPlatformAdmin = adminMeQ.data?.is_platform_admin ?? false;

  const acao =
    "inline-flex h-10 items-center gap-1.5 rounded-full px-3 text-sm font-medium text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <header
      aria-label="Cabeçalho do sistema"
      className="flex items-center gap-3 bg-gradient-to-r from-brand-dark via-brand to-brand-light px-4 py-3 pt-safe shadow-md sm:gap-5 sm:px-6"
    >
      <Link
        href="/home"
        aria-label="Início"
        className="flex h-11 shrink-0 items-center rounded-lg bg-card px-3 shadow-sm transition-shadow duration-fast hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
      >
        <MarcaDoMunicipio />
      </Link>
      <div className="flex-1" />
      {user ? (
        <div className="hidden min-w-0 text-right text-primary-foreground lg:block">
          <div className="truncate font-display text-sm font-semibold leading-tight">
            {user.nome}
          </div>
          <div className="truncate text-xs leading-tight opacity-90">{user.email}</div>
        </div>
      ) : null}
      <div className="flex items-center gap-1 rounded-full bg-card px-1.5 py-0.5 shadow-sm">
        {isPlatformAdmin && (
          <Link href="/admin/tenants" className={acao}>
            <Shield className="h-4 w-4" aria-hidden="true" />
            Plataforma
          </Link>
        )}
        <button type="button" onClick={() => logout()} className={acao}>
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sair
        </button>
      </div>
    </header>
  );
}

/**
 * Layout do launcher (`/modulos`). Autenticado como o `(app)`, mas SEM
 * Sidebar nem o Header de módulo — mostrar o menu de um módulo numa tela cuja
 * função é escolher o módulo seria circular. Veste, porém, a mesma moldura do
 * "Menu principal": faixa do município, trilha de volta e a assinatura do
 * produto no rodapé.
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
    <div className="flex min-h-dvh flex-col bg-background">
      <CabecalhoDoLauncher />
      <main className="flex-1 p-4 sm:p-[var(--density-space)]">
        <div className="mx-auto w-full max-w-7xl">
          <Link
            href="/home"
            className="inline-flex items-center gap-2.5 rounded font-display text-sm font-semibold text-titulo-destaque underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <HomeIcon className="h-5 w-5 text-foreground-subtle" aria-hidden="true" />
            Menu principal
          </Link>
          <div className="mt-5">{children}</div>
        </div>
      </main>
      <AssinaturaAprimora className="px-4 pb-5 pt-2" />
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

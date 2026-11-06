"use client";

import { usePathname } from "next/navigation";
import { useState } from "react";

import { AssinaturaAprimora } from "@/components/AssinaturaAprimora";
import { CommandPaletteProvider } from "@/components/CommandPalette";
import { Header } from "@/components/Header";
import { LoadingBar } from "@/components/LoadingBar";
import { ShellCarregando } from "@/components/ShellCarregando";
import { Sidebar } from "@/components/Sidebar";
import { TrilhaDoModulo } from "@/components/TrilhaDoModulo";
import { AuthProvider, useAuth } from "@/lib/auth";
import { MENUS } from "@/lib/menus";
import { ModuloAtualProvider } from "@/lib/modulo-atual";
import { moduloDoPathname, nomeDoModulo } from "@/lib/modulos";
import { Providers } from "@/lib/providers";

function Shell({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();
  const modulo = moduloDoPathname(pathname);

  if (loading) return <ShellCarregando comMenuLateral />;
  if (!user) return null;
  // Publicado para o `PageHeader` montar a trilha sem ler a URL por conta
  // própria (ver `lib/modulo-atual.tsx`).
  const moduloAtual = modulo
    ? { slug: modulo, nome: nomeDoModulo(modulo), raiz: MENUS[modulo]?.raiz ?? `/m/${modulo}` }
    : null;
  return (
    <ModuloAtualProvider value={moduloAtual}>
      <div className="flex h-dvh bg-background">
        {/* Skip link (fatia 3.5): primeiro focável — teclado pula sidebar e
            header direto para o conteúdo. Invisível até receber foco. */}
        <a
          href="#conteudo"
          className="sr-only z-toast focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:rounded-md focus:bg-brand focus:px-3 focus:py-2 focus:text-sm focus:font-medium focus:text-primary-foreground"
        >
          Pular para o conteúdo
        </a>
        <LoadingBar />
        {/* Menu único (2026-11-05): a barra lateral está em TODA tela, com
            todos os módulos contratados — no Início, no perfil e dentro dos
            módulos. Antes ela só existia dentro de um módulo e mostrava só ele;
            a troca de módulo passava pelo launcher. */}
        <Sidebar modulo={modulo} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Header onOpenSidebar={() => setSidebarOpen(true)} />
          <main
            id="conteudo"
            className="flex-1 overflow-y-auto p-4 sm:p-[var(--density-space)]"
          >
            {/* Contrato de largura (spec §12.2): max-w-7xl centrado por padrão;
                página full-width (dashboard) opta por fora marcando qualquer
                elemento seu com data-full-width — o :has() solta o teto. */}
            <div
              key={pathname}
              className="mx-auto w-full max-w-7xl animate-page-in motion-reduce:animate-none has-[[data-full-width]]:max-w-none"
            >
              {/* No shell, e não no PageHeader: várias telas de módulo
                  desenham o próprio título sem ele, e ficavam sem trilha. */}
              {moduloAtual ? <TrilhaDoModulo modulo={moduloAtual} /> : null}
              {children}
            </div>
            {/* Layout de referência: a assinatura do produto fecha toda tela
                interna, como já fecha o login e o launcher. Dentro do <main>,
                para rolar com o conteúdo em vez de roubar altura da tela. */}
            <AssinaturaAprimora className="pb-2 pt-8" />
          </main>
        </div>
      </div>
    </ModuloAtualProvider>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <AuthProvider>
        <CommandPaletteProvider>
          <Shell>{children}</Shell>
        </CommandPaletteProvider>
      </AuthProvider>
    </Providers>
  );
}

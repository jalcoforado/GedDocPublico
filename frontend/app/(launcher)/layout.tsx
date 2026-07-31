"use client";

import { AuthProvider, useAuth } from "@/lib/auth";
import { Providers } from "@/lib/providers";

/**
 * Layout do launcher (`/modulos`). Autenticado como o `(app)`, mas SEM
 * Sidebar nem Header de módulo — mostrar o menu de um módulo numa tela cuja
 * função é escolher o módulo seria circular.
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
    <main className="flex min-h-dvh flex-col items-center justify-center bg-background p-6">
      {children}
    </main>
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

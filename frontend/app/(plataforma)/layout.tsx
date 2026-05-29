"use client";

import { Providers } from "@/lib/providers";

export default function PlataformaLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <div className="min-h-dvh bg-background">
        <header className="border-b border-border bg-card">
          <div className="mx-auto flex max-w-6xl items-baseline gap-2 px-4 py-3 sm:px-6">
            <span className="text-xl font-bold text-primary">Aprimora</span>
            <span className="text-xs text-muted-foreground">Administração da Plataforma</span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </Providers>
  );
}

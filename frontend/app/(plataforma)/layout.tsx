"use client";

import { LogoAprimora } from "@/components/AssinaturaAprimora";
import { Providers } from "@/lib/providers";

export default function PlataformaLayout({ children }: { children: React.ReactNode }) {
  return (
    <Providers>
      <div className="min-h-dvh bg-background">
        {/* Território do produto, não de um município: o filete e o rótulo
            usam a assinatura da Aprimora, que o tema do tenant não alcança. */}
        <header className="border-b border-t-2 border-border border-t-assinatura bg-card">
          <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
            <LogoAprimora className="h-6" />
            <span className="text-xs font-medium text-assinatura-texto">
              Administração da Plataforma
            </span>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">{children}</main>
      </div>
    </Providers>
  );
}

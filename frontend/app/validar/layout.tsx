import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Validação de Assinatura — Aprimora",
  description:
    "Verifique a autenticidade e a integridade de uma assinatura eletrônica.",
};

export default function ValidarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-3xl items-baseline gap-2 px-4 py-3 sm:px-6">
          <span className="text-xl font-bold text-primary">Aprimora</span>
          <span className="text-xs text-muted-foreground">
            Validação de Assinatura
          </span>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6">{children}</main>
    </div>
  );
}

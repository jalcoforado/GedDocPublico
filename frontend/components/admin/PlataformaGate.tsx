"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

/** Gate da área de plataforma (PR3a): só renderiza o conteúdo para admin de
 * plataforma (allowlist no backend). A API também responde 403; isto evita
 * sequer exibir o painel para quem não é plataforma. */
export function PlataformaGate({ children }: { children: React.ReactNode }) {
  const q = useQuery({ queryKey: ["admin-me"], queryFn: () => api.admin.me() });

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground" role="status">Carregando…</p>;
  }
  if (!q.data?.is_platform_admin) {
    return (
      <div className="rounded-md border border-border bg-card p-6">
        <h1 className="text-lg font-semibold text-foreground">Acesso restrito</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Esta área é exclusiva para administradores da plataforma.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}

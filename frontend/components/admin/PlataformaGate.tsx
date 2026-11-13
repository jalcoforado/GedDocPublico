"use client";

import { Carregando } from "@/components/ui/carregando";

import { useQuery } from "@tanstack/react-query";
import { ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { api } from "@/lib/api";

/** Gate da área de plataforma (PR3a): só renderiza o conteúdo para admin de
 * plataforma (allowlist no backend). A API também responde 403; isto evita
 * sequer exibir o painel para quem não é plataforma. */
export function PlataformaGate({ children }: { children: React.ReactNode }) {
  const q = useQuery({ queryKey: ["admin-me"], queryFn: () => api.admin.me() });

  if (q.isLoading) {
    return <Carregando className="text-sm text-foreground-muted" />;
  }
  if (!q.data?.is_platform_admin) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title="Acesso restrito"
        description="Esta área é exclusiva para administradores da plataforma."
      />
    );
  }
  return <>{children}</>;
}

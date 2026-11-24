import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * O que aparece enquanto o `/auth/me` não responde — a MOLDURA da tela, e não
 * um "Carregando..." solto no meio do branco.
 *
 * O texto antigo trocava a tela inteira duas vezes (branco → texto → app), e
 * cada troca de grupo de rota repetia o pisca. A moldura tem as mesmas peças
 * e medidas da tela que vem — faixa do município no alto, barra lateral nas
 * telas de módulo, blocos no lugar do conteúdo —, então quando o app chega
 * nada muda de lugar: os blocos só ganham conteúdo.
 *
 * Fica invisível nos primeiros 150ms (`animate-aparece-depois`): resposta
 * rápida não pisca moldura nenhuma.
 */
export function ShellCarregando({ comMenuLateral = false }: { comMenuLateral?: boolean }) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Carregando o sistema"
      className="flex h-dvh animate-aparece-depois flex-col bg-background motion-reduce:animate-none"
    >
      <div
        aria-hidden="true"
        className="flex h-[73px] shrink-0 items-center gap-6 border-b border-border bg-surface-1 px-4 sm:px-6"
      >
        <Skeleton className="h-10 w-40" />
        <Skeleton className="mx-auto hidden h-10 w-full max-w-lg rounded-full sm:block" />
        <Skeleton className="ml-auto h-10 w-40 rounded-full" />
      </div>
      <div className="flex min-h-0 flex-1">
        {comMenuLateral && (
          <div
            aria-hidden="true"
            className="hidden w-64 shrink-0 flex-col gap-2 min-[1440px]:w-72 border-r border-sidebar-border bg-sidebar px-4 pt-5 md:flex"
          >
            <div className="mb-4 h-11 rounded-button bg-sidebar-accent" />
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="h-10 rounded-md bg-sidebar-accent/60" />
            ))}
          </div>
        )}
        <div aria-hidden="true" className="flex-1 overflow-hidden p-4 sm:p-[var(--density-space)]">
          <div className="mx-auto w-full max-w-7xl space-y-6">
            <div className="space-y-2">
              <Skeleton className="h-7 w-56" />
              <Skeleton className="h-4 w-80 max-w-full" />
            </div>
            <div className={cn("grid gap-4 sm:grid-cols-2", comMenuLateral ? "lg:grid-cols-4" : "lg:grid-cols-3")}>
              {Array.from({ length: comMenuLateral ? 4 : 6 }).map((_, i) => (
                <Skeleton key={i} className="h-24 rounded-card" variant="shimmer" />
              ))}
            </div>
            <Skeleton className="h-64 rounded-card" />
          </div>
        </div>
      </div>
    </div>
  );
}

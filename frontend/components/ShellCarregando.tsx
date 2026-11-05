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
      className="flex h-dvh animate-aparece-depois bg-background motion-reduce:animate-none"
    >
      {comMenuLateral && (
        <div
          aria-hidden="true"
          className="hidden w-64 shrink-0 flex-col gap-3 border-r border-sidebar-border bg-sidebar p-3 md:flex"
        >
          <div className="h-12 w-24 rounded-lg bg-sidebar-accent" />
          <div className="mt-3 h-10 rounded-button bg-sidebar-accent" />
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="h-8 rounded-md bg-sidebar-accent/60" />
          ))}
        </div>
      )}
      <div className="flex flex-1 flex-col overflow-hidden">
        <div
          aria-hidden="true"
          className="flex h-16 shrink-0 items-center gap-4 bg-gradient-to-r from-brand-dark via-brand to-brand-light px-4 shadow-md sm:px-6"
        >
          {!comMenuLateral && <div className="h-11 w-24 rounded-lg bg-card/90" />}
          <div className="mx-auto hidden h-10 w-full max-w-md rounded-full bg-card/80 sm:block" />
          <div className="ml-auto h-10 w-40 rounded-full bg-card/80" />
        </div>
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

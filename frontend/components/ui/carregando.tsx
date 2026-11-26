import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/**
 * Carregando de bloco — o substituto do `<p>Carregando...</p>` solto.
 *
 * O texto aparecia por um instante e sumia, empurrando o conteúdo quando ele
 * chegava; em telas rápidas era só um pisca. Aqui: linhas de esqueleto no
 * lugar do conteúdo, que só ficam visíveis se a espera passar de 150ms
 * (`animate-aparece-depois`), e o "Carregando…" continua existindo para o
 * leitor de tela.
 *
 * `className` é a do texto antigo e fica no invólucro, onde ainda posiciona o
 * bloco (padding, altura, centralização); as linhas vão empilhadas dentro,
 * centradas se o texto era centrado.
 *
 * Para tabela, use `SkeletonRow`; para cartão de número, `SkeletonKpi`.
 */
export function Carregando({ className, linhas = 3 }: { className?: string; linhas?: number }) {
  const larguras = ["w-2/3", "w-full", "w-1/2", "w-5/6", "w-3/4"];
  const centrado = /\b(text-center|justify-center|items-center)\b/.test(className ?? "");
  return (
    <div role="status" className={cn(className, "animate-aparece-depois motion-reduce:animate-none")}>
      <span className="sr-only">Carregando…</span>
      <div aria-hidden="true" className={cn("w-full max-w-md space-y-2", centrado && "mx-auto")}>
        {Array.from({ length: linhas }).map((_, i) => (
          <Skeleton
            key={i}
            role="presentation"
            aria-label={undefined}
            className={cn("h-3.5", larguras[i % larguras.length], centrado && "mx-auto")}
          />
        ))}
      </div>
    </div>
  );
}

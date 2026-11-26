import { cn } from "@/lib/utils";

/**
 * Marca da Aprimora, o PRODUTO — distinta da marca do município, que vem de
 * `useBranding()` e domina a interface. Aparece só onde o produto se assina:
 * rodapé do login, launcher e administração da plataforma.
 *
 * São dois arquivos porque o wordmark é navy e some sobre o fundo escuro; a
 * variante `-escuro` troca só o navy por claro e mantém o laranja.
 */
export function LogoAprimora({ className }: { className?: string }) {
  return (
    <>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/aprimora-logo.png"
        alt="Aprimora"
        width={211}
        height={30}
        className={cn("h-5 w-auto dark:hidden", className)}
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/aprimora-logo-escuro.png"
        alt="Aprimora"
        width={211}
        height={30}
        className={cn("hidden h-5 w-auto dark:block", className)}
      />
    </>
  );
}

/** "Sistema desenvolvido por: [Aprimora]" — o rodapé que assina o produto. */
export function AssinaturaAprimora({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        "flex items-center justify-center gap-2 text-xs text-foreground-subtle",
        className,
      )}
    >
      Sistema desenvolvido por:
      <LogoAprimora className="h-4" />
    </p>
  );
}

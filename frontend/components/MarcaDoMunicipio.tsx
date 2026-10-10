"use client";

import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";

/**
 * Marca do município: a de login (horizontal) se houver, senão a quadrada,
 * senão o nome por extenso. É o que identifica a prefeitura no cabeçalho do
 * sistema e das telas públicas — a marca do PRODUTO é outra coisa e mora em
 * `AssinaturaAprimora`.
 */
export function MarcaDoMunicipio({
  className,
  quadrada = false,
}: {
  className?: string;
  /** Só a marca quadrada (o brasão), para onde a horizontal não cabe. */
  quadrada?: boolean;
}) {
  const branding = useBranding();
  const src = quadrada
    ? branding?.logo_url
    : (branding?.logo_login_url ?? branding?.logo_url);
  if (quadrada && !src) {
    // Sem brasão: a inicial do município, para a barra recolhida não ficar muda.
    return (
      <span className="font-display text-sm font-bold text-brand" aria-hidden="true">
        {(branding?.nome ?? "A").trim().charAt(0).toUpperCase()}
      </span>
    );
  }
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={branding?.nome ?? "Aprimora"}
        className={cn("h-8 w-auto object-contain", className)}
      />
    );
  }
  return (
    <span className="font-display text-sm font-semibold text-brand">
      {branding?.nome ?? "Aprimora"}
    </span>
  );
}

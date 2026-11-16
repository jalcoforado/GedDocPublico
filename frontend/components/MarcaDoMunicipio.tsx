"use client";

import { useState } from "react";

import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";

/**
 * Variante da marca para fundo escuro, por convenção de nome: `x.png` →
 * `x-escuro.png`, a mesma da marca do produto (`aprimora-logo-escuro.png`).
 * Só para arquivo local de `/brand/` — endereço externo não tem variante.
 */
export function varianteEscura(src: string): string | null {
  const m = /^(\/brand\/[A-Za-z0-9._-]+?)\.(png|webp|svg|jpe?g)$/i.exec(src);
  return m ? `${m[1]}-escuro.${m[2]}` : null;
}

/**
 * Marca do município: a de login (horizontal) se houver, senão a quadrada,
 * senão o nome por extenso. É o que identifica a prefeitura no cabeçalho do
 * sistema e das telas públicas — a marca do PRODUTO é outra coisa e mora em
 * `AssinaturaAprimora`.
 *
 * Logotipo de prefeitura costuma ter texto escuro (o de Itaitinga é marinho),
 * que some no tema escuro. Se existir a variante `-escuro`, ela entra no
 * escuro; se não existir (o arquivo falha ao carregar), a marca normal ganha
 * um fundo claro atrás, só nesse tema.
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
  const [semEscuro, setSemEscuro] = useState(false);
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
    const alt = branding?.nome ?? "Aprimora";
    const escuro = semEscuro ? null : varianteEscura(src);
    if (escuro) {
      return (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={src} alt={alt} className={cn("h-8 w-auto object-contain dark:hidden", className)} />
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={escuro}
            alt={alt}
            onError={() => setSemEscuro(true)}
            className={cn("hidden h-8 w-auto object-contain dark:block", className)}
          />
        </>
      );
    }
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={alt}
        className={cn(
          "h-8 w-auto object-contain dark:rounded-md dark:bg-marca-fundo dark:px-2 dark:py-1",
          className,
        )}
      />
    );
  }
  return (
    <span className="font-display text-sm font-semibold text-brand">
      {branding?.nome ?? "Aprimora"}
    </span>
  );
}

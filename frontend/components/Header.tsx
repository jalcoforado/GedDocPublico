"use client";

import { Menu } from "lucide-react";
import Link from "next/link";

import { AvatarDropdown } from "@/components/AvatarDropdown";
import { BuscaGlobal } from "@/components/BuscaGlobal";
import { NotificacoesBell } from "@/components/NotificacoesBell";
import { useBranding } from "@/lib/branding";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  return (
    <header
      className="
        sticky top-0 z-30
        flex items-center gap-3 border-b border-border
        bg-surface-1/85 px-4 py-2.5 pt-safe backdrop-blur-md
        sm:px-6
      "
    >
      {/* Mobile menu trigger */}
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label="Abrir menu"
        className="
          inline-flex h-10 w-10 items-center justify-center rounded-md
          text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground
          lg:hidden
        "
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>

      {/* Brand mark — visível em mobile (sidebar tem o logo grande no desktop) */}
      <Link
        href="/home"
        className="flex items-center gap-2 lg:hidden"
        aria-label="Início"
      >
        <BrandMark />
        <span className="text-sm font-semibold tracking-tight">Aprimora</span>
      </Link>

      {/* Busca global ocupa o centro */}
      <div className="hidden flex-1 md:block">
        <BuscaGlobal />
      </div>
      <div className="flex-1 md:hidden" />

      {/* Right cluster */}
      <div className="flex items-center gap-1.5">
        <NotificacoesBell />
        <AvatarDropdown />
      </div>
    </header>
  );
}

/** Marca pequena: monogram do tenant ou ícone gradient. */
function BrandMark() {
  const branding = useBranding();
  if (branding?.logo_url) {
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={branding.logo_url}
        alt={branding.nome ?? "Aprimora"}
        className="h-7 w-7 rounded-md object-cover"
      />
    );
  }
  return (
    <div
      className="
        inline-flex h-7 w-7 items-center justify-center rounded-md
        bg-brand-gradient text-[11px] font-bold text-white shadow-brand
      "
      aria-hidden="true"
    >
      A
    </div>
  );
}

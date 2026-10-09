"use client";

import { Menu, Search } from "lucide-react";
import Link from "next/link";

import { AvatarDropdown } from "@/components/AvatarDropdown";
import { BuscaGlobal } from "@/components/BuscaGlobal";
import { useCommandPalette } from "@/components/CommandPalette";
import { MarcaDoMunicipio } from "@/components/MarcaDoMunicipio";
import { ModuloSwitcher } from "@/components/ModuloSwitcher";
import { NotificacoesBell } from "@/components/NotificacoesBell";
import { useAuth } from "@/lib/auth";

interface HeaderProps {
  /** Ausente nas telas sem barra lateral (início, perfil): some o hambúrguer. */
  onOpenSidebar?: () => void;
}

/**
 * Cabeçalho do sistema — layout de referência: protótipo Figma
 * "Sistema - Aprimora". Faixa na cor da marca do município, com a marca dele
 * num cartão branco, a busca em pílula e a conta à direita.
 *
 * Os controles da direita (módulos, notificações, conta) ficam DENTRO de um
 * cartão branco, e não soltos sobre a faixa: eles e seus popovers são
 * desenhados para fundo claro, e reestilizá-los para fundo de marca exigiria
 * uma segunda versão de cada um.
 */
export function Header({ onOpenSidebar }: HeaderProps) {
  const cmd = useCommandPalette();
  const { user } = useAuth();
  return (
    <header
      aria-label="Cabeçalho do sistema"
      className="
        sticky top-0 z-sticky
        flex items-center gap-3 bg-gradient-to-r from-brand-dark via-brand to-brand-light
        px-4 py-3 pt-safe shadow-md
        sm:gap-5 sm:px-6
      "
    >
      {onOpenSidebar ? (
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Abrir menu"
          className="
            inline-flex h-10 w-10 items-center justify-center rounded-md
            text-primary-foreground transition-colors duration-fast hover:bg-white/15
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white
            md:hidden
          "
        >
          <Menu className="h-5 w-5" aria-hidden="true" />
        </button>
      ) : null}

      <Link
        href="/home"
        aria-label="Início"
        className="
          flex h-11 shrink-0 items-center rounded-lg bg-card px-3 shadow-sm
          transition-shadow duration-fast hover:shadow-md
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white
        "
      >
        <MarcaDoMunicipio />
      </Link>

      {/* Busca global ocupa o centro */}
      <div className="hidden flex-1 md:block">
        <BuscaGlobal />
      </div>
      <div className="flex-1 md:hidden" />

      <div className="flex items-center gap-3">
        {user ? (
          <div className="hidden min-w-0 text-right text-primary-foreground lg:block">
            <div className="truncate font-display text-sm font-semibold leading-tight">
              {user.nome}
            </div>
            <div className="truncate text-xs leading-tight opacity-90">{user.email}</div>
          </div>
        ) : null}
        <div className="flex items-center gap-1 rounded-full bg-card px-1.5 py-0.5 shadow-sm">
          {/* Busca no mobile (fatia 3.4): abaixo de md o campo some — este
              ícone mantém o palette a um toque. */}
          <button
            type="button"
            onClick={() => cmd?.open()}
            aria-label="Buscar"
            className="inline-flex h-10 w-10 items-center justify-center rounded-full text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
          >
            <Search className="h-5 w-5" aria-hidden="true" />
          </button>
          <ModuloSwitcher />
          <NotificacoesBell />
          <AvatarDropdown />
        </div>
      </div>
    </header>
  );
}

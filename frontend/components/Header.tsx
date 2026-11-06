"use client";

import { Menu, Search } from "lucide-react";
import Link from "next/link";

import { AvatarDropdown } from "@/components/AvatarDropdown";
import { BuscaGlobal } from "@/components/BuscaGlobal";
import { useCommandPalette } from "@/components/CommandPalette";
import { MarcaDoMunicipio } from "@/components/MarcaDoMunicipio";
import { NotificacoesBell } from "@/components/NotificacoesBell";
import { UnidadeAtiva } from "@/components/UnidadeAtiva";
import { useAuth } from "@/lib/auth";

interface HeaderProps {
  /** Abre a barra lateral em gaveta (abaixo de md). */
  onOpenSidebar?: () => void;
}

/**
 * Cabeçalho do sistema — faixa CLARA, de ponta a ponta, acima da barra
 * lateral, com a marca do município à esquerda (2026-11-06).
 *
 * Antes era uma faixa na cor da marca, com a marca da prefeitura num cartão
 * branco e os controles da direita noutro cartão branco — dois remendos para
 * a mesma coisa: brasões e logotipos de prefeitura têm texto escuro e cores
 * próprias (o de Itaitinga é marinho e dourado), que somem sobre verde. Com
 * a faixa clara a marca entra direto, em PNG transparente, e os controles
 * (feitos para fundo claro) ficam soltos. A cor do produto fica com a barra
 * lateral, logo abaixo.
 */
export function Header({ onOpenSidebar }: HeaderProps) {
  const cmd = useCommandPalette();
  const { user } = useAuth();
  // `flex-wrap` só abaixo de sm, e só a unidade ativa quebra: ela vai para
  // uma segunda linha (`order-last basis-full`). Na mesma linha não cabia —
  // marca, hambúrguer e os controles já ocupam quase os 390px de um celular
  // comum. O grupo da esquerda é `flex-1` com base zero, então ele nunca
  // força a quebra dos controles da direita.
  return (
    <header
      aria-label="Cabeçalho do sistema"
      className="
        sticky top-0 z-sticky
        flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-border bg-surface-1
        px-4 py-3 pt-safe
        sm:flex-nowrap sm:gap-6 sm:px-6
      "
    >
      <div className="flex min-w-0 flex-1 items-center gap-3 sm:gap-6">
        {onOpenSidebar ? (
          <button
            type="button"
            onClick={onOpenSidebar}
            aria-label="Abrir menu"
            className="
              inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-md
              text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
              md:hidden
            "
          >
            <Menu className="h-5 w-5" aria-hidden="true" />
          </button>
        ) : null}

        {/* No escuro entra a variante `-escuro` da marca (texto claro), sem
            cartão — ver `MarcaDoMunicipio`. */}
        <Link
          href="/home"
          aria-label="Início"
          className="
            flex h-12 shrink-0 items-center rounded-lg px-2
            transition-colors duration-fast hover:bg-muted
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
          "
        >
          <MarcaDoMunicipio className="h-11 max-w-[11rem] sm:max-w-none" />
        </Link>

        <div className="hidden flex-1 md:block">
          <BuscaGlobal />
        </div>
        <div className="flex-1 md:hidden" />
      </div>

      {/* A unidade ativa fica à vista em toda largura: é ela que as caixas e
          o painel contam. No celular, numa linha só dela (ver o comentário do
          `header`); de sm em diante, ao lado do nome. */}
      <div className="order-last flex min-w-0 basis-full sm:order-none sm:basis-auto">
        <UnidadeAtiva />
      </div>

      <div className="flex min-w-0 items-center gap-1 sm:gap-2">
        {user ? (
          <div className="hidden min-w-0 border-l border-border pl-4 text-right lg:block">
            <div className="truncate font-display text-sm font-semibold leading-tight text-foreground">
              {user.nome}
            </div>
            <div className="truncate text-xs leading-tight text-foreground-muted">{user.email}</div>
          </div>
        ) : null}
        {/* Busca no mobile (fatia 3.4): abaixo de md o campo some — este
            ícone mantém o palette a um toque. */}
        <button
          type="button"
          onClick={() => cmd?.open()}
          aria-label="Buscar"
          className="inline-flex h-10 w-10 items-center justify-center rounded-md text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
        >
          <Search className="h-5 w-5" aria-hidden="true" />
        </button>
        <NotificacoesBell />
        <AvatarDropdown />
      </div>
    </header>
  );
}

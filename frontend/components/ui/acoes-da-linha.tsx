"use client";

import { MoreHorizontal, type LucideIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ActionsMenu } from "@/components/ui/actions-menu";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface AcaoDaLinha {
  label: string;
  icon?: LucideIcon;
  onClick?: () => void;
  /** Navegação em vez de clique (Detalhes, Abrir). Só vale para ação visível. */
  href?: string;
  /** Destrutiva (Excluir, Revogar, Inativar): texto vermelho, sem fundo cheio. */
  perigo?: boolean;
  disabled?: boolean;
  /** Some da linha (sem permissão, estado que não admite a ação). */
  oculta?: boolean;
  /**
   * Nome acessível completo quando o rótulo sozinho é ambíguo numa tabela
   * ("Estornar" → "Estornar pagamento da parcela 1"). Leitor de tela navega
   * botão a botão, sem a linha em volta.
   */
  ariaLabel?: string;
  /**
   * Vai para o ⋯ mesmo havendo espaço à vista. Serve à lista que quer a
   * MESMA forma em toda linha (ex.: anexos do processo, SI-72): sem isso, a
   * linha com uma ação a menos mostrava "Excluir" à vista e a outra o
   * escondia no menu.
   */
  sempreNoMenu?: boolean;
}

interface AcoesDaLinhaProps {
  acoes: AcaoDaLinha[];
  /**
   * Quantas ficam à vista. As demais vão para o menu "Mais ações" (⋯). Com
   * `acoes.length <= visiveis + 1` todas ficam à vista — um menu com um item
   * só é um clique a mais sem ganho de espaço.
   */
  visiveis?: number;
  className?: string;
}

/**
 * Coluna "Ações" padrão das tabelas. Antes cada tela desenhava a sua: até seis
 * botões numa linha, quebrando em duas, com um "Excluir" vermelho cheio em
 * todas. O padrão: no máximo `visiveis` botões discretos, o resto no ⋯, e a
 * ação destrutiva sempre por último.
 */
export function AcoesDaLinha({ acoes, visiveis = 2, className }: AcoesDaLinhaProps) {
  const ativas = acoes.filter((a) => !a.oculta);
  // Destrutivas por último, preservando a ordem relativa do resto.
  const destrutivasPorUltimo = (l: AcaoDaLinha[]) => [
    ...l.filter((a) => !a.perigo),
    ...l.filter((a) => a.perigo),
  ];
  const ordenadas = destrutivasPorUltimo(ativas.filter((a) => !a.sempreNoMenu));
  const fixasNoMenu = ativas.filter((a) => a.sempreNoMenu);
  // "Um item só no menu não vale o clique" só se aplica quando não há
  // nenhuma ação que vá ao menu de qualquer jeito.
  const cabe =
    ordenadas.length <= (fixasNoMenu.length > 0 ? visiveis : visiveis + 1);
  const aVista = cabe ? ordenadas : ordenadas.slice(0, visiveis);
  const noMenu = destrutivasPorUltimo([...(cabe ? [] : ordenadas.slice(visiveis)), ...fixasNoMenu]);

  return (
    <div className={cn("inline-flex flex-nowrap items-center justify-end gap-1.5", className)}>
      {aVista.map((a) => {
        const Icone = a.icon;
        const conteudo = (
          <>
            {Icone && <Icone className="h-3.5 w-3.5" aria-hidden="true" />}
            {a.label}
          </>
        );
        const variante = a.perigo ? "danger-outline" : "secondary";
        return a.href && !a.disabled ? (
          <Button key={a.label} asChild variant={variante} size="sm" aria-label={a.ariaLabel}>
            <Link href={a.href}>{conteudo}</Link>
          </Button>
        ) : (
          <Button
            key={a.label}
            variant={variante}
            size="sm"
            disabled={a.disabled}
            aria-label={a.ariaLabel}
            onClick={a.onClick}
          >
            {conteudo}
          </Button>
        );
      })}
      {noMenu.length > 0 && (
        <ActionsMenu
          label="Mais ações"
          icon={MoreHorizontal}
          semSeta
          variant="ghost"
          items={noMenu.map((a) => ({
            label: a.label,
            icon: a.icon,
            disabled: a.disabled,
            perigo: a.perigo,
            onClick: () => a.onClick?.(),
          }))}
        />
      )}
    </div>
  );
}

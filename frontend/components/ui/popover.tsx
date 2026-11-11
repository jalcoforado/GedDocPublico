"use client";

import {
  autoUpdate,
  flip,
  offset,
  shift,
  size,
  useFloating,
  type Placement,
} from "@floating-ui/react-dom";
import * as React from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/utils";

interface PopoverProps {
  open: boolean;
  /** Elemento âncora — o trigger que o painel segue. */
  anchorRef: React.RefObject<HTMLElement | null>;
  /** Chamado em clique fora e Escape. O estado `open` é do caller. */
  onClose: () => void;
  placement?: Placement;
  /** Largura mínima igual à da âncora (padrão de dropdown/combobox). */
  matchAnchorWidth?: boolean;
  children: React.ReactNode;
  className?: string;
}

/**
 * Margem da viewport para flip/colisão. Em cima, conta o cabeçalho fixo: ele
 * fica acima dos dropdowns (z-sticky > z-dropdown), e um painel que abria
 * para cima "cabendo" na viewport escondia a busca embaixo dele.
 */
function margens() {
  const topo = document.querySelector("[data-topo-fixo]")?.getBoundingClientRect().bottom ?? 0;
  return { top: Math.max(0, topo) + 8, right: 8, bottom: 8, left: 8 };
}

/**
 * Popover base (UX-02 fatia 2.6, Floating UI — decisão do §11 da spec):
 * portal para o body (escapa de overflow-hidden), posição fixed com flip e
 * colisão de viewport, altura máxima limitada ao espaço disponível. É o
 * primitivo dos 5 popovers artesanais — actions-menu e combobox primeiro.
 *
 * O que ele NÃO faz de propósito: gerenciar foco/teclado do conteúdo (cada
 * padrão ARIA — menu, listbox — tem regras próprias, que ficam no dono) e
 * possuir o estado `open` (caller controla; aqui só se reporta fechamento).
 */
export function Popover({
  open,
  anchorRef,
  onClose,
  placement = "bottom-start",
  matchAnchorWidth = false,
  children,
  className,
}: PopoverProps) {
  // `open` liga o `isPositioned`: até a primeira conta de posição o painel
  // nasce em (0,0), no alto da tela, e com a animação de entrada aparecia ali
  // por um instante antes de pular para baixo do campo. Fica transparente até
  // estar no lugar (opacidade, não `visibility`: continua na árvore de
  // acessibilidade desde o primeiro quadro).
  const { refs, floatingStyles, isPositioned } = useFloating({
    open,
    placement,
    strategy: "fixed",
    whileElementsMounted: autoUpdate,
    elements: { reference: anchorRef.current },
    middleware: [
      offset(4),
      flip(() => ({ padding: margens() })),
      shift(() => ({ padding: margens() })),
      size(() => ({
        padding: margens(),
        apply({ availableHeight, rects, elements }) {
          elements.floating.style.maxHeight = `${Math.max(120, availableHeight)}px`;
          if (matchAnchorWidth) {
            elements.floating.style.minWidth = `${rects.reference.width}px`;
          }
        },
      })),
    ],
  });

  // Clique fora e Escape — sempre reportados ao caller.
  React.useEffect(() => {
    if (!open) return;
    function onDocMouseDown(e: MouseEvent) {
      const alvo = e.target as Node;
      if (anchorRef.current?.contains(alvo)) return;
      if (refs.floating.current?.contains(alvo)) return;
      onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        // Escape fecha só o painel. Sem isto o mesmo Escape chegava ao
        // `window`, onde o Dialog ouve, e fechava o diálogo inteiro junto —
        // perdendo o que já estava preenchido. (Listener do document roda
        // antes do do window na subida.)
        e.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose, anchorRef, refs.floating]);

  if (!open || typeof document === "undefined") return null;

  // Aberto de dentro de um diálogo, o painel sobe para `z-popover`: no
  // `z-dropdown` (abaixo de `z-modal`) a lista de um campo de busca abria
  // ATRÁS do diálogo. Fora de diálogo continua em `z-dropdown`, sob o
  // cabeçalho fixo (ver `margens`).
  const dentroDeDialogo = !!anchorRef.current?.closest('[role="dialog"]');

  return createPortal(
    <div
      ref={refs.setFloating}
      data-popover=""
      style={
        isPositioned
          ? floatingStyles
          : // Transparente, sem animação e sem receber clique — a entrada
            // (scale-in) só começa quando o painel já está no lugar.
            { ...floatingStyles, opacity: 0, animation: "none", pointerEvents: "none" }
      }
      className={cn(
        dentroDeDialogo ? "z-popover" : "z-dropdown",
        "flex flex-col overflow-hidden rounded-dropdown border border-border bg-card shadow-dropdown origin-top animate-scale-in",
        className,
      )}
    >
      {children}
    </div>,
    document.body,
  );
}

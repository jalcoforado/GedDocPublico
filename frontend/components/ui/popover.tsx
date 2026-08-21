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
  const { refs, floatingStyles } = useFloating({
    placement,
    strategy: "fixed",
    whileElementsMounted: autoUpdate,
    elements: { reference: anchorRef.current },
    middleware: [
      offset(4),
      flip({ padding: 8 }),
      shift({ padding: 8 }),
      size({
        padding: 8,
        apply({ availableHeight, rects, elements }) {
          elements.floating.style.maxHeight = `${Math.max(120, availableHeight)}px`;
          if (matchAnchorWidth) {
            elements.floating.style.minWidth = `${rects.reference.width}px`;
          }
        },
      }),
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
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("mousedown", onDocMouseDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocMouseDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onClose, anchorRef, refs.floating]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={refs.setFloating}
      data-popover=""
      style={floatingStyles}
      className={cn(
        "z-dropdown flex flex-col overflow-hidden rounded-dropdown border border-border bg-card shadow-dropdown animate-fade-in",
        className,
      )}
    >
      {children}
    </div>,
    document.body,
  );
}

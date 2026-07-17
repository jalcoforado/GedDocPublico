"use client";

import { ChevronDown, type LucideIcon } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ActionsMenuItem {
  /** Texto exibido no item de menu. */
  label: string;
  /** Ícone opcional à esquerda do label. */
  icon?: LucideIcon;
  /** Handler do clique no item. Recebe controle e fecha o menu automaticamente. */
  onClick: () => void;
  /** Se true, item aparece esmaecido e ignora cliques/teclas. */
  disabled?: boolean;
}

interface ActionsMenuProps {
  /** Texto do botão que abre o menu. */
  label: string;
  /** Ícone opcional do botão. */
  icon?: LucideIcon;
  /** Itens do menu. */
  items: ActionsMenuItem[];
  /** Variante do botão; default "secondary". */
  variant?: "primary" | "secondary" | "ghost";
  /** Tamanho do botão; default "sm". */
  size?: "sm" | "md";
  /** className extra no wrapper. */
  className?: string;
}

/**
 * Dropdown leve para agrupar ações relacionadas (ex: "Imprimir" com
 * Capa / Etiqueta / Etiqueta dupla / PDF completo).
 *
 * Sem dependências externas (sem Radix/HeadlessUI). Acessibilidade
 * mínima: role=menu, navegação Arrow/Enter/ESC, foco preserva último
 * item selecionado, click-outside fecha. Suficiente pra toolbars com
 * 3–6 itens.
 */
export function ActionsMenu({
  label,
  icon: Icon,
  items,
  variant = "secondary",
  size = "sm",
  className,
}: ActionsMenuProps) {
  const [open, setOpen] = React.useState(false);
  const [focusIdx, setFocusIdx] = React.useState<number>(-1);
  const wrapperRef = React.useRef<HTMLDivElement>(null);
  const itemRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  // Fecha em click fora.
  React.useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
        setFocusIdx(-1);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  // Foca o item quando focusIdx muda enquanto aberto.
  React.useEffect(() => {
    if (open && focusIdx >= 0) {
      itemRefs.current[focusIdx]?.focus();
    }
  }, [open, focusIdx]);

  function nextEnabled(from: number, dir: 1 | -1): number {
    const len = items.length;
    for (let step = 1; step <= len; step++) {
      const idx = (from + dir * step + len) % len;
      if (!items[idx]?.disabled) return idx;
    }
    return from;
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpen(true);
        setFocusIdx(nextEnabled(-1, 1));
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setFocusIdx(-1);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusIdx((i) => nextEnabled(i, 1));
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusIdx((i) => nextEnabled(i < 0 ? 0 : i, -1));
      return;
    }
    if (e.key === "Home") {
      e.preventDefault();
      setFocusIdx(nextEnabled(-1, 1));
      return;
    }
    if (e.key === "End") {
      e.preventDefault();
      setFocusIdx(nextEnabled(items.length, -1));
      return;
    }
  }

  function handleSelect(item: ActionsMenuItem) {
    if (item.disabled) return;
    setOpen(false);
    setFocusIdx(-1);
    item.onClick();
  }

  return (
    <div
      ref={wrapperRef}
      className={cn("relative inline-block", className)}
      onKeyDown={onKeyDown}
    >
      <Button
        type="button"
        variant={variant}
        size={size}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => {
            const next = !v;
            if (next) setFocusIdx(nextEnabled(-1, 1));
            else setFocusIdx(-1);
            return next;
          });
        }}
      >
        {Icon && <Icon className="h-4 w-4" aria-hidden="true" />}
        {label}
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 transition-transform",
            open && "rotate-180",
          )}
          aria-hidden="true"
        />
      </Button>

      {open && (
        <ul
          role="menu"
          className="absolute right-0 z-30 mt-1 min-w-[12rem] rounded-dropdown border border-border bg-surface-1 py-1 shadow-dropdown focus:outline-none"
        >
          {items.map((item, i) => {
            const ItemIcon = item.icon;
            return (
              <li key={i} role="none">
                <button
                  ref={(el) => {
                    itemRefs.current[i] = el;
                  }}
                  type="button"
                  role="menuitem"
                  disabled={item.disabled}
                  tabIndex={focusIdx === i ? 0 : -1}
                  onClick={() => handleSelect(item)}
                  className={cn(
                    "flex w-full items-center gap-2 px-3 py-2 text-left text-sm",
                    "transition-colors duration-fast",
                    "focus-visible:outline-none focus-visible:bg-muted focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset",
                    item.disabled
                      ? "cursor-not-allowed text-foreground-subtle opacity-50"
                      : "text-foreground hover:bg-muted",
                  )}
                >
                  {ItemIcon && (
                    <ItemIcon
                      className="h-4 w-4 shrink-0"
                      aria-hidden="true"
                    />
                  )}
                  <span className="truncate">{item.label}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

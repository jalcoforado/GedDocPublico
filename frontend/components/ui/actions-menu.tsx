"use client";

import { ChevronDown, type LucideIcon } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { Popover } from "@/components/ui/popover";
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
 * Desde a UX-02 (fatia 2.6) o painel sai pelo `Popover` (portal + Floating
 * UI): deixa de ser clipado por `overflow-hidden` e ganha flip/colisão de
 * viewport. Fechar — por Escape, clique fora ou seleção — devolve o foco ao
 * botão que abriu; antes o foco caía no body. Acessibilidade: role=menu,
 * navegação Arrow/Home/End/Enter, roving tabindex.
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
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  const itemRefs = React.useRef<(HTMLButtonElement | null)[]>([]);

  const close = React.useCallback((devolverFoco: boolean) => {
    setOpen(false);
    setFocusIdx(-1);
    if (devolverFoco) triggerRef.current?.focus();
  }, []);

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

  // No trigger E no painel (o portal tira o painel da árvore DOM do wrapper —
  // keydown de item não borbulha mais até aqui sem esta duplicação).
  function onKeyDown(e: React.KeyboardEvent) {
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
      close(true);
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
    close(true);
    item.onClick();
  }

  return (
    <div className={cn("relative inline-block", className)} onKeyDown={onKeyDown}>
      <Button
        ref={triggerRef}
        type="button"
        variant={variant}
        size={size}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          if (open) {
            close(false);
          } else {
            setOpen(true);
            setFocusIdx(nextEnabled(-1, 1));
          }
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

      <Popover
        open={open}
        anchorRef={triggerRef}
        onClose={() => close(true)}
        placement="bottom-end"
        className="min-w-[12rem] py-1"
      >
        <ul role="menu" onKeyDown={onKeyDown} className="focus:outline-none">
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
      </Popover>
    </div>
  );
}

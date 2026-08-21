"use client";

import { Check, ChevronDown, Search, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";

import { Popover } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface ComboboxOption<T = unknown> {
  value: number | string;
  label: string;
  hint?: string;
  data?: T;
}

interface ComboboxProps<T> {
  options: ComboboxOption<T>[];
  value: number | string | null;
  onChange: (value: number | string | null, option: ComboboxOption<T> | null) => void;
  placeholder?: string;
  searchPlaceholder?: string;
  emptyText?: string;
  disabled?: boolean;
  clearable?: boolean;
  /** Texto exibido ao final do dropdown — útil pra "cadastrar novo" */
  footer?: React.ReactNode;
  /** Loading externo (ex.: queryKey ainda fetchando) */
  loading?: boolean;
  /** Filtro custom — por padrão case-insensitive em label + hint */
  filter?: (option: ComboboxOption<T>, query: string) => boolean;
  className?: string;
  id?: string;
}

function defaultFilter<T>(option: ComboboxOption<T>, query: string): boolean {
  const q = query.toLowerCase();
  if (option.label.toLowerCase().includes(q)) return true;
  if (option.hint?.toLowerCase().includes(q)) return true;
  return false;
}

export function Combobox<T>({
  options,
  value,
  onChange,
  placeholder = "Selecione…",
  searchPlaceholder = "Buscar…",
  emptyText = "Nenhum resultado.",
  disabled,
  clearable = true,
  footer,
  loading,
  filter,
  className,
  id,
}: ComboboxProps<T>) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);

  const triggerRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const reactId = useId();
  const listboxId = id ? `${id}-listbox` : `cb-${reactId}-listbox`;

  const filterFn = filter ?? defaultFilter;
  const filtered = useMemo(() => {
    if (!query) return options;
    return options.filter((o) => filterFn(o, query));
  }, [options, query, filterFn]);

  const selected = options.find((o) => o.value === value) ?? null;

  // Posicionamento (flip/colisão/scroll/resize) e clique-fora agora são do
  // Popover (Floating UI) — eram ~60 linhas manuais aqui, a "6ª
  // reimplementação" que a spec §11 aposentou.
  const close = useCallback((devolverFoco = false) => {
    setOpen(false);
    setQuery("");
    setActiveIdx(0);
    // Escape/seleção devolvem o foco ao trigger; clique fora NÃO (o usuário
    // já está indo para outro lugar — roubar o foco de volta seria pior).
    if (devolverFoco) triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    if (activeIdx >= filtered.length) setActiveIdx(Math.max(0, filtered.length - 1));
  }, [filtered.length, activeIdx]);

  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector<HTMLLIElement>(
      `[data-idx="${activeIdx}"]`,
    );
    el?.scrollIntoView({ block: "nearest" });
  }, [activeIdx, open]);

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIdx((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIdx((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const opt = filtered[activeIdx];
      if (opt) {
        onChange(opt.value, opt);
        close(true);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      close(true);
    }
  }

  function pick(opt: ComboboxOption<T>) {
    onChange(opt.value, opt);
    close(true);
  }

  return (
    <div className={cn("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-11 w-full items-center justify-between gap-2 rounded-input border border-input bg-card px-3 text-sm shadow-input transition-colors duration-fast",
          "hover:border-border-strong hover:bg-muted/50",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
          "disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:border-input disabled:hover:bg-card",
        )}
      >
        <span
          className={cn(
            "min-w-0 flex-1 truncate text-left",
            selected ? "text-foreground" : "text-foreground-subtle",
          )}
        >
          {selected ? (
            <>
              {selected.label}
              {selected.hint && (
                <span className="ml-1 text-xs text-foreground-subtle">
                  · {selected.hint}
                </span>
              )}
            </>
          ) : (
            placeholder
          )}
        </span>
        <span
          className={cn(
            "flex items-center gap-1",
            // reserva o lugar do botão Limpar (irmão absoluto) para o texto não passar por baixo
            clearable && selected && !disabled && "mr-6",
          )}
        >
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-foreground-muted transition-transform duration-fast",
              open && "rotate-180",
            )}
            aria-hidden="true"
          />
        </span>
      </button>

      {/* Limpar mora FORA do trigger: botão dentro de botão é aninhamento
          interativo inválido — era por isso que ele vivia com tabIndex=-1,
          invisível ao teclado (fatia 2.6). */}
      {clearable && selected && !disabled && (
        <button
          type="button"
          aria-label="Limpar seleção"
          onClick={() => onChange(null, null)}
          className="absolute right-9 top-1/2 inline-flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-foreground-muted transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <X className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
      )}

      <Popover
        open={open}
        anchorRef={triggerRef}
        onClose={() => close(false)}
        matchAnchorWidth
        className="min-w-[220px]"
      >
        <>
            <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
              <Search
                className="h-4 w-4 shrink-0 text-foreground-muted"
                aria-hidden="true"
              />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActiveIdx(0);
                }}
                onKeyDown={handleKey}
                placeholder={searchPlaceholder}
                className="h-7 w-full border-0 bg-transparent text-sm outline-none placeholder:text-foreground-subtle"
                aria-autocomplete="list"
                aria-controls={listboxId}
                aria-activedescendant={
                  filtered[activeIdx]
                    ? `${listboxId}-opt-${filtered[activeIdx].value}`
                    : undefined
                }
              />
            </div>
            <ul
              ref={listRef}
              role="listbox"
              id={listboxId}
              className="min-h-0 flex-1 overflow-y-auto py-1"
            >
              {loading && (
                <li className="px-3 py-2 text-xs text-foreground-muted">
                  Carregando…
                </li>
              )}
              {!loading && filtered.length === 0 && (
                <li className="px-3 py-3 text-center text-xs text-foreground-subtle">
                  {emptyText}
                </li>
              )}
              {!loading &&
                filtered.map((opt, i) => {
                  const isActive = i === activeIdx;
                  const isSelected = opt.value === value;
                  return (
                    <li
                      key={opt.value}
                      id={`${listboxId}-opt-${opt.value}`}
                      role="option"
                      data-idx={i}
                      aria-selected={isSelected}
                      onMouseEnter={() => setActiveIdx(i)}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        pick(opt);
                      }}
                      className={cn(
                        "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm transition-colors duration-fast",
                        isActive
                          ? "bg-muted text-foreground"
                          : "text-foreground hover:bg-muted/60",
                      )}
                    >
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium">{opt.label}</div>
                        {opt.hint && (
                          <div className="truncate text-xs text-foreground-subtle">
                            {opt.hint}
                          </div>
                        )}
                      </div>
                      {isSelected && (
                        <Check
                          className="h-4 w-4 shrink-0 text-brand"
                          aria-hidden="true"
                        />
                      )}
                    </li>
                  );
                })}
            </ul>
        {footer && (
          <div className="border-t border-border bg-surface-2/40 px-3 py-2 text-xs">
            {footer}
          </div>
        )}
        </>
      </Popover>
    </div>
  );
}

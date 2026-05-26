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
  const containerRef = useRef<HTMLDivElement>(null);
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

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    setActiveIdx(0);
  }, []);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) {
        close();
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open, close]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  // Keep activeIdx in range
  useEffect(() => {
    if (activeIdx >= filtered.length) setActiveIdx(Math.max(0, filtered.length - 1));
  }, [filtered.length, activeIdx]);

  // Scroll active into view
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
        close();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    }
  }

  function pick(opt: ComboboxOption<T>) {
    onChange(opt.value, opt);
    close();
  }

  function clear(e: React.MouseEvent) {
    e.stopPropagation();
    onChange(null, null);
  }

  return (
    <div ref={containerRef} className={cn("relative", className)}>
      <button
        type="button"
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-11 w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 text-sm transition-colors duration-fast",
          "hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:cursor-not-allowed disabled:opacity-50",
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
        <span className="flex items-center gap-1">
          {clearable && selected && !disabled && (
            <span
              role="button"
              aria-label="Limpar seleção"
              tabIndex={-1}
              onClick={clear}
              className="inline-flex h-5 w-5 cursor-pointer items-center justify-center rounded text-foreground-muted hover:bg-muted hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </span>
          )}
          <ChevronDown
            className={cn(
              "h-4 w-4 shrink-0 text-foreground-muted transition-transform duration-fast",
              open && "rotate-180",
            )}
            aria-hidden="true"
          />
        </span>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-[calc(100%+4px)] z-50 overflow-hidden rounded-md border border-border bg-popover shadow-lg animate-fade-in">
          <div className="flex items-center gap-2 border-b border-border px-3 py-2">
            <Search className="h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
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
            className="max-h-72 overflow-y-auto py-1"
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
                      "flex cursor-pointer items-center justify-between gap-2 px-3 py-2 text-sm",
                      isActive
                        ? "bg-brand/5 text-foreground"
                        : "text-foreground",
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
                      <Check className="h-4 w-4 shrink-0 text-brand" aria-hidden="true" />
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
        </div>
      )}
    </div>
  );
}

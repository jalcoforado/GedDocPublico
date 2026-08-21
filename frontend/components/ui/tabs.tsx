"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface TabsContextValue {
  value: string;
  onChange: (value: string) => void;
  idBase: string;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabs(quem: string): TabsContextValue {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error(`${quem} deve ser usado dentro de <Tabs>`);
  return ctx;
}

interface TabsProps {
  value: string;
  onChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

/**
 * Tabs controladas com ARIA completo (UX-02 fatia 2.5): tablist/tab/tabpanel
 * ligados por aria-controls/aria-labelledby, roving tabindex e navegação por
 * setas/Home/End com wrap. Seleção segue o foco (padrão APG para conteúdo
 * carregado no cliente).
 */
export function Tabs({ value, onChange, children, className }: TabsProps) {
  const idBase = React.useId();
  const ctx = React.useMemo(() => ({ value, onChange, idBase }), [value, onChange, idBase]);
  return (
    <TabsContext.Provider value={ctx}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export interface TabDef {
  value: string;
  label: string;
  disabled?: boolean;
}

interface TabListProps {
  tabs: TabDef[];
  "aria-label": string;
  className?: string;
}

export function TabList({ tabs, className, ...aria }: TabListProps) {
  const { value, onChange, idBase } = useTabs("TabList");
  const refs = React.useRef(new Map<string, HTMLButtonElement>());

  const habilitadas = tabs.filter((t) => !t.disabled);

  function ativar(v: string) {
    onChange(v);
    refs.current.get(v)?.focus();
  }

  function onKeyDown(e: React.KeyboardEvent) {
    const atual = habilitadas.findIndex((t) => t.value === value);
    if (atual < 0) return;
    let proxima: number | null = null;
    if (e.key === "ArrowRight") proxima = (atual + 1) % habilitadas.length;
    else if (e.key === "ArrowLeft") proxima = (atual - 1 + habilitadas.length) % habilitadas.length;
    else if (e.key === "Home") proxima = 0;
    else if (e.key === "End") proxima = habilitadas.length - 1;
    if (proxima === null) return;
    e.preventDefault();
    ativar(habilitadas[proxima].value);
  }

  return (
    <div
      role="tablist"
      {...aria}
      onKeyDown={onKeyDown}
      className={cn("flex gap-1 border-b border-border", className)}
    >
      {tabs.map((t) => {
        const ativa = t.value === value;
        return (
          <button
            key={t.value}
            ref={(el) => {
              if (el) refs.current.set(t.value, el);
              else refs.current.delete(t.value);
            }}
            type="button"
            role="tab"
            id={`${idBase}-tab-${t.value}`}
            aria-selected={ativa}
            aria-controls={`${idBase}-panel-${t.value}`}
            tabIndex={ativa ? 0 : -1}
            disabled={t.disabled}
            onClick={() => onChange(t.value)}
            className={cn(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors duration-fast",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-50",
              ativa
                ? "border-brand text-brand"
                : "border-transparent text-foreground-muted hover:border-border-strong hover:text-foreground",
            )}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

interface TabPanelProps {
  value: string;
  children: React.ReactNode;
  className?: string;
}

export function TabPanel({ value, children, className }: TabPanelProps) {
  const { value: ativa, idBase } = useTabs("TabPanel");
  if (value !== ativa) return null;
  return (
    <div
      role="tabpanel"
      id={`${idBase}-panel-${value}`}
      aria-labelledby={`${idBase}-tab-${value}`}
      tabIndex={0}
      className={cn("pt-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring", className)}
    >
      {children}
    </div>
  );
}

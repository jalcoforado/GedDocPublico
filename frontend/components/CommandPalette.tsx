"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  BarChart3,
  Bell,
  Building2,
  ChevronRight,
  Cog,
  FileText,
  GitBranch,
  Home,
  KeyboardIcon,
  LogOut,
  Maximize2,
  Minimize2,
  Monitor,
  Moon,
  Network,
  Plus,
  Search,
  Shield,
  Sun,
  User,
  UserCircle,
  Users,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { buscaApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/* ---------- Tipos ---------- */

type CommandAction = {
  id: string;
  type: "navigate" | "action";
  title: string;
  subtitle?: string;
  icon: React.ComponentType<{ className?: string }>;
  href?: string;
  onSelect?: () => void;
  /** Categoria pra agrupar. */
  group: "navegar" | "criar" | "preferencias" | "conta" | "resultados";
  /** Keywords adicionais pro fuzzy filter. */
  keywords?: string[];
};

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/* ---------- Componente principal ---------- */

export function CommandPalette({ open, onOpenChange }: Props) {
  const router = useRouter();
  const { logout } = useAuth();
  const { setPreference, setDensity } = useTheme();
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [activeIdx, setActiveIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Reset state ao abrir
  useEffect(() => {
    if (open) {
      setQ("");
      setDebouncedQ("");
      setActiveIdx(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  // Debounce busca
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q]);

  // Resultados de busca quando >= 2 chars
  const searchQuery = useQuery({
    queryKey: ["cmd-busca", debouncedQ],
    queryFn: () => buscaApi.global(debouncedQ),
    enabled: open && debouncedQ.length >= 2,
  });

  /* ---- Ações estáticas ---- */
  const staticActions: CommandAction[] = useMemo(
    () => [
      // Navegar
      { id: "nav-home", type: "navigate", title: "Início", icon: Home, href: "/home", group: "navegar", keywords: ["dashboard", "início"] },
      { id: "nav-dash", type: "navigate", title: "Dashboard executivo", icon: BarChart3, href: "/dashboard", group: "navegar", keywords: ["kpi", "métricas", "bi"] },
      { id: "nav-processos", type: "navigate", title: "Processos", icon: FileText, href: "/processos", group: "navegar" },
      { id: "nav-workflow", type: "navigate", title: "Workflows", icon: GitBranch, href: "/workflow", group: "navegar", keywords: ["bpm", "fluxo"] },
      { id: "nav-org", type: "navigate", title: "Organograma", icon: Network, href: "/organograma", group: "navegar", keywords: ["unidades", "hierarquia"] },
      { id: "nav-audit", type: "navigate", title: "Auditoria", icon: Shield, href: "/auditoria", group: "navegar", keywords: ["log", "histórico"] },
      { id: "nav-usuarios", type: "navigate", title: "Usuários", icon: Users, href: "/usuarios", group: "navegar" },
      { id: "nav-unidades", type: "navigate", title: "Unidades", icon: Building2, href: "/unidades-trabalho", group: "navegar" },
      { id: "nav-manif", type: "navigate", title: "Manifestantes", icon: UserCircle, href: "/manifestantes", group: "navegar", keywords: ["cidadão", "requerente"] },
      { id: "nav-relat", type: "navigate", title: "Relatórios", icon: BarChart3, href: "/relatorios", group: "navegar" },
      { id: "nav-jobs", type: "navigate", title: "Jobs em background", icon: Cog, href: "/jobs", group: "navegar", keywords: ["celery", "tarefas"] },
      { id: "nav-perfil", type: "navigate", title: "Meu perfil", icon: User, href: "/perfil", group: "navegar" },
      { id: "nav-notif-prefs", type: "navigate", title: "Preferências de notificações", icon: Bell, href: "/perfil/notificacoes", group: "navegar", keywords: ["email", "whatsapp"] },

      // Criar
      { id: "act-novo-processo", type: "navigate", title: "Novo processo", icon: Plus, href: "/processos/novo", group: "criar" },
      { id: "act-novo-workflow", type: "navigate", title: "Novo workflow", icon: Plus, href: "/workflow/novo", group: "criar" },

      // Preferências (tema + densidade)
      { id: "pref-theme-system", type: "action", title: "Tema: seguir sistema", icon: Monitor, onSelect: () => setPreference("system"), group: "preferencias", keywords: ["theme", "auto", "modo"] },
      { id: "pref-theme-light", type: "action", title: "Tema: claro", icon: Sun, onSelect: () => setPreference("light"), group: "preferencias", keywords: ["theme", "light", "claro"] },
      { id: "pref-theme-dark", type: "action", title: "Tema: escuro", icon: Moon, onSelect: () => setPreference("dark"), group: "preferencias", keywords: ["theme", "dark", "escuro", "noturno"] },
      { id: "pref-density-comfortable", type: "action", title: "Densidade: confortável", icon: Maximize2, onSelect: () => setDensity("comfortable"), group: "preferencias", keywords: ["density", "espaçoso"] },
      { id: "pref-density-compact", type: "action", title: "Densidade: compacta", icon: Minimize2, onSelect: () => setDensity("compact"), group: "preferencias", keywords: ["density", "denso", "power-user"] },

      // Conta
      { id: "act-logout", type: "action", title: "Sair", icon: LogOut, onSelect: logout, group: "conta", keywords: ["logout", "sign out"] },
    ],
    [logout, setPreference, setDensity],
  );

  /* ---- Resultados de busca como ações ---- */
  const searchResults: CommandAction[] = useMemo(() => {
    const r = searchQuery.data;
    if (!r) return [];
    const procs: CommandAction[] = r.processos.map((p) => ({
      id: `proc-${p.id}`,
      type: "navigate",
      title: p.numero,
      subtitle: "Processo",
      icon: FileText,
      href: `/processos/${p.id}`,
      group: "resultados",
    }));
    const manifs: CommandAction[] = r.manifestantes.map((m) => ({
      id: `manif-${m.id}`,
      type: "navigate",
      title: m.nome,
      subtitle: `Manifestante${m.cpf_cnpj ? ` · ${m.cpf_cnpj}` : ""}`,
      icon: UserCircle,
      href: `/manifestantes`,
      group: "resultados",
    }));
    const usrs: CommandAction[] = r.usuarios.map((u) => ({
      id: `usr-${u.id}`,
      type: "navigate",
      title: u.nome,
      subtitle: `Usuário · ${u.email}`,
      icon: User,
      href: `/usuarios`,
      group: "resultados",
    }));
    return [...procs, ...manifs, ...usrs];
  }, [searchQuery.data]);

  /* ---- Filtro fuzzy nas ações estáticas ---- */
  const filteredStatic = useMemo(() => {
    if (debouncedQ.length === 0) return staticActions;
    const needle = debouncedQ.toLowerCase();
    return staticActions.filter((a) => {
      const hay = [a.title, a.subtitle ?? "", ...(a.keywords ?? [])]
        .join(" ")
        .toLowerCase();
      return hay.includes(needle);
    });
  }, [staticActions, debouncedQ]);

  /* ---- Lista final (search results primeiro quando há query, senão só static) ---- */
  const items: CommandAction[] = useMemo(() => {
    if (debouncedQ.length >= 2) {
      // Pinta os mais relevantes primeiro
      return [...searchResults, ...filteredStatic];
    }
    return filteredStatic;
  }, [debouncedQ, searchResults, filteredStatic]);

  // Mantém activeIdx dentro dos limites
  useEffect(() => {
    if (activeIdx >= items.length) setActiveIdx(Math.max(0, items.length - 1));
  }, [items.length, activeIdx]);

  function executeItem(item: CommandAction) {
    onOpenChange(false);
    if (item.type === "navigate" && item.href) {
      router.push(item.href);
    } else if (item.onSelect) {
      item.onSelect();
    }
  }

  /* ---- Atalho global Ctrl+K / Cmd+K ---- */
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        onOpenChange(!open);
      }
      if (open && e.key === "Escape") {
        e.preventDefault();
        onOpenChange(false);
      }
      if (open) {
        if (e.key === "ArrowDown") {
          e.preventDefault();
          setActiveIdx((i) => Math.min(items.length - 1, i + 1));
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          setActiveIdx((i) => Math.max(0, i - 1));
        } else if (e.key === "Enter") {
          e.preventDefault();
          const item = items[activeIdx];
          if (item) executeItem(item);
        }
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, items, activeIdx]);

  // Scroll auto pro item ativo
  useEffect(() => {
    if (!listRef.current) return;
    const el = listRef.current.querySelector<HTMLElement>(`[data-cmd-idx="${activeIdx}"]`);
    el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIdx]);

  if (!open) return null;

  // Agrupa pra render. CommandActionView é o que circula no UI: ganha
  // `_idx` (índice global pós-agrupamento, usado pelo teclado e foco).
  type CommandActionView = CommandAction & { _idx: number };
  const groups: { key: CommandAction["group"]; label: string; items: CommandActionView[] }[] = [];
  const groupLabels: Record<CommandAction["group"], string> = {
    resultados: "Resultados",
    navegar: "Navegar",
    criar: "Criar",
    preferencias: "Preferências",
    conta: "Conta",
  };
  let runningIdx = 0;
  const indexed: CommandActionView[] = items.map((it) => ({ ...it, _idx: runningIdx++ }));
  for (const g of ["resultados", "navegar", "criar", "preferencias", "conta"] as const) {
    const inGroup = indexed.filter((i) => i.group === g);
    if (inGroup.length > 0) {
      groups.push({ key: g, label: groupLabels[g], items: inGroup });
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Paleta de comandos"
      className="fixed inset-0 z-[100] flex items-start justify-center px-4 pt-[10vh] sm:pt-[15vh]"
    >
      {/* Backdrop */}
      <button
        type="button"
        aria-label="Fechar"
        onClick={() => onOpenChange(false)}
        className="absolute inset-0 bg-foreground/30 backdrop-blur-sm animate-fade-in"
      />

      {/* Panel */}
      <div
        className={cn(
          "relative w-full max-w-2xl overflow-hidden rounded-xl border border-border bg-surface-1 shadow-xl",
          "animate-scale-in",
        )}
      >
        {/* Input */}
        <div className="flex items-center gap-2 border-b border-border px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar processos, usuários, comandos…"
            aria-label="Comando ou busca"
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-foreground-subtle"
          />
          <kbd className="hidden items-center gap-0.5 rounded border border-border bg-muted px-1.5 py-0.5 text-[10px] font-mono text-foreground-muted sm:inline-flex">
            ESC
          </kbd>
        </div>

        {/* Lista */}
        <div
          ref={listRef}
          role="listbox"
          aria-label="Comandos disponíveis"
          className="max-h-[60vh] overflow-y-auto py-1"
        >
          {searchQuery.isLoading && debouncedQ.length >= 2 && (
            <div className="px-4 py-3 text-sm text-foreground-muted">
              Buscando…
            </div>
          )}
          {items.length === 0 && !searchQuery.isLoading && (
            <div className="px-4 py-8 text-center text-sm text-foreground-muted">
              Nada encontrado para “{debouncedQ}”.
            </div>
          )}
          {groups.map((g) => (
            <div key={g.key}>
              <div className="px-3 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
                {g.label}
              </div>
              {g.items.map((it) => {
                const Icon = it.icon;
                const isActive = it._idx === activeIdx;
                return (
                  <button
                    key={it.id}
                    type="button"
                    data-cmd-idx={it._idx}
                    role="option"
                    aria-selected={isActive}
                    onMouseEnter={() => setActiveIdx(it._idx)}
                    onClick={() => executeItem(it)}
                    className={cn(
                      "flex w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors",
                      isActive
                        ? "bg-brand/10 text-foreground dark:bg-brand/20"
                        : "text-foreground-muted hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon
                      className={cn(
                        "h-4 w-4 shrink-0",
                        isActive ? "text-brand dark:text-brand-light" : "",
                      )}
                      aria-hidden="true"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-medium">{it.title}</div>
                      {it.subtitle && (
                        <div className="truncate text-[11px] text-foreground-subtle">
                          {it.subtitle}
                        </div>
                      )}
                    </div>
                    {isActive && (
                      <ChevronRight
                        className="h-3.5 w-3.5 shrink-0 text-foreground-muted"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer com atalhos */}
        <div className="flex items-center justify-between border-t border-border bg-surface-2 px-3 py-1.5 text-[10px] text-foreground-subtle">
          <span className="flex items-center gap-2">
            <KeyboardIcon className="h-3 w-3" aria-hidden="true" />
            <Kbd>↑</Kbd> <Kbd>↓</Kbd> navegar · <Kbd>↵</Kbd> abrir
          </span>
          <span className="flex items-center gap-1">
            <Kbd>Ctrl</Kbd>+<Kbd>K</Kbd> abre
          </span>
        </div>
      </div>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center rounded border border-border bg-surface-1 px-1 py-0.5 font-mono text-[9px] text-foreground-muted">
      {children}
    </kbd>
  );
}

/* ---------- Hook + Provider de conveniência ---------- */

import { createContext, useCallback, useContext } from "react";

const CommandPaletteContext = createContext<{ open: () => void } | null>(null);

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const openFn = useCallback(() => setOpen(true), []);
  return (
    <CommandPaletteContext.Provider value={{ open: openFn }}>
      {children}
      <CommandPalette open={open} onOpenChange={setOpen} />
    </CommandPaletteContext.Provider>
  );
}

export function useCommandPalette() {
  const ctx = useContext(CommandPaletteContext);
  return ctx;
}

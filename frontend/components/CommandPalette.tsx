"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  ChevronRight,
  FileText,
  KeyboardIcon,
  LogOut,
  Maximize2,
  Minimize2,
  Monitor,
  Moon,
  Plus,
  Search,
  Sun,
  User,
  UserCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { api, buscaApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { canSeeItem, itensNavegaveis, type NavItem } from "@/lib/menus";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

/**
 * Itens que a paleta oferecia SEM ter item correspondente em `lib/menus` —
 * telas de perfil (não pertencem a nenhum módulo, sempre visíveis) e atalhos
 * de criação (mesmo módulo/permissão da tela de listagem equivalente). Não
 * vêm de `itensNavegaveis()` porque não há link para eles na Sidebar.
 * `moduloSlug: "comum"` marca "nunca bloqueado por módulo", igual ao grupo
 * transversal de `lib/menus/comum.ts`.
 */
export const ITENS_EXTRA: ReadonlyArray<{ item: NavItem; moduloSlug: string; group: "navegar" | "criar" }> = [
  { moduloSlug: "comum", group: "navegar", item: { label: "Meu perfil", href: "/perfil", icon: User } },
  {
    moduloSlug: "comum",
    group: "navegar",
    item: { label: "Preferências de notificações", href: "/perfil/notificacoes", icon: Bell },
  },
  {
    moduloSlug: "protocolo",
    group: "criar",
    item: { label: "Novo processo", href: "/m/protocolo/processos/novo", icon: Plus, perm: "processo" },
  },
  {
    moduloSlug: "protocolo",
    group: "criar",
    item: { label: "Novo workflow", href: "/m/protocolo/workflow/novo", icon: Plus },
  },
];

/**
 * Keywords que os itens estáticos antigos tinham e `lib/menus` não guarda
 * (o menu não precisa de sinônimo de busca, a paleta precisa). Perder essas
 * palavras-chave não quebraria teste nenhum — só pioraria o fuzzy match
 * silenciosamente, então ficam preservadas aqui em vez de descartadas.
 */
export const KEYWORDS_POR_HREF: Record<string, string[]> = {
  "/home": ["dashboard", "início"],
  "/m/protocolo/workflow": ["bpm", "fluxo"],
  "/m/administracao/organograma": ["unidades", "hierarquia"],
  "/m/administracao/auditoria": ["log", "histórico"],
  "/m/administracao/jobs": ["celery", "tarefas"],
  "/m/protocolo/manifestantes": ["cidadão", "requerente"],
  "/m/transporte/recadastramento": ["ciclo", "convocação", "prazo", "escalonamento"],
  "/m/transporte/linhas": ["linha", "itinerario", "horario", "distrital", "escolar"],
  "/perfil/notificacoes": ["email", "whatsapp"],
};

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
  const { logout, can } = useAuth();
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

  // Módulos contratados do tenant — MESMA queryKey que ModuloSwitcher e o
  // launcher usam (não inventa chave nova). Herda o cache: a paleta abre por
  // cima de uma página já montada dentro de `(app)`, então o dado costuma já
  // estar quente quando o usuário aperta Ctrl+K.
  const modulosQuery = useQuery({ queryKey: ["modulos-me"], queryFn: api.modulos });
  const modulosContratados = useMemo(
    () => new Set((modulosQuery.data?.itens ?? []).map((m) => m.slug)),
    [modulosQuery.data],
  );
  // "comum" nunca é bloqueado — mesma regra do backend e da Sidebar. Enquanto
  // o dado não chegou (loading/erro), itens de módulo ficam de fora: mais
  // seguro esconder um item por um instante do que oferecer um que 403.
  const moduloLiberado = (slug: string) => slug === "comum" || modulosContratados.has(slug);

  /* ---- Ações estáticas ---- */
  const staticActions: CommandAction[] = useMemo(() => {
    // Fonte única: os itens de navegação vêm de `lib/menus`, os mesmos que a
    // Sidebar mostra — filtrados por módulo contratado e, com a MESMA
    // `canSeeItem` da Sidebar, por permissão. Duas cópias da poda divergem;
    // esta paleta era a segunda cópia até esta mudança.
    const doMenu: CommandAction[] = itensNavegaveis()
      .filter(({ moduloSlug, item }) => moduloLiberado(moduloSlug) && canSeeItem(item, can))
      .map(({ item }) => ({
        id: `nav-${item.href}`,
        type: "navigate" as const,
        title: item.label,
        icon: item.icon,
        href: item.href,
        group: "navegar" as const,
        keywords: KEYWORDS_POR_HREF[item.href],
      }));

    // Telas/atalhos sem item de menu equivalente — não vêm de `lib/menus`,
    // mas passam pelo mesmo filtro de módulo/permissão.
    const extras: CommandAction[] = ITENS_EXTRA.filter(
      ({ moduloSlug, item }) => moduloLiberado(moduloSlug) && canSeeItem(item, can),
    ).map(({ item, group }) => ({
      id: `extra-${item.href}`,
      type: "navigate" as const,
      title: item.label,
      icon: item.icon,
      href: item.href,
      group,
      keywords: KEYWORDS_POR_HREF[item.href],
    }));

    return [
      ...doMenu,
      ...extras,

      // Preferências (tema + densidade)
      { id: "pref-theme-system", type: "action", title: "Tema: seguir sistema", icon: Monitor, onSelect: () => setPreference("system"), group: "preferencias", keywords: ["theme", "auto", "modo"] },
      { id: "pref-theme-light", type: "action", title: "Tema: claro", icon: Sun, onSelect: () => setPreference("light"), group: "preferencias", keywords: ["theme", "light", "claro"] },
      { id: "pref-theme-dark", type: "action", title: "Tema: escuro", icon: Moon, onSelect: () => setPreference("dark"), group: "preferencias", keywords: ["theme", "dark", "escuro", "noturno"] },
      { id: "pref-density-comfortable", type: "action", title: "Densidade: confortável", icon: Maximize2, onSelect: () => setDensity("comfortable"), group: "preferencias", keywords: ["density", "espaçoso"] },
      { id: "pref-density-compact", type: "action", title: "Densidade: compacta", icon: Minimize2, onSelect: () => setDensity("compact"), group: "preferencias", keywords: ["density", "denso", "power-user"] },

      // Conta
      { id: "act-logout", type: "action", title: "Sair", icon: LogOut, onSelect: logout, group: "conta", keywords: ["logout", "sign out"] },
    ];
  }, [can, modulosContratados, logout, setPreference, setDensity]);

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
      href: `/m/protocolo/processos/${p.id}`,
      group: "resultados",
    }));
    const manifs: CommandAction[] = r.manifestantes.map((m) => ({
      id: `manif-${m.id}`,
      type: "navigate",
      title: m.nome,
      subtitle: `Manifestante${m.cpf_cnpj ? ` · ${m.cpf_cnpj}` : ""}`,
      icon: UserCircle,
      href: `/m/protocolo/manifestantes`,
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
      className="fixed inset-0 z-popover flex items-start justify-center px-4 pt-[10vh] sm:pt-[15vh]"
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

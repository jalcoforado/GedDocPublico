"use client";

import {
  ChevronDown,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  Shield,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { canSeeItem, MENUS, menuDoModulo, type NavGroup, type NavItem } from "@/lib/menus";
import { cn } from "@/lib/utils";
import { DensityToggle } from "./DensityToggle";
import { Popover } from "@/components/ui/popover";
import { SidebarModuloHeader } from "./SidebarModuloHeader";
import { ThemeToggle } from "./ThemeToggle";

function isPathActive(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

/** True se o item OU algum descendente corresponde ao pathname atual. */
function itemMatchesPath(item: NavItem, pathname: string): boolean {
  if (isPathActive(item.href, pathname)) return true;
  return item.children?.some((c) => itemMatchesPath(c, pathname)) ?? false;
}

interface SidebarProps {
  /** Slug do módulo ativo (derivado de `moduloDoPathname`), ou `null` em rota transversal. */
  modulo: string | null;
  open: boolean;
  onClose: () => void;
}

const COLLAPSED_KEY = "aprimora.sidebar.collapsed";
const GROUP_STATE_KEY = "aprimora.sidebar.groups.v1";
const FOCUSABLE =
  'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function Sidebar({ modulo, open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { can } = useAuth();
  const branding = useBranding();
  // Transversais (comum) sempre primeiro — é a ordem do NAV original ("Geral"
  // abria a lista) e continua sendo o caminho de volta para /home e
  // /dashboard, agora no topo em vez do fim. Depois vêm os grupos do módulo
  // ativo. "comum" nunca duplica: menuDoModulo(null) devolve null, e o guard
  // `menu.slug !== "comum"` evita repetir o grupo se algum dia o slug do
  // pathname vier como "comum" por engano (hoje nenhuma entrada de
  // ROTA_MODULO mapeia para "comum" — é defesa, não caminho alcançável).
  const menu = menuDoModulo(modulo);
  const NAV: NavGroup[] = [
    ...MENUS.comum.grupos,
    ...(menu && menu.slug !== "comum" ? menu.grupos : []),
  ];
  // PR3a — link de plataforma só aparece para admin de plataforma (allowlist).
  const adminMeQ = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => api.admin.me(),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const isPlatformAdmin = adminMeQ.data?.is_platform_admin ?? false;
  const lastPath = useRef(pathname);
  // Collapsed (icon-only) — só faz sentido em desktop. Persistido em
  // localStorage E espelhado no <html> pelo THEME_INIT_SCRIPT: o initializer
  // lê a marca para o PRIMEIRO render já sair no estado certo (anti-FOUC,
  // fatia 3.2) — antes, um useEffect corrigia depois e a sidebar piscava.
  const [collapsed, setCollapsed] = useState(
    () =>
      typeof document !== "undefined" &&
      document.documentElement.dataset.sidebarCollapsed === "1",
  );
  // Tablets (768–1024, fatia 3.8): sidebar colapsada SEMPRE presente em vez
  // de drawer — largura sobra para 68px de ícones, e o hambúrguer custava um
  // toque por navegação. A preferência do usuário volta a mandar fora da faixa.
  const TABLET_QUERY = "(min-width: 768px) and (max-width: 1023.98px)";
  const [tablet, setTablet] = useState(
    () => typeof window !== "undefined" && window.matchMedia(TABLET_QUERY).matches,
  );
  useEffect(() => {
    const mq = window.matchMedia(TABLET_QUERY);
    const atualiza = () => setTablet(mq.matches);
    mq.addEventListener?.("change", atualiza);
    return () => mq.removeEventListener?.("change", atualiza);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const colapsada = collapsed || tablet;
  // Grupos abertos/fechados — chave: title do grupo. O estado salvo entra já
  // no initializer (anti-FOUC, fatia 3.2): via useEffect os grupos piscavam
  // no default e colapsavam um frame depois.
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>(() => {
    const defaults = Object.fromEntries(NAV.map((g) => [g.title, g.defaultOpen ?? true]));
    try {
      const raw = localStorage.getItem(GROUP_STATE_KEY);
      if (raw) return { ...defaults, ...(JSON.parse(raw) as Record<string, boolean>) };
    } catch {
      /* ignore */
    }
    return defaults;
  });
  // Subgrupos (item com children) abertos/fechados — chave: label do item.
  // Não persistido (não exigido); abre sozinho se um filho estiver ativo.
  const [subOpen, setSubOpen] = useState<Record<string, boolean>>({});
  const toggleSub = (label: string) =>
    setSubOpen((prev) => ({ ...prev, [label]: !prev[label] }));


  // Auto-expand o grupo que contém o item ativo (não fecha grupos abertos).
  useEffect(() => {
    const activeGroup = NAV.find((g) => g.items.some((i) => itemMatchesPath(i, pathname)));
    if (activeGroup && !groupOpen[activeGroup.title]) {
      setGroupOpen((prev) => ({ ...prev, [activeGroup.title]: true }));
    }
    // Auto-expand o subgrupo que contém o filho ativo.
    const activeParent = NAV.flatMap((g) => g.items).find(
      (i) => i.children && i.children.some((c) => itemMatchesPath(c, pathname)),
    );
    if (activeParent && !subOpen[activeParent.label]) {
      setSubOpen((prev) => ({ ...prev, [activeParent.label]: true }));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, next ? "1" : "0");
        // espelha a marca que o THEME_INIT_SCRIPT lê no próximo load
        if (next) document.documentElement.dataset.sidebarCollapsed = "1";
        else delete document.documentElement.dataset.sidebarCollapsed;
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  const toggleGroup = (title: string) => {
    setGroupOpen((prev) => {
      const next = { ...prev, [title]: !prev[title] };
      try {
        localStorage.setItem(GROUP_STATE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  };

  useEffect(() => {
    if (lastPath.current !== pathname) {
      lastPath.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

  // Drawer mobile como Dialog-pattern (UX-03 fatia 3.1): ESC fecha, Tab fica
  // preso dentro, o foco entra ao abrir e volta ao gatilho ao fechar. `open`
  // só é true no drawer (o hambúrguer é lg:hidden); em desktop a nav é
  // estática e nada disto roda.
  const navRef = useRef<HTMLElement>(null);
  const focoAnterior = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const nav = navRef.current;
    const ativo = document.activeElement;
    if (ativo instanceof HTMLElement && !nav?.contains(ativo)) {
      focoAnterior.current = ativo;
    }
    if (nav && !nav.contains(document.activeElement)) {
      nav.querySelector<HTMLElement>(FOCUSABLE)?.focus();
    }

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab") return;
      const focaveis = navRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
      if (!focaveis || focaveis.length === 0) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];
      const atual = document.activeElement;
      if (e.shiftKey && atual === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && atual === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      const anterior = focoAnterior.current;
      focoAnterior.current = null;
      if (anterior?.isConnected) anterior.focus();
    };
  }, [open, onClose]);

  // Clicar em link da ROTA ATUAL não muda o pathname — o efeito acima nunca
  // fecharia. Qualquer clique em <a> dentro do drawer aberto fecha.
  function fechaAoClicarLink(e: React.MouseEvent) {
    if (!open) return;
    if ((e.target as HTMLElement).closest("a")) onClose();
  }

  // Calcula quais grupos têm o item ativo (pra realçar o header).
  const activeGroupTitle = useMemo(() => {
    return NAV.find((g) => g.items.some((i) => itemMatchesPath(i, pathname)))?.title;
  }, [pathname]);

  return (
    <>
      {/* Camadas do drawer mobile, pela escala `--z-*`: o Header é `z-sticky`,
          o overlay fica acima dele (`z-modal-backdrop`) e o painel acima do
          overlay (`z-modal`). Em desktop o painel é lg:static e o z não
          interfere. Ordem travada em __tests__/z-index-camadas.test.ts. */}
      <div
        onClick={onClose}
        aria-hidden="true"
        data-testid="sidebar-overlay"
        className={cn(
          "fixed inset-0 z-modal-backdrop bg-black/50 transition-opacity duration-200 md:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <nav
        ref={navRef}
        aria-label="Navegação principal"
        onClick={fechaAoClicarLink}
        data-collapsed={colapsada}
        className={cn(
          "fixed inset-y-0 left-0 z-modal flex w-72 shrink-0 flex-col overflow-hidden",
          "border-r border-sidebar-border bg-sidebar text-sidebar-foreground pt-safe transition-[transform,width] duration-base ease-out-expo",
          "md:static md:w-[68px] md:translate-x-0",
          !colapsada && "lg:w-64",
          open ? "translate-x-0 shadow-xl" : "-translate-x-full shadow-none md:translate-x-0",
        )}
      >
        {/* Brand block */}
        <div className="flex items-center justify-between gap-2 border-b border-sidebar-border px-3 py-4">
          <Link
            href="/home"
            className={cn(
              "flex items-center gap-2.5 rounded px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              colapsada && "md:justify-center md:gap-0",
            )}
            aria-label="Início"
            title={colapsada ? branding?.nome ?? "Aprimora" : undefined}
          >
            {branding?.logo_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={branding.logo_url}
                alt={branding.nome ?? "Aprimora"}
                className="h-9 w-9 rounded-md object-cover"
              />
            ) : (
              <div
                aria-hidden="true"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-brand-gradient text-base font-bold text-white shadow-brand"
              >
                A
              </div>
            )}
            <div className={cn(colapsada && "md:hidden")}>
              <div className="text-base font-semibold leading-tight tracking-tight">
                {branding?.nome ?? "Aprimora"}
              </div>
              <div className="text-[10px] uppercase tracking-wider text-sidebar-muted">
                Gestão de processos
              </div>
            </div>
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar menu"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground md:hidden"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Cabeçalho de módulo — onde o usuário está e o caminho de volta a
            /modulos. Acima de todos os grupos, de propósito (ver componente). */}
        <SidebarModuloHeader modulo={modulo} collapsed={colapsada} />

        {/* Items */}
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto px-2 py-2">
          {NAV.map((group) => {
            const visible = group.items
              .filter((item) => canSeeItem(item, can))
              .map((item) =>
                item.children
                  ? { ...item, children: item.children.filter((c) => canSeeItem(c, can)) }
                  : item,
              )
              .filter((item) => !item.children || item.children.length > 0);
            if (visible.length === 0) return null;
            const isOpen = groupOpen[group.title] ?? group.defaultOpen ?? true;
            const groupIsActive = activeGroupTitle === group.title;
            // Em collapsed mode (icon-only), grupos não colapsam — sempre mostra itens.
            const showItems = colapsada || isOpen;
            const slugId = `nav-group-${group.title.toLowerCase().replace(/\s+/g, "-")}`;

            return (
              <div key={group.title} className="rounded-md">
                {/* Group header — clicável (exceto em collapsed mode, vira só separador). */}
                {colapsada ? (
                  <div
                    className="my-1 hidden h-px w-full bg-sidebar-border md:block"
                    aria-hidden="true"
                  />
                ) : (
                  <button
                    type="button"
                    onClick={() => toggleGroup(group.title)}
                    aria-expanded={isOpen}
                    aria-controls={slugId}
                    className={cn(
                      "flex w-full items-center gap-1.5 rounded-md px-2 py-1.5 text-left transition-colors duration-fast",
                      "hover:bg-sidebar-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      groupIsActive && "text-sidebar-foreground",
                    )}
                  >
                    <ChevronDown
                      className={cn(
                        "h-3 w-3 shrink-0 text-sidebar-muted transition-transform duration-fast",
                        !isOpen && "-rotate-90",
                      )}
                      aria-hidden="true"
                    />
                    <span
                      className={cn(
                        "flex-1 text-[10px] font-semibold uppercase tracking-wider",
                        groupIsActive ? "text-sidebar-foreground" : "text-sidebar-muted",
                      )}
                    >
                      {group.title}
                    </span>
                    {!isOpen && groupIsActive && (
                      <span
                        className="h-1.5 w-1.5 rounded-full bg-accent"
                        aria-label="Página atual neste grupo"
                      />
                    )}
                  </button>
                )}

                {/* Items do grupo */}
                <div
                  id={slugId}
                  className={cn("flex flex-col gap-0.5", !showItems && "hidden")}
                >
                  {visible.map((item) => {
                    const Icon = item.icon;
                    const active = isPathActive(item.href, pathname);

                    if (item.children && item.children.length > 0 && !colapsada) {
                      const subIsOpen = subOpen[item.label] ?? false;
                      const subSlugId = `nav-sub-${item.label.toLowerCase().replace(/\s+/g, "-")}`;
                      const subGroupActive = item.children.some((c) => isPathActive(c.href, pathname));
                      return (
                        <div key={item.label}>
                          <button
                            type="button"
                            onClick={() => toggleSub(item.label)}
                            aria-expanded={subIsOpen}
                            aria-controls={subSlugId}
                            className={cn(
                              "group relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                              subGroupActive
                                ? "text-sidebar-foreground"
                                : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                            )}
                          >
                            <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                            <span className="flex-1 text-left">{item.label}</span>
                            <ChevronRight
                              className={cn(
                                "h-3.5 w-3.5 shrink-0 text-sidebar-muted transition-transform duration-fast",
                                subIsOpen && "rotate-90",
                              )}
                              aria-hidden="true"
                            />
                          </button>
                          <div
                            id={subSlugId}
                            className={cn("ml-3 flex flex-col gap-0.5 border-l border-sidebar-border pl-2", !subIsOpen && "hidden")}
                          >
                            {item.children.map((child) => {
                              const ChildIcon = child.icon;
                              const childActive = isPathActive(child.href, pathname);
                              return (
                                <Link
                                  key={child.href}
                                  href={child.href}
                                  aria-current={childActive ? "page" : undefined}
                                  className={cn(
                                    "group relative flex items-center gap-3 rounded-md px-3 py-1.5 text-sm font-medium transition-colors duration-fast",
                                    childActive
                                      ? "bg-sidebar-active text-sidebar-foreground"
                                      : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                                  )}
                                >
                                  <span
                                    aria-hidden="true"
                                    className={cn(
                                      "absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full transition-all duration-fast",
                                      childActive ? "bg-accent" : "bg-transparent group-hover:bg-sidebar-border",
                                    )}
                                  />
                                  <ChildIcon
                                    className={cn(
                                      "h-4 w-4 shrink-0 transition-colors",
                                      childActive ? "text-accent" : "",
                                    )}
                                    aria-hidden="true"
                                  />
                                  <span className="flex-1">{child.label}</span>
                                </Link>
                              );
                            })}
                          </div>
                        </div>
                      );
                    }

    // Pai com children em modo collapsed: flyout com os filhos (fatia 3.6) —
                    // a versão anterior virava link para o 1º filho, uma troca
                    // silenciosa de destino que o usuário não pedia.
                    if (colapsada && item.children && item.children.length > 0) {
                      return (
                        <ItemColapsadoComFilhos
                          key={item.label}
                          item={item}
                          pathname={pathname}
                        />
                      );
                    }
                    const linkHref = item.href;
                    const linkActive = active;

                    return (
                      <Link
                        key={item.label}
                        href={linkHref}
                        aria-current={linkActive ? "page" : undefined}
                        title={colapsada ? item.label : undefined}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                          colapsada && "md:justify-center md:gap-0 md:px-0",
                          linkActive
                            ? "bg-sidebar-active text-sidebar-foreground"
                            : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
                        )}
                      >
                        <span
                          aria-hidden="true"
                          className={cn(
                            "absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full transition-all duration-fast",
                            linkActive ? "bg-accent" : "bg-transparent group-hover:bg-sidebar-border",
                          )}
                        />
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            linkActive ? "text-accent" : "",
                          )}
                          aria-hidden="true"
                        />
                        {/* sr-only, não hidden: o rótulo continua sendo o nome
                            acessível do link no modo colapsado (fatia 3.6) */}
                        <span className={cn("flex-1", colapsada && "md:sr-only")}>
                          {item.label}
                        </span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {isPlatformAdmin && (
            <Link
              href="/admin/tenants"
              title={colapsada ? "Plataforma" : undefined}
              aria-current={isPathActive("/admin", pathname) ? "page" : undefined}
              className={cn(
                "group relative mt-1 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                colapsada && "md:justify-center md:gap-0 md:px-0",
                isPathActive("/admin", pathname)
                  ? "bg-sidebar-active text-sidebar-foreground"
                  : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
            >
              <Shield className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className={cn("flex-1", colapsada && "md:sr-only")}>Plataforma</span>
            </Link>
          )}
        </div>

        {/* Footer com toggles */}
        <div
          className={cn(
            "flex items-center gap-2 border-t border-sidebar-border bg-sidebar-accent/50 px-3 py-3",
            colapsada ? "md:flex-col" : "justify-between",
          )}
        >
          <div className={cn(colapsada && "md:hidden")}>
            <ThemeToggle />
          </div>
          <div className="flex items-center gap-1.5">
            <DensityToggle />
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
              title={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
              className="hidden h-9 w-9 items-center justify-center rounded-md border border-sidebar-border bg-sidebar text-sidebar-muted transition-colors duration-fast hover:bg-sidebar-accent hover:text-sidebar-foreground lg:inline-flex"
            >
              {collapsed ? (
                <ChevronsRight className="h-4 w-4" aria-hidden="true" />
              ) : (
                <ChevronsLeft className="h-4 w-4" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </nav>
    </>
  );
}

/**
 * Item-pai com filhos no modo colapsado (fatia 3.6): botão que abre um
 * flyout à direita com os filhos — clicar no pai não navega para lugar
 * nenhum sozinho.
 */
function ItemColapsadoComFilhos({
  item,
  pathname,
}: {
  item: NavItem;
  pathname: string;
}) {
  const [aberto, setAberto] = useState(false);
  const gatilhoRef = useRef<HTMLButtonElement>(null);
  const ativo = item.children!.some((c) => isPathActive(c.href, pathname));
  const Icon = item.icon;

  const fechar = () => {
    setAberto(false);
    gatilhoRef.current?.focus();
  };

  return (
    <div className="relative">
      <button
        ref={gatilhoRef}
        type="button"
        aria-haspopup="true"
        aria-expanded={aberto}
        title={item.label}
        onClick={() => setAberto((v) => !v)}
        className={cn(
          "group relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
          "md:justify-center md:gap-0 md:px-0",
          ativo
            ? "bg-sidebar-active text-sidebar-foreground"
            : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
        )}
      >
        <Icon className={cn("h-4 w-4 shrink-0", ativo && "text-accent")} aria-hidden="true" />
        <span className="flex-1 md:sr-only">{item.label}</span>
      </button>
      <Popover
        open={aberto}
        anchorRef={gatilhoRef}
        onClose={fechar}
        placement="right-start"
        className="min-w-[12rem] py-1"
      >
        {/* Links de navegação, não menu de ações — sem role=menu para não
            mascarar o role de link dos filhos. */}
        <nav aria-label={item.label}>
          {item.children!.map((child) => {
            const ChildIcon = child.icon;
            const childActive = isPathActive(child.href, pathname);
            return (
              <Link
                key={child.href}
                href={child.href}
                aria-current={childActive ? "page" : undefined}
                onClick={() => setAberto(false)}
                className={cn(
                  "flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors duration-fast",
                  childActive
                    ? "bg-muted text-foreground"
                    : "text-foreground hover:bg-muted",
                )}
              >
                <ChildIcon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span className="truncate">{child.label}</span>
              </Link>
            );
          })}
        </nav>
      </Popover>
    </div>
  );
}

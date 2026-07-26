"use client";

import {
  BarChart3,
  Banknote,
  BookOpen,
  Building2,
  Bus,
  CalendarClock,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  ChevronsLeft,
  ChevronsRight,
  Cog,
  FileText,
  FolderTree,
  GitBranch,
  Home,
  IdCard,
  Inbox,
  Layers,
  ListChecks,
  Map,
  MapPin,
  Car,
  Paperclip,
  PenSquare,
  Settings,
  Shield,
  ShieldCheck,
  Tag,
  Truck,
  UserCircle,
  Users,
  Wallet,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";
import { DensityToggle } from "./DensityToggle";
import { ThemeToggle } from "./ThemeToggle";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  perm?: string;
  anyOf?: string[];
  /** Subitens — vira um subgrupo colapsável (chevron) dentro do grupo pai. */
  children?: NavItem[];
}

interface NavGroup {
  title: string;
  items: NavItem[];
  /** Estado inicial do grupo (antes da hidratação do localStorage). */
  defaultOpen?: boolean;
}

const NAV: NavGroup[] = [
  {
    title: "Geral",
    defaultOpen: true,
    items: [
      { label: "Início", href: "/home", icon: Home },
      { label: "Dashboard", href: "/dashboard", icon: BarChart3 },
      { label: "Organograma", href: "/organograma", icon: Building2 },
    ],
  },
  {
    title: "Processos",
    defaultOpen: true,
    items: [
      { label: "Processos", href: "/processos", icon: FileText, perm: "processo" },
      { label: "Para assinar", href: "/para-assinar", icon: PenSquare },
      { label: "Workflows", href: "/workflow", icon: GitBranch },
      { label: "Relatórios", href: "/relatorios", icon: BarChart3, perm: "processo" },
    ],
  },
  {
    title: "Protocolo",
    defaultOpen: true,
    items: [
      { label: "Balcão", href: "/protocolo/balcao", icon: Inbox, perm: "processo" },
      {
        label: "Vencendo prazo",
        href: "/protocolo/vencendo-prazo",
        icon: CalendarClock,
        perm: "processo",
      },
      {
        label: "CCD (Classificação)",
        href: "/protocolo/ccd",
        icon: FolderTree,
        perm: "catalogo",
      },
      {
        label: "TTD (Temporalidade)",
        href: "/protocolo/ttd",
        icon: CalendarClock,
        perm: "catalogo",
      },
    ],
  },
  {
    title: "Cadastros",
    defaultOpen: false,
    items: [
      { label: "Manifestantes", href: "/manifestantes", icon: UserCircle, perm: "manifestante" },
      { label: "Tipos de Manifestante", href: "/tipos-manifestante", icon: Tag, perm: "manifestante" },
      { label: "Tipos de Processo", href: "/tipos-processo", icon: Layers, perm: "catalogo" },
      { label: "Assuntos", href: "/assuntos", icon: BookOpen, perm: "assunto" },
      { label: "Catálogo de Serviços", href: "/servicos", icon: ClipboardList, perm: "servico" },
      { label: "Tipos de Anexo", href: "/tipos-anexo", icon: Paperclip, perm: "catalogo" },
      { label: "Templates de documento", href: "/templates-documento", icon: FileText, perm: "minuta_template" },
      { label: "Cidades", href: "/cidades", icon: MapPin, perm: "cidade" },
      { label: "Bairros", href: "/bairros", icon: Map, perm: "endereco" },
      { label: "Endereços", href: "/enderecos", icon: MapPin, perm: "endereco" },
    ],
  },
  {
    title: "Frota",
    defaultOpen: false,
    items: [
      { label: "Frota Pública", href: "/frotas", icon: Truck, perm: "frota" },
      { label: "Veículos", href: "/frotas/veiculos", icon: Car, perm: "frota" },
      { label: "Motoristas", href: "/frotas/motoristas", icon: IdCard, perm: "frota" },
      { label: "Solicitações", href: "/frotas/solicitacoes", icon: ClipboardList, perm: "frota" },
    ],
  },
  {
    title: "Transporte Regulado",
    defaultOpen: false,
    items: [
      { label: "Transporte Regulado", href: "/transporte-regulado", icon: Bus, perm: "transporte_regulado" },
      {
        label: "Permissionários",
        href: "/transporte-regulado/permissionarios",
        icon: IdCard,
        perm: "transporte_regulado",
      },
      {
        label: "Empresas",
        href: "/transporte-regulado/empresas",
        icon: Building2,
        perm: "transporte_regulado",
      },
      {
        label: "Veículos",
        href: "/transporte-regulado/veiculos",
        icon: Car,
        perm: "transporte_regulado",
      },
    ],
  },
  {
    title: "Pagamentos",
    defaultOpen: false,
    items: [
      { label: "Visão geral", href: "/pagamentos", icon: Inbox,
        anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
      { label: "Dashboard", href: "/pagamentos/dashboard", icon: BarChart3,
        anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar", "pagamento_cadastro"] },
      { label: "Contas a pagar", href: "/pagamentos/contas-a-pagar", icon: ClipboardList,
        anyOf: ["pagamento_solicitar", "pagamento_aprovar", "pagamento_autorizar", "pagamento_pagar"] },
      { label: "Autorizações", href: "/pagamentos/autorizacao", icon: ShieldCheck,
        anyOf: ["pagamento_autorizar"] },
      { label: "Tesouraria", href: "/pagamentos/tesouraria", icon: Banknote,
        perm: "pagamento_pagar" },
      { label: "Caixa", href: "/pagamentos/caixa", icon: Wallet, perm: "pagamento_cadastro" },
      {
        label: "Cadastros",
        href: "/pagamentos/cadastros/fornecedores",
        icon: FolderTree,
        perm: "pagamento_cadastro",
        children: [
          { label: "Fornecedores", href: "/pagamentos/cadastros/fornecedores", icon: UserCircle, perm: "pagamento_cadastro" },
          { label: "Naturezas", href: "/pagamentos/cadastros/naturezas", icon: Layers, perm: "pagamento_cadastro" },
          { label: "Fontes de recursos", href: "/pagamentos/cadastros/fontes", icon: BookOpen, perm: "pagamento_cadastro" },
          { label: "Contas bancárias", href: "/pagamentos/cadastros/contas", icon: Building2, perm: "pagamento_cadastro" },
          { label: "Contratos", href: "/pagamentos/cadastros/contratos", icon: FileText, perm: "pagamento_cadastro" },
          { label: "Alçadas", href: "/pagamentos/cadastros/alcadas", icon: Shield, perm: "pagamento_cadastro" },
          { label: "Checklist documental", href: "/pagamentos/cadastros/checklist", icon: ListChecks, perm: "pagamento_cadastro" },
        ],
      },
    ],
  },
  {
    title: "Administração",
    defaultOpen: false,
    items: [
      { label: "Usuários", href: "/usuarios", icon: Users, perm: "usuario" },
      { label: "Unidades", href: "/unidades-trabalho", icon: Building2, perm: "unidadeTrabalho" },
      { label: "Grupos & Permissões", href: "/grupos", icon: Shield },
      { label: "Configurações", href: "/configuracoes", icon: Settings, perm: "usuario" },
      { label: "Auditoria", href: "/auditoria", icon: Shield },
      { label: "Jobs em background", href: "/jobs", icon: Cog },
    ],
  },
];

function canSeeItem(item: NavItem, can: (perm: string) => boolean): boolean {
  return (
    (!item.perm && !item.anyOf) ||
    (!!item.perm && can(item.perm)) ||
    (!!item.anyOf && item.anyOf.some((p) => can(p)))
  );
}

function isPathActive(href: string, pathname: string): boolean {
  return pathname === href || pathname.startsWith(href + "/");
}

/** True se o item OU algum descendente corresponde ao pathname atual. */
function itemMatchesPath(item: NavItem, pathname: string): boolean {
  if (isPathActive(item.href, pathname)) return true;
  return item.children?.some((c) => itemMatchesPath(c, pathname)) ?? false;
}

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const COLLAPSED_KEY = "aprimora.sidebar.collapsed";
const GROUP_STATE_KEY = "aprimora.sidebar.groups.v1";

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { can } = useAuth();
  const branding = useBranding();
  // PR3a — link de plataforma só aparece para admin de plataforma (allowlist).
  const adminMeQ = useQuery({
    queryKey: ["admin-me"],
    queryFn: () => api.admin.me(),
    staleTime: 5 * 60_000,
    retry: false,
  });
  const isPlatformAdmin = adminMeQ.data?.is_platform_admin ?? false;
  const lastPath = useRef(pathname);
  // Collapsed (icon-only) — só faz sentido em desktop. Persistido em localStorage.
  const [collapsed, setCollapsed] = useState(false);
  // Grupos abertos/fechados — chave: title do grupo.
  const [groupOpen, setGroupOpen] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(NAV.map((g) => [g.title, g.defaultOpen ?? true])),
  );
  // Subgrupos (item com children) abertos/fechados — chave: label do item.
  // Não persistido (não exigido); abre sozinho se um filho estiver ativo.
  const [subOpen, setSubOpen] = useState<Record<string, boolean>>({});
  const toggleSub = (label: string) =>
    setSubOpen((prev) => ({ ...prev, [label]: !prev[label] }));

  useEffect(() => {
    try {
      const raw = localStorage.getItem(COLLAPSED_KEY);
      if (raw === "1") setCollapsed(true);
    } catch {
      /* ignore */
    }
    try {
      const raw = localStorage.getItem(GROUP_STATE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, boolean>;
        // Preserva defaults pra grupos novos que ainda não foram salvos
        setGroupOpen((prev) => ({ ...prev, ...parsed }));
      }
    } catch {
      /* ignore */
    }
  }, []);

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

  // Calcula quais grupos têm o item ativo (pra realçar o header).
  const activeGroupTitle = useMemo(() => {
    return NAV.find((g) => g.items.some((i) => itemMatchesPath(i, pathname)))?.title;
  }, [pathname]);

  return (
    <>
      <div
        onClick={onClose}
        aria-hidden="true"
        className={cn(
          "fixed inset-0 z-30 bg-black/50 transition-opacity duration-200 lg:hidden",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      <nav
        aria-label="Navegação principal"
        data-collapsed={collapsed}
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 shrink-0 flex-col overflow-hidden",
          "border-r border-sidebar-border bg-sidebar text-sidebar-foreground pt-safe transition-[transform,width] duration-base ease-out-expo",
          collapsed ? "lg:static lg:w-[68px]" : "lg:static lg:w-64 lg:translate-x-0",
          open ? "translate-x-0 shadow-xl" : "-translate-x-full shadow-none lg:translate-x-0",
        )}
      >
        {/* Brand block */}
        <div className="flex items-center justify-between gap-2 border-b border-sidebar-border px-3 py-4">
          <Link
            href="/home"
            className={cn(
              "flex items-center gap-2.5 rounded px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              collapsed && "lg:justify-center lg:gap-0",
            )}
            aria-label="Início"
            title={collapsed ? branding?.nome ?? "Aprimora" : undefined}
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
            <div className={cn(collapsed && "lg:hidden")}>
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
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-sidebar-muted transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground lg:hidden"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

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
            const showItems = collapsed || isOpen;
            const slugId = `nav-group-${group.title.toLowerCase().replace(/\s+/g, "-")}`;

            return (
              <div key={group.title} className="rounded-md">
                {/* Group header — clicável (exceto em collapsed mode, vira só separador). */}
                {collapsed ? (
                  <div
                    className="my-1 hidden h-px w-full bg-sidebar-border lg:block"
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

                    if (item.children && item.children.length > 0 && !collapsed) {
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

                    // Item simples (ou pai com children em modo collapsed — vira link p/ 1º filho).
                    const linkHref = collapsed && item.children?.length ? item.children[0].href : item.href;
                    const linkActive = collapsed && item.children?.length
                      ? item.children.some((c) => isPathActive(c.href, pathname))
                      : active;

                    return (
                      <Link
                        key={item.label}
                        href={linkHref}
                        aria-current={linkActive ? "page" : undefined}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                          collapsed && "lg:justify-center lg:gap-0 lg:px-0",
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
                        <span className={cn("flex-1", collapsed && "lg:hidden")}>
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
              title={collapsed ? "Plataforma" : undefined}
              aria-current={pathname.startsWith("/admin") ? "page" : undefined}
              className={cn(
                "group relative mt-1 flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                collapsed && "lg:justify-center lg:gap-0 lg:px-0",
                pathname.startsWith("/admin")
                  ? "bg-sidebar-active text-sidebar-foreground"
                  : "text-sidebar-foreground/90 hover:bg-sidebar-accent hover:text-sidebar-foreground",
              )}
            >
              <Shield className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span className={cn("flex-1", collapsed && "lg:hidden")}>Plataforma</span>
            </Link>
          )}
        </div>

        {/* Footer com toggles */}
        <div
          className={cn(
            "flex items-center gap-2 border-t border-sidebar-border bg-sidebar-accent/50 px-3 py-3",
            collapsed ? "lg:flex-col" : "justify-between",
          )}
        >
          <div className={cn(collapsed && "lg:hidden")}>
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

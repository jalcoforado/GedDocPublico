"use client";

import {
  BarChart3,
  BookOpen,
  Building2,
  ChevronsLeft,
  ChevronsRight,
  Cog,
  FileText,
  GitBranch,
  Home,
  Layers,
  Map,
  MapPin,
  Paperclip,
  PenSquare,
  Shield,
  Tag,
  User,
  UserCircle,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

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
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    title: "Geral",
    items: [
      { label: "Início", href: "/home", icon: Home },
      { label: "Dashboard", href: "/dashboard", icon: BarChart3 },
      { label: "Organograma", href: "/organograma", icon: Building2 },
      { label: "Processos", href: "/processos", icon: FileText, perm: "processo" },
      { label: "Para assinar", href: "/para-assinar", icon: PenSquare },
      { label: "Relatórios", href: "/relatorios", icon: BarChart3, perm: "processo" },
      { label: "Workflows", href: "/workflow", icon: GitBranch },
      { label: "Auditoria", href: "/auditoria", icon: Shield },
      { label: "Jobs em background", href: "/jobs", icon: Cog },
      { label: "Meu perfil", href: "/perfil", icon: User },
    ],
  },
  {
    title: "Acesso",
    items: [
      { label: "Usuários", href: "/usuarios", icon: Users, perm: "usuario" },
      { label: "Unidades", href: "/unidades-trabalho", icon: Building2, perm: "unidadeTrabalho" },
      { label: "Grupos & Permissões", href: "/grupos", icon: Shield },
    ],
  },
  {
    title: "Localização",
    items: [
      { label: "Cidades", href: "/cidades", icon: MapPin, perm: "cidade" },
      { label: "Bairros", href: "/bairros", icon: Map, perm: "endereco" },
      { label: "Endereços", href: "/enderecos", icon: MapPin, perm: "endereco" },
    ],
  },
  {
    title: "Catálogos",
    items: [
      { label: "Tipos de Processo", href: "/tipos-processo", icon: Layers, perm: "catalogo" },
      { label: "Assuntos", href: "/assuntos", icon: BookOpen, perm: "assunto" },
      { label: "Tipos de Anexo", href: "/tipos-anexo", icon: Paperclip, perm: "catalogo" },
    ],
  },
  {
    title: "Manifestantes",
    items: [
      { label: "Manifestantes", href: "/manifestantes", icon: UserCircle, perm: "manifestante" },
      { label: "Tipos", href: "/tipos-manifestante", icon: Tag, perm: "manifestante" },
    ],
  },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

const COLLAPSED_KEY = "aprimora.sidebar.collapsed";

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { can } = useAuth();
  const branding = useBranding();
  const lastPath = useRef(pathname);
  // Collapsed state — só faz sentido em desktop. Persistido em localStorage.
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(COLLAPSED_KEY);
      if (raw === "1") setCollapsed(true);
    } catch {
      /* ignore */
    }
  }, []);

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

  useEffect(() => {
    if (lastPath.current !== pathname) {
      lastPath.current = pathname;
      onClose();
    }
  }, [pathname, onClose]);

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
          // No desktop: largura depende de collapsed
          collapsed ? "lg:static lg:w-[68px]" : "lg:static lg:w-64 lg:translate-x-0",
          // Mobile sempre full sidebar (collapsed só vale desktop)
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
              <div className="text-[10px] uppercase tracking-wider text-foreground-subtle">
                Gestão de processos
              </div>
            </div>
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar menu"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-foreground-muted transition-colors hover:bg-muted hover:text-foreground lg:hidden"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        {/* Items */}
        <div className="flex flex-1 flex-col gap-3 overflow-y-auto px-3 py-3">
          {NAV.map((group) => {
            const visible = group.items.filter((item) => !item.perm || can(item.perm));
            if (visible.length === 0) return null;
            return (
              <div key={group.title}>
                <div
                  className={cn(
                    "mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle",
                    collapsed && "lg:hidden",
                  )}
                >
                  {group.title}
                </div>
                {/* Em collapsed mode, separator sutil entre grupos */}
                {collapsed && (
                  <div className="mb-1 hidden h-px w-full bg-sidebar-border lg:block" aria-hidden="true" />
                )}
                <div className="flex flex-col gap-0.5">
                  {visible.map((item) => {
                    const Icon = item.icon;
                    const active =
                      pathname === item.href || pathname.startsWith(item.href + "/");
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        aria-current={active ? "page" : undefined}
                        title={collapsed ? item.label : undefined}
                        className={cn(
                          "group relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-fast",
                          collapsed && "lg:justify-center lg:gap-0 lg:px-0",
                          active
                            ? "bg-brand/12 text-brand dark:bg-brand/25 dark:text-brand-light"
                            : "text-foreground-muted hover:bg-sidebar-accent hover:text-foreground",
                        )}
                      >
                        {/* Indicator bar à esquerda quando ativo */}
                        <span
                          aria-hidden="true"
                          className={cn(
                            "absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full transition-all duration-fast",
                            active ? "bg-accent" : "bg-transparent group-hover:bg-border-strong",
                          )}
                        />
                        <Icon
                          className={cn(
                            "h-4 w-4 shrink-0 transition-colors",
                            active ? "text-brand dark:text-brand-light" : "",
                          )}
                          aria-hidden="true"
                        />
                        <span className={cn("flex-1", collapsed && "lg:hidden")}>{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer com toggles (visível em todos os breakpoints) */}
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
            {/* Botão collapse — só desktop */}
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
              title={collapsed ? "Expandir sidebar" : "Recolher sidebar"}
              className="hidden h-9 w-9 items-center justify-center rounded-md border border-sidebar-border bg-sidebar text-foreground-muted transition-colors duration-fast hover:bg-sidebar-accent hover:text-foreground lg:inline-flex"
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

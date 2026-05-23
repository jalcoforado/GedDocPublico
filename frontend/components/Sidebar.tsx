"use client";

import {
  BarChart3,
  BookOpen,
  Building2,
  Cog,
  FileText,
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
import { useEffect, useRef } from "react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

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
      { label: "Processos", href: "/processos", icon: FileText, perm: "processo" },
      { label: "Para assinar", href: "/para-assinar", icon: PenSquare },
      { label: "Relatórios", href: "/relatorios", icon: BarChart3, perm: "processo" },
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

export function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { can } = useAuth();
  const lastPath = useRef(pathname);

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
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex w-72 shrink-0 flex-col gap-4 overflow-y-auto border-r border-border bg-card p-4 pt-safe transition-transform duration-200",
          "lg:static lg:w-64 lg:translate-x-0",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-start justify-between gap-2 px-2">
          <Link href="/home" className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
            <div className="text-xl font-bold text-primary">Aprimora</div>
            <div className="text-xs text-muted-foreground">
              Gestão de processos
            </div>
          </Link>
          <button
            type="button"
            onClick={onClose}
            aria-label="Fechar menu"
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
        {NAV.map((group) => {
          const visible = group.items.filter((item) => !item.perm || can(item.perm));
          if (visible.length === 0) return null;
          return (
            <div key={group.title}>
              <div className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {group.title}
              </div>
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
                      className={cn(
                        "flex items-center gap-3 rounded px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "text-foreground hover:bg-muted",
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span className="flex-1">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>
    </>
  );
}

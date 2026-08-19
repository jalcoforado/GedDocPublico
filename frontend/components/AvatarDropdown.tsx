"use client";

import {
  ChevronDown,
  Layers,
  LogOut,
  Maximize2,
  Minimize2,
  Monitor,
  Moon,
  Settings,
  Shield,
  Sparkles,
  Sun,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useTheme, type Density, type ThemePreference } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";

function initials(nome: string | null | undefined): string {
  if (!nome) return "?";
  const parts = nome.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const THEME_OPTS: Array<{ value: ThemePreference; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { value: "system", label: "Sistema", icon: Monitor },
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Escuro", icon: Moon },
];

const DENSITY_OPTS: Array<{ value: Density; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { value: "comfortable", label: "Confortável", icon: Maximize2 },
  { value: "compact", label: "Compacto", icon: Minimize2 },
];

export function AvatarDropdown() {
  const { user, perms, logout } = useAuth();
  const branding = useBranding();
  const { preference, setPreference, density, setDensity, theme } = useTheme();

  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClick(e: MouseEvent) {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;

  const ThemeIcon =
    THEME_OPTS.find((o) => o.value === preference)?.icon ??
    (theme === "dark" ? Moon : Sun);

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "group inline-flex h-10 items-center gap-1.5 rounded-full pl-1 pr-2 transition-colors duration-fast",
          "hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
        aria-label={`Conta de ${user.nome}`}
      >
        <span
          className="
            inline-flex h-8 w-8 items-center justify-center rounded-full
            bg-brand-gradient text-xs font-bold text-white shadow-brand
          "
        >
          {initials(user.nome)}
        </span>
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-foreground-muted transition-transform duration-fast",
            open && "rotate-180",
          )}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          role="menu"
          className="
            absolute right-0 top-[calc(100%+6px)] z-dropdown w-72
            overflow-hidden rounded-lg border border-border bg-card shadow-xl
            animate-scale-in origin-top-right
          "
        >
          {/* Header da conta */}
          <div className="border-b border-border bg-surface-2/40 px-4 py-3">
            <div className="flex items-center gap-3">
              <span
                className="
                  inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full
                  bg-brand-gradient text-sm font-bold text-white shadow-brand
                "
              >
                {initials(user.nome)}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-foreground">
                  {user.nome}
                </div>
                <div className="truncate text-xs text-foreground-muted">
                  {user.email}
                </div>
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {perms?.is_super_usuario && (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-dark">
                  <Sparkles className="h-2.5 w-2.5" aria-hidden="true" />
                  Super usuário
                </span>
              )}
              {branding?.nome && (
                <span className="inline-flex items-center gap-1 rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand">
                  <Layers className="h-2.5 w-2.5" aria-hidden="true" />
                  {branding.nome}
                </span>
              )}
            </div>
          </div>

          {/* Tema */}
          <div className="border-b border-border px-3 py-2">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-foreground-subtle">
              <ThemeIcon className="h-3 w-3" aria-hidden="true" />
              Tema
            </div>
            <div className="flex rounded-md border border-border bg-surface-1 p-0.5">
              {THEME_OPTS.map((opt) => {
                const Icon = opt.icon;
                const active = preference === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    onClick={() => setPreference(opt.value)}
                    className={cn(
                      "inline-flex h-8 flex-1 items-center justify-center gap-1 rounded text-xs font-medium transition-colors duration-fast",
                      active
                        ? "bg-brand text-primary-foreground shadow-sm"
                        : "text-foreground-muted hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3 w-3" aria-hidden="true" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Densidade */}
          <div className="border-b border-border px-3 py-2">
            <div className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-foreground-subtle">
              Densidade
            </div>
            <div className="flex rounded-md border border-border bg-surface-1 p-0.5">
              {DENSITY_OPTS.map((opt) => {
                const Icon = opt.icon;
                const active = density === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="menuitemradio"
                    aria-checked={active}
                    onClick={() => setDensity(opt.value)}
                    className={cn(
                      "inline-flex h-8 flex-1 items-center justify-center gap-1 rounded text-xs font-medium transition-colors duration-fast",
                      active
                        ? "bg-brand text-primary-foreground shadow-sm"
                        : "text-foreground-muted hover:bg-muted hover:text-foreground",
                    )}
                  >
                    <Icon className="h-3 w-3" aria-hidden="true" />
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Links */}
          <div className="py-1">
            <MenuLink
              href="/perfil"
              icon={UserIcon}
              label="Meu perfil"
              onClick={() => setOpen(false)}
            />
            <MenuLink
              href="/perfil"
              icon={Settings}
              label="Preferências de notificação"
              onClick={() => setOpen(false)}
            />
            {perms?.is_super_usuario && (
              <MenuLink
                href="/auditoria"
                icon={Shield}
                label="Auditoria"
                onClick={() => setOpen(false)}
              />
            )}
          </div>

          {/* Logout */}
          <div className="border-t border-border py-1">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="
                flex w-full items-center gap-2 px-3 py-2 text-sm
                text-danger transition-colors duration-fast
                hover:bg-danger-soft hover:text-danger-soft-foreground
              "
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              Sair
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function MenuLink({
  href,
  icon: Icon,
  label,
  onClick,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  onClick?: () => void;
}) {
  return (
    <Link
      href={href}
      role="menuitem"
      onClick={onClick}
      className="
        flex items-center gap-2 px-3 py-2 text-sm text-foreground
        transition-colors duration-fast hover:bg-muted
      "
    >
      <Icon className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
      {label}
    </Link>
  );
}

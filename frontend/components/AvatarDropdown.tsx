"use client";

import {
  ChevronDown,
  Layers,
  LogOut,
  Settings,
  Shield,
  Sparkles,
  User as UserIcon,
} from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { PreferenciasAparencia } from "@/components/PreferenciasAparencia";
import { Popover } from "@/components/ui/popover";
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

export function AvatarDropdown() {
  const { user, perms, logout } = useAuth();
  const branding = useBranding();

  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Clique-fora/ESC são do Popover (fatia 3.4); fechar devolve o foco ao
  // avatar em vez de deixá-lo cair no body.
  const fechar = () => {
    setOpen(false);
    triggerRef.current?.focus();
  };

  if (!user) return null;

  return (
    <div className="relative">
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
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

      {/* Painel de conta com seções e radiogroups — não é um menu ARIA de
          verdade (role=menu exigiria menuitems homogêneos e roubaria o role
          dos links); div simples anuncia cada controle pelo próprio papel. */}
      <Popover open={open} anchorRef={triggerRef} onClose={fechar} placement="bottom-end" className="w-72">
        <div>
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

          {/* Tema + densidade — radiogroups compartilhados com /perfil (fatia 3.7) */}
          <div className="border-b border-border px-3 py-2">
            <PreferenciasAparencia />
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
              href="/perfil/notificacoes"
              icon={Settings}
              label="Preferências de notificação"
              onClick={() => setOpen(false)}
            />
            {perms?.is_super_usuario && (
              <MenuLink
                href="/m/administracao/auditoria"
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
      </Popover>
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

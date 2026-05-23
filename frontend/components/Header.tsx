"use client";

import { LogOut, Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";

interface HeaderProps {
  onOpenSidebar: () => void;
}

export function Header({ onOpenSidebar }: HeaderProps) {
  const { user, logout, perms } = useAuth();

  return (
    <header className="flex items-center justify-between gap-2 border-b border-border bg-card px-4 py-3 pt-safe sm:px-6">
      <button
        type="button"
        onClick={onOpenSidebar}
        aria-label="Abrir menu"
        className="inline-flex h-11 w-11 items-center justify-center rounded-md text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring lg:hidden"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>
      <div className="flex flex-1 items-center justify-end gap-4">
        {user && (
          <div className="hidden text-right sm:block">
            <div className="text-sm font-medium text-foreground">{user.nome}</div>
            <div className="flex items-center justify-end gap-2 text-xs text-muted-foreground">
              <span className="max-w-[260px] truncate">{user.email}</span>
              {perms?.is_super_usuario && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-semibold uppercase text-primary">
                  Super
                </span>
              )}
            </div>
          </div>
        )}
        <Button variant="secondary" size="sm" onClick={logout} className="gap-2">
          <LogOut className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">Sair</span>
          <span className="sr-only sm:hidden">Sair</span>
        </Button>
      </div>
    </header>
  );
}

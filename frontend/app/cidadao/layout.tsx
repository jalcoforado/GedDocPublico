"use client";

import { FileText, LogOut, PenSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { CidadaoAuthProvider, useCidadao } from "@/lib/cidadao-auth";
import { Providers } from "@/lib/providers";
import { cn } from "@/lib/utils";

const PUBLIC_PATHS = ["/cidadao/login", "/cidadao/cadastrar"];

function CidadaoHeader() {
  const pathname = usePathname();
  const { cidadao, logout, loading } = useCidadao();
  const isPublic = PUBLIC_PATHS.includes(pathname);

  return (
    <header className="border-b border-border bg-card pt-safe">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3 sm:px-6">
        <Link
          href={cidadao ? "/cidadao/processos" : "/cidadao/login"}
          className="flex items-baseline gap-2 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <span className="text-xl font-bold text-primary">Aprimora</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">
            Portal do Cidadão
          </span>
        </Link>
        <nav className="flex items-center gap-3 text-sm" aria-label="Menu">
          {cidadao ? (
            <>
              <Link
                href="/cidadao/processos"
                aria-current={pathname === "/cidadao/processos" ? "page" : undefined}
                className={cn(
                  "hidden text-foreground transition-colors hover:text-primary sm:inline",
                  pathname === "/cidadao/processos" && "font-semibold text-primary",
                )}
              >
                Meus processos
              </Link>
              <Link
                href="/cidadao/abrir"
                aria-current={pathname === "/cidadao/abrir" ? "page" : undefined}
                className={cn(
                  "hidden text-foreground transition-colors hover:text-primary sm:inline",
                  pathname === "/cidadao/abrir" && "font-semibold text-primary",
                )}
              >
                Abrir processo
              </Link>
              <span className="hidden max-w-[220px] truncate text-xs text-muted-foreground md:inline">
                {cidadao.nome ?? cidadao.cpf_cnpj}
              </span>
              <button
                type="button"
                onClick={logout}
                className="hidden h-9 items-center gap-1.5 rounded-md border border-danger px-3 text-xs font-medium text-danger transition-colors hover:bg-danger-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-danger sm:inline-flex"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Sair
              </button>
            </>
          ) : !loading && isPublic ? (
            <>
              <Link
                href="/cidadao/login"
                aria-current={pathname === "/cidadao/login" ? "page" : undefined}
                className={cn(
                  "text-foreground transition-colors hover:text-primary",
                  pathname === "/cidadao/login" && "font-semibold text-primary",
                )}
              >
                Entrar
              </Link>
              <Link
                href="/cidadao/cadastrar"
                aria-current={pathname === "/cidadao/cadastrar" ? "page" : undefined}
                className={cn(
                  "text-foreground transition-colors hover:text-primary",
                  pathname === "/cidadao/cadastrar" && "font-semibold text-primary",
                )}
              >
                Cadastrar-se
              </Link>
            </>
          ) : null}
        </nav>
      </div>
    </header>
  );
}

function BottomNav() {
  const pathname = usePathname();
  const { cidadao, logout } = useCidadao();
  if (!cidadao) return null;

  const items = [
    {
      href: "/cidadao/processos",
      label: "Processos",
      icon: FileText,
      active:
        pathname === "/cidadao/processos" || pathname.startsWith("/cidadao/processos/"),
    },
    {
      href: "/cidadao/abrir",
      label: "Abrir",
      icon: PenSquare,
      active: pathname === "/cidadao/abrir",
    },
  ];

  return (
    <nav
      aria-label="Navegação inferior"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-card pb-safe sm:hidden"
    >
      <div className="flex items-stretch justify-around">
        {items.map((it) => {
          const Icon = it.icon;
          return (
            <Link
              key={it.href}
              href={it.href}
              aria-current={it.active ? "page" : undefined}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors",
                it.active ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span>{it.label}</span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={logout}
          aria-label="Sair"
          className="flex flex-1 flex-col items-center justify-center gap-1 py-2 text-xs font-medium text-danger transition-colors"
        >
          <LogOut className="h-5 w-5" aria-hidden="true" />
          <span>Sair</span>
        </button>
      </div>
    </nav>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh bg-background pb-16 sm:pb-0">
      <CidadaoHeader />
      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">{children}</main>
      <BottomNav />
    </div>
  );
}

export default function CidadaoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Providers>
      <CidadaoAuthProvider requireAuth={false}>
        <Shell>{children}</Shell>
      </CidadaoAuthProvider>
    </Providers>
  );
}

"use client";

import { AlertOctagon, FileText, ListChecks, LogOut, PenSquare } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { AssinaturaAprimora } from "@/components/AssinaturaAprimora";
import { MarcaDoMunicipio } from "@/components/MarcaDoMunicipio";
import { CidadaoAuthProvider, useCidadao } from "@/lib/cidadao-auth";
import { Providers } from "@/lib/providers";
import { cn } from "@/lib/utils";

// Telas que quem ainda não entrou usa: nelas o topo oferece Entrar/Cadastrar.
// A Carta de Serviços é pública — quem chegou nela pelo atalho do login
// precisa do caminho de volta para entrar.
const PUBLIC_PATHS = ["/cidadao/login", "/cidadao/cadastrar"];
const ehPublica = (p: string) => PUBLIC_PATHS.includes(p) || p.startsWith("/cidadao/servicos");

/** As áreas de quem já entrou — a mesma lista no topo (computador) e na barra de baixo (celular). */
const AREAS = [
  {
    href: "/cidadao/processos",
    rotulo: "Meus processos",
    curto: "Processos",
    icon: FileText,
    ativa: (p: string) => p === "/cidadao/processos" || p.startsWith("/cidadao/processos/"),
  },
  {
    href: "/cidadao/abrir",
    rotulo: "Abrir processo",
    curto: "Abrir",
    icon: PenSquare,
    ativa: (p: string) => p === "/cidadao/abrir",
  },
  {
    href: "/cidadao/servicos",
    rotulo: "Serviços",
    curto: "Serviços",
    icon: ListChecks,
    ativa: (p: string) => p.startsWith("/cidadao/servicos"),
  },
  {
    href: "/cidadao/denuncias",
    rotulo: "Minhas denúncias",
    curto: "Denúncias",
    icon: AlertOctagon,
    ativa: (p: string) => p.startsWith("/cidadao/denuncias"),
  },
] as const;

const LINK_TOPO =
  "rounded-md px-2 py-1.5 text-foreground transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

function CidadaoHeader() {
  const pathname = usePathname();
  const { cidadao, logout, loading } = useCidadao();

  return (
    <header className="border-b border-border bg-card pt-safe">
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-2 px-4 py-3 sm:px-6">
        <Link
          href={cidadao ? "/cidadao/processos" : "/cidadao/login"}
          className="flex items-center gap-3 rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <MarcaDoMunicipio />
          <span className="hidden text-xs text-foreground-muted sm:inline">Portal do Cidadão</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm" aria-label="Menu">
          {cidadao ? (
            <>
              {AREAS.map((a) => (
                <Link
                  key={a.href}
                  href={a.href}
                  aria-current={a.ativa(pathname) ? "page" : undefined}
                  className={cn(
                    LINK_TOPO,
                    "hidden sm:inline",
                    a.ativa(pathname) && "font-semibold text-primary",
                  )}
                >
                  {a.rotulo}
                </Link>
              ))}
              <span className="ml-2 hidden max-w-[200px] truncate text-xs text-foreground-muted lg:inline">
                {cidadao.nome ?? cidadao.cpf_cnpj}
              </span>
              {/* Sair não é ação destrutiva: botão neutro, não vermelho. */}
              <button
                type="button"
                onClick={logout}
                className="ml-1 hidden h-9 items-center gap-1.5 rounded-md border border-border-strong px-3 text-xs font-medium text-foreground transition-colors duration-fast hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:inline-flex"
              >
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Sair
              </button>
            </>
          ) : !loading && ehPublica(pathname) ? (
            <>
              <Link
                href="/cidadao/login"
                aria-current={pathname === "/cidadao/login" ? "page" : undefined}
                className={cn(LINK_TOPO, pathname === "/cidadao/login" && "font-semibold text-primary")}
              >
                Entrar
              </Link>
              <Link
                href="/cidadao/cadastrar"
                aria-current={pathname === "/cidadao/cadastrar" ? "page" : undefined}
                className={cn(LINK_TOPO, pathname === "/cidadao/cadastrar" && "font-semibold text-primary")}
              >
                Criar conta
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

  const item =
    "flex min-h-14 flex-1 flex-col items-center justify-center gap-1 py-2 text-xs font-medium transition-colors duration-fast";

  return (
    <nav
      aria-label="Navegação inferior"
      className="fixed inset-x-0 bottom-0 z-fixed border-t border-border bg-card pb-safe sm:hidden"
    >
      <div className="flex items-stretch justify-around">
        {AREAS.map((a) => {
          const Icon = a.icon;
          const ativa = a.ativa(pathname);
          return (
            <Link
              key={a.href}
              href={a.href}
              aria-current={ativa ? "page" : undefined}
              className={cn(item, ativa ? "text-primary" : "text-foreground-muted hover:text-foreground")}
            >
              <Icon className="h-5 w-5" aria-hidden="true" />
              <span>{a.curto}</span>
            </Link>
          );
        })}
        <button
          type="button"
          onClick={logout}
          className={cn(item, "text-foreground-muted hover:text-foreground")}
        >
          <LogOut className="h-5 w-5" aria-hidden="true" />
          <span>Sair</span>
        </button>
      </div>
    </nav>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  const { cidadao } = useCidadao();
  // Altura da barra de baixo do celular (só existe com sessão). As barras
  // fixas das telas (botão "Solicitar", ações do formulário) sobem por ela
  // com `bottom-[var(--barra-inferior)]` — sem isso ficavam escondidas atrás.
  const barra = cidadao ? "calc(3.5rem + 1px + max(env(safe-area-inset-bottom), 0.5rem))" : "0px";
  return (
    <div
      style={{ "--barra-inferior": barra } as React.CSSProperties}
      className="min-h-dvh bg-background pb-[var(--barra-inferior)] sm:pb-0"
    >
      <CidadaoHeader />
      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">{children}</main>
      <AssinaturaAprimora className="px-4 pb-6 pt-2" />
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

"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  Bell,
  CalendarDays,
  FileSignature,
  Home as HomeIcon,
  Inbox,
  Layers,
  Loader2,
  Package,
  PenSquare,
  RefreshCw,
  Search,
  TrendingUp,
  UserRound,
} from "lucide-react";
import Link from "next/link";

import {
  api,
  assinaturasApi,
  notificacoesApi,
  temporalidadeApi,
  workflowApi,
  type PendenciaAssinatura,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

function fmtDataCurta(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

export default function HomePage() {
  const { user, perms } = useAuth();

  const idUnidadeUser = user?.id_unidade_trabalho;
  const primeiroNome = (user?.nome ?? "").split(/\s+/)[0] || "—";

  // ---- Action counters --------------------------------------------------
  const assinaturasQ = useQuery({
    queryKey: ["home-assinaturas-pendentes"],
    queryFn: () => assinaturasApi.minhasPendentes(),
    staleTime: 60_000,
  });

  const alertasQ = useQuery({
    queryKey: ["home-alertas-sla"],
    queryFn: () => workflowApi.listAlertas({ apenas_pendentes: true }),
    staleTime: 60_000,
  });

  const vencendoQ = useQuery({
    queryKey: ["home-vencendo-prazo"],
    queryFn: () => temporalidadeApi.vencendoPrazo({ dias: 365 }),
    staleTime: 60_000,
  });

  const notifQ = useQuery({
    queryKey: ["home-notif-unread"],
    queryFn: () =>
      notificacoesApi.listarMinhas({ apenas_nao_lidas: true, limit: 1 }),
    staleTime: 30_000,
  });

  const processosUnidadeQ = useQuery({
    queryKey: ["home-processos-unidade", idUnidadeUser],
    queryFn: () =>
      api.processos.list({
        id_unidade: idUnidadeUser!,
        apenas_ativos: true,
        page_size: 6,
      }),
    enabled: !!idUnidadeUser,
    staleTime: 60_000,
  });

  const naoLidas = notifQ.data?.nao_lidas ?? 0;
  const assinaturasPendentes = assinaturasQ.data?.length ?? 0;
  const alertasPendentes = alertasQ.data?.length ?? 0;
  const vencendoPrazo = vencendoQ.data?.length ?? 0;

  const totalPendencias = assinaturasPendentes + alertasPendentes + vencendoPrazo + naoLidas;
  const algumaPendencia = totalPendencias > 0;

  // Com qualquer contador falho, "sem pendências" seria uma afirmação falsa:
  // o número pode existir e não ter carregado.
  const algumaFalha =
    assinaturasQ.isError || alertasQ.isError || vencendoQ.isError || notifQ.isError;

  return (
    <div className="space-y-7">
      {/* === Menu principal — layout de referência: protótipo Figma
          "Sistema - Aprimora" === */}
      <div>
        <p className="flex items-center gap-2.5 font-display text-sm font-semibold text-titulo-destaque">
          <HomeIcon className="h-5 w-5 text-foreground-subtle" aria-hidden="true" />
          Menu principal
        </p>
        <h1 className="mt-5 border-b border-border-strong pb-2 text-xl font-normal text-titulo-destaque">
          Olá, {primeiroNome}
          {perms?.is_super_usuario ? (
            <span className="ml-3 align-middle font-sans text-[10px] font-semibold uppercase tracking-wider text-foreground-subtle">
              super usuário
            </span>
          ) : null}
        </h1>
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="space-y-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <BotaoDoMenu href="/perfil" icon={UserRound} rotulo="Meu perfil" />
            <BotaoDoMenu href="/modulos" icon={Layers} rotulo="Meus módulos" />
            <BotaoDoMenu
              href="#pendencias"
              icon={Package}
              rotulo="Minhas pendências"
              contador={algumaPendencia ? totalPendencias : undefined}
            />
          </div>
          <DocumentosAguardandoAssinatura
            pendencias={assinaturasQ.data ?? []}
            loading={assinaturasQ.isLoading}
            error={assinaturasQ.isError}
            onRetry={() => assinaturasQ.refetch()}
          />
        </div>
        <MeusCompromissos />
      </div>

      {/* Ações pendentes */}
      <section id="pendencias" className="scroll-mt-4">
        <header className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
            O que precisa de você
          </h2>
          <span
            className={cn(
              "text-[10px] uppercase tracking-[0.15em]",
              algumaFalha ? "text-warning" : "text-foreground-subtle",
            )}
          >
            {algumaFalha ? "alguns dados não carregaram" : "atualizado agora"}
          </span>
        </header>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <ActionCard
            href="/para-assinar"
            label="Para assinar"
            count={assinaturasPendentes}
            hint={
              assinaturasPendentes === 1
                ? "1 documento aguardando sua assinatura digital"
                : "documentos aguardando sua assinatura digital"
            }
            icon={FileSignature}
            intent="primary"
            loading={assinaturasQ.isLoading}
            error={assinaturasQ.isError}
            onRetry={() => assinaturasQ.refetch()}
          />
          <ActionCard
            href="/m/protocolo/workflow"
            label="Alertas SLA"
            count={alertasPendentes}
            hint={
              alertasPendentes === 1
                ? "1 processo ultrapassou prazo de etapa"
                : "processos ultrapassaram prazo de etapa"
            }
            icon={AlertTriangle}
            intent="warning"
            loading={alertasQ.isLoading}
            error={alertasQ.isError}
            onRetry={() => alertasQ.refetch()}
          />
          <ActionCard
            href="/m/protocolo/protocolo/vencendo-prazo"
            label="Vencendo guarda"
            count={vencendoPrazo}
            hint={
              vencendoPrazo === 1
                ? "1 processo próximo do fim do prazo TTD (12m)"
                : "processos próximos do fim do prazo TTD (12m)"
            }
            icon={Archive}
            intent="success"
            loading={vencendoQ.isLoading}
            error={vencendoQ.isError}
            onRetry={() => vencendoQ.refetch()}
          />
          <ActionCard
            href="/perfil"
            label="Não lidas"
            count={naoLidas}
            hint={
              naoLidas === 1
                ? "1 notificação nova no seu inbox"
                : "notificações novas no seu inbox"
            }
            icon={Bell}
            intent="info"
            loading={notifQ.isLoading}
            error={notifQ.isError}
            onRetry={() => notifQ.refetch()}
          />
        </div>
      </section>

      {/* 2 colunas: Atividade da unidade + Atalhos rápidos */}
      <div className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <UnidadeSection
          idUnidade={idUnidadeUser}
          processos={processosUnidadeQ.data?.items ?? []}
          total={processosUnidadeQ.data?.total ?? 0}
          loading={processosUnidadeQ.isLoading}
          error={processosUnidadeQ.isError}
          onRetry={() => processosUnidadeQ.refetch()}
        />
        <AtalhosSection />
      </div>
    </div>
  );
}

// ============================================================================
// Menu principal — blocos do layout de referência (Figma "Sistema - Aprimora")
// ============================================================================

/** Botão largo em gradiente da marca, com o ícone num disco mais escuro. */
function BotaoDoMenu({
  href,
  icon: Icon,
  rotulo,
  contador,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  rotulo: string;
  /** Quantidade a destacar (pendências); omitido = sem selo. */
  contador?: number;
}) {
  return (
    <Link
      href={href}
      className="group flex h-14 items-center gap-3 rounded-2xl bg-gradient-to-r from-brand-dark to-brand-light px-3 text-primary-foreground shadow-brand transition-all duration-fast hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background motion-reduce:hover:translate-y-0"
    >
      <span
        className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-black/20"
        aria-hidden="true"
      >
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1 truncate font-display text-md font-medium">{rotulo}</span>
      {contador !== undefined ? (
        <span className="rounded-full bg-card px-2 py-0.5 text-xs font-semibold tabular-nums text-brand">
          {contador}
          <span className="sr-only"> pendências</span>
        </span>
      ) : null}
    </Link>
  );
}

function DocumentosAguardandoAssinatura({
  pendencias,
  loading,
  error,
  onRetry,
}: {
  pendencias: PendenciaAssinatura[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
}) {
  const visiveis = pendencias.slice(0, 5);
  return (
    <section className="rounded-2xl bg-muted p-5">
      <header className="flex items-baseline justify-between gap-3 border-b border-border-strong pb-3">
        <h2 className="text-md font-medium text-foreground">Documentos aguardando assinatura</h2>
        {pendencias.length > 0 ? (
          <Link
            href="/para-assinar"
            className="shrink-0 text-xs font-medium text-brand underline-offset-2 hover:underline"
          >
            Ver {pendencias.length === 1 ? "o documento" : `os ${pendencias.length}`}
          </Link>
        ) : null}
      </header>

      {loading ? (
        <p className="flex items-center gap-2 py-6 text-sm text-foreground-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Carregando…
        </p>
      ) : error ? (
        <div className="flex items-center gap-3 py-6 text-sm text-foreground-muted">
          Não foi possível carregar os documentos.
          <button
            type="button"
            onClick={onRetry}
            className="font-medium text-brand underline-offset-2 hover:underline"
          >
            Tentar de novo
          </button>
        </div>
      ) : visiveis.length === 0 ? (
        <p className="py-6 text-sm text-foreground-muted">
          Nenhum documento aguardando a sua assinatura.
        </p>
      ) : (
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className="font-display text-foreground">
              <th scope="col" className="px-3 py-2 font-medium">Documento</th>
              <th scope="col" className="px-3 py-2 font-medium">Solicitante</th>
              <th scope="col" className="px-3 py-2 font-medium">Data do envio</th>
              <th scope="col" className="px-3 py-2 font-medium">Nº do processo</th>
            </tr>
          </thead>
          <tbody>
            {visiveis.map((p) => (
              <tr key={p.id_assinatura_anexo} className="text-foreground-muted even:[&>td]:bg-card">
                <td className="rounded-l-full px-3 py-1.5">
                  <Link href="/para-assinar" className="underline-offset-2 hover:underline">
                    {p.anexo_descricao ?? `Anexo ${p.id_anexo}`}
                  </Link>
                </td>
                <td className="px-3 py-1.5">{p.nome_solicitante}</td>
                <td className="px-3 py-1.5 tabular-nums">
                  {new Date(p.dt_inicio).toLocaleDateString("pt-BR")}
                </td>
                <td className="rounded-r-full px-3 py-1.5 tabular-nums">
                  {p.numero_processo ?? "rascunho"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

/**
 * "Meus compromissos" do layout de referência. O sistema ainda não tem agenda:
 * o painel ocupa o lugar previsto e diz a verdade — não há compromisso porque
 * não há de onde vir. Quando a agenda existir, é aqui que ela entra.
 */
function MeusCompromissos() {
  return (
    <aside className="flex flex-col rounded-2xl bg-muted p-4" aria-labelledby="compromissos-titulo">
      <div className="flex items-center gap-3">
        <span
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-dark text-primary-foreground"
          aria-hidden="true"
        >
          <CalendarDays className="h-5 w-5" />
        </span>
        <h2 id="compromissos-titulo" className="text-md font-medium text-foreground">
          Meus compromissos
        </h2>
      </div>
      <div className="mt-4 flex min-h-[11rem] flex-1 items-center justify-center rounded-xl border border-border-strong px-4 text-center">
        <p className="font-display text-md text-brand-dark">Sem compromissos pendentes</p>
      </div>
    </aside>
  );
}

// ============================================================================
// ActionCard — KPI clicável com count, hint e intent
// ============================================================================

type Intent = "primary" | "warning" | "success" | "info";

const INTENT_STYLES: Record<Intent, { ring: string; iconBg: string; accent: string; countActive: string }> = {
  primary: {
    ring: "hover:border-brand/40 hover:shadow-brand/10",
    iconBg: "bg-brand/10 text-brand",
    accent: "bg-brand",
    countActive: "text-brand",
  },
  warning: {
    ring: "hover:border-warning/40 hover:shadow-warning/10",
    iconBg: "bg-warning/10 text-warning",
    accent: "bg-warning",
    countActive: "text-warning",
  },
  success: {
    ring: "hover:border-success/40 hover:shadow-success/10",
    iconBg: "bg-success/10 text-success",
    accent: "bg-success",
    countActive: "text-success",
  },
  info: {
    ring: "hover:border-info/40 hover:shadow-info/10",
    iconBg: "bg-info/10 text-info",
    accent: "bg-info",
    countActive: "text-info",
  },
};

function ActionCard({
  href,
  label,
  count,
  hint,
  icon: Icon,
  intent,
  loading,
  error,
  onRetry,
}: {
  href: string;
  label: string;
  count: number;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  intent: Intent;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  const style = INTENT_STYLES[intent];
  const zerado = count === 0;

  // Falhou: sem número confiável, o card vira aviso com retry — não Link,
  // para não aninhar botão dentro de âncora.
  if (error) {
    return (
      <div className="relative flex flex-col gap-3 overflow-hidden rounded-xl border border-danger/40 bg-card p-4 shadow-xs">
        <span
          aria-hidden="true"
          className="absolute left-0 top-0 h-full w-1 bg-danger opacity-100"
        />
        <div className="flex items-start justify-between gap-2">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-danger/10 text-danger">
            <Icon className="h-4 w-4" aria-hidden="true" />
          </span>
        </div>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-foreground-subtle">
            {label}
          </p>
          <p className="mt-0.5 font-display text-4xl font-semibold leading-none text-foreground-subtle">
            —
          </p>
        </div>
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-danger">Não foi possível carregar.</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs font-medium text-foreground hover:bg-muted"
            >
              <RefreshCw className="h-3 w-3" aria-hidden="true" />
              Tentar novamente
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <Link
      href={href}
      className={cn(
        "group relative flex flex-col gap-3 overflow-hidden rounded-xl border border-border bg-card p-4 shadow-xs",
        "transition-all duration-base ease-out-expo",
        "hover:-translate-y-0.5 hover:shadow-md",
        style.ring,
      )}
    >
      {/* Barra de accent à esquerda (mais opaca quando há count) */}
      <span
        aria-hidden="true"
        className={cn(
          "absolute left-0 top-0 h-full w-1 transition-opacity",
          style.accent,
          zerado ? "opacity-20" : "opacity-100",
        )}
      />

      <div className="flex items-start justify-between gap-2">
        <span
          className={cn(
            "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg transition-colors",
            zerado ? "bg-surface-3 text-foreground-muted" : style.iconBg,
          )}
        >
          <Icon className="h-4 w-4" aria-hidden="true" />
        </span>
        <ArrowRight
          className="h-4 w-4 text-foreground-muted opacity-0 transition-all duration-fast group-hover:translate-x-0.5 group-hover:opacity-100"
          aria-hidden="true"
        />
      </div>

      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-foreground-subtle">
          {label}
        </p>
        <p
          className={cn(
            "mt-0.5 font-display text-4xl font-semibold leading-none tabular-nums",
            loading
              ? "animate-pulse text-foreground-subtle/50"
              : zerado
                ? "text-foreground-subtle"
                : style.countActive,
          )}
        >
          {loading ? "—" : count}
        </p>
      </div>

      <p className="text-xs text-foreground-muted">
        {loading ? "carregando…" : count === 0 ? "tudo em dia" : hint}
      </p>
    </Link>
  );
}

// ============================================================================
// UnidadeSection — Processos da sua unidade
// ============================================================================

interface ProcessoMin {
  id: number;
  /** E3 — null enquanto o processo é rascunho (lista já exclui por padrão) */
  numero_processo: string | null;
  nup?: string | null;
  data_hora_abertura: string;
  manifestante: string | null;
  assunto: string | null;
  local_atual: string | null;
}

function UnidadeSection({
  idUnidade,
  processos,
  total,
  loading,
  error,
  onRetry,
}: {
  idUnidade: number | null | undefined;
  processos: ProcessoMin[];
  total: number;
  loading: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex items-start gap-3">
          <span
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand/8 text-brand"
            aria-hidden="true"
          >
            <Inbox className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold tracking-tight">
              Sua unidade
            </h2>
            <p className="mt-0.5 text-xs text-foreground-muted">
              Processos ativos passando pela unidade {idUnidade ? `#${idUnidade}` : "(sem unidade)"}.
            </p>
          </div>
        </div>
        {idUnidade && (
          <Link
            href={`/m/protocolo/processos?id_unidade=${idUnidade}`}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
          >
            ver todos {total > 0 && <span className="font-mono">({total})</span>}
            <ArrowRight className="h-3 w-3" aria-hidden="true" />
          </Link>
        )}
      </header>

      <div className="p-2">
        {!idUnidade && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            Você não está lotado em uma unidade. Atualize seu perfil.
          </p>
        )}
        {idUnidade && loading && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            <Loader2 className="mr-1 inline h-4 w-4 animate-spin" /> Carregando…
          </p>
        )}
        {idUnidade && !loading && error && (
          <div className="flex flex-col items-center gap-3 px-3 py-6 text-center">
            <p className="text-sm text-danger">
              Não foi possível carregar os processos da sua unidade.
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
              >
                <RefreshCw className="h-3 w-3" aria-hidden="true" />
                Tentar novamente
              </button>
            )}
          </div>
        )}
        {idUnidade && !loading && !error && processos.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            Nenhum processo ativo passando agora.
          </p>
        )}
        {!error && processos.length > 0 && (
          <ul className="divide-y divide-border">
            {processos.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/m/protocolo/processos/${p.id}`}
                  className="group flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-surface-2"
                >
                  <span className="text-[10px] font-mono text-foreground-subtle tabular-nums">
                    {fmtDataCurta(p.data_hora_abertura)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-primary group-hover:underline">
                        {p.nup ?? p.numero_processo ?? "Rascunho"}
                      </span>
                      {p.nup && (
                        <span className="font-mono text-[10px] text-foreground-subtle">
                          ({p.numero_processo})
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 truncate text-xs text-foreground-muted">
                      {p.manifestante ?? "—"}{" "}
                      <span className="text-foreground-subtle">·</span>{" "}
                      {p.assunto ?? "—"}
                    </div>
                  </div>
                  <ArrowRight
                    className="h-3.5 w-3.5 shrink-0 text-foreground-subtle opacity-0 transition-all group-hover:translate-x-0.5 group-hover:opacity-100"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

// ============================================================================
// AtalhosSection — Tiles de ação rápida
// ============================================================================

const ATALHOS = [
  {
    href: "/m/protocolo/protocolo/balcao",
    label: "Protocolar",
    sub: "Receber documento físico",
    icon: Inbox,
  },
  {
    href: "/m/protocolo/processos/novo",
    label: "Novo processo",
    sub: "Abrir processo interno",
    icon: PenSquare,
  },
  {
    href: "/m/protocolo/processos",
    label: "Buscar processo",
    sub: "Listagem completa",
    icon: Search,
  },
  {
    href: "/dashboard",
    label: "Dashboard",
    sub: "Visão executiva",
    icon: TrendingUp,
  },
];

function AtalhosSection() {
  return (
    <section className="rounded-xl border border-border bg-card shadow-xs">
      <header className="border-b border-border px-5 py-4">
        <h2 className="text-sm font-semibold tracking-tight">Atalhos</h2>
        <p className="mt-0.5 text-xs text-foreground-muted">
          As ações que você mais usa, a um clique.
        </p>
      </header>
      <div className="grid grid-cols-2 gap-2 p-3">
        {ATALHOS.map((a) => {
          const Icon = a.icon;
          return (
            <Link
              key={a.href}
              href={a.href}
              className="
                group relative flex flex-col gap-2 overflow-hidden rounded-lg
                border border-border bg-surface-1 p-3 transition-all duration-base
                hover:-translate-y-0.5 hover:border-brand/30 hover:bg-brand/5 hover:shadow-sm
              "
            >
              <span
                className="
                  inline-flex h-8 w-8 items-center justify-center rounded-md
                  bg-surface-3 text-foreground-muted transition-colors
                  group-hover:bg-brand/15 group-hover:text-brand
                "
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
              <div>
                <p className="text-sm font-medium text-foreground">{a.label}</p>
                <p className="text-[11px] text-foreground-muted">{a.sub}</p>
              </div>
            </Link>
          );
        })}
      </div>
    </section>
  );
}

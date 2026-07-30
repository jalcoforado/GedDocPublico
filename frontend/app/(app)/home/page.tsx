"use client";

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  Archive,
  ArrowRight,
  Bell,
  Building2,
  FileSignature,
  Inbox,
  Loader2,
  PenSquare,
  Search,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import {
  api,
  assinaturasApi,
  notificacoesApi,
  temporalidadeApi,
  workflowApi,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useBranding } from "@/lib/branding";
import { cn } from "@/lib/utils";

const DIAS_SEMANA = [
  "domingo",
  "segunda-feira",
  "terça-feira",
  "quarta-feira",
  "quinta-feira",
  "sexta-feira",
  "sábado",
];
const MESES = [
  "janeiro",
  "fevereiro",
  "março",
  "abril",
  "maio",
  "junho",
  "julho",
  "agosto",
  "setembro",
  "outubro",
  "novembro",
  "dezembro",
];

function dataExtensa(d: Date): string {
  return `${DIAS_SEMANA[d.getDay()]}, ${d.getDate()} de ${MESES[d.getMonth()]}`;
}

function saudacaoPorHora(d: Date): string {
  const h = d.getHours();
  if (h < 6) return "Boa madrugada";
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function fmtDataCurta(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" });
}

export default function HomePage() {
  const { user, perms } = useAuth();
  const branding = useBranding();

  const idUnidadeUser = user?.id_unidade_trabalho;
  const agora = useMemo(() => new Date(), []);

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

  const algumaPendencia =
    assinaturasPendentes > 0 ||
    alertasPendentes > 0 ||
    vencendoPrazo > 0 ||
    naoLidas > 0;

  return (
    <div className="space-y-7">
      <GreetingSection
        userName={user?.nome ?? "—"}
        isSuperUser={perms?.is_super_usuario ?? false}
        tenantName={branding?.nome ?? null}
        agora={agora}
        algumaPendencia={algumaPendencia}
      />

      {/* Ações pendentes */}
      <section>
        <header className="mb-3 flex items-baseline justify-between">
          <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
            O que precisa de você
          </h2>
          <span className="text-[10px] uppercase tracking-[0.15em] text-foreground-subtle">
            atualizado agora
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
          />
          <ActionCard
            href="/workflow"
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
          />
          <ActionCard
            href="/protocolo/vencendo-prazo"
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
        />
        <AtalhosSection />
      </div>
    </div>
  );
}

// ============================================================================
// GreetingSection — Cabeçalho hero com saudação + meta
// ============================================================================

function GreetingSection({
  userName,
  isSuperUser,
  tenantName,
  agora,
  algumaPendencia,
}: {
  userName: string;
  isSuperUser: boolean;
  tenantName: string | null;
  agora: Date;
  algumaPendencia: boolean;
}) {
  const primeiroNome = userName.split(/\s+/)[0] || userName;
  const saudacao = saudacaoPorHora(agora);
  const dataStr = dataExtensa(agora);

  return (
    <section
      className={cn(
        "relative overflow-hidden rounded-2xl border border-border",
        "bg-gradient-to-br from-brand/10 via-card to-surface-1",
        "px-6 py-7 shadow-xs",
      )}
    >
      {/* Mesh decoration sutil */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-32 -top-32 h-72 w-72 rounded-full bg-brand/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-20 -left-10 h-44 w-44 rounded-full bg-accent/10 blur-2xl"
      />

      <div className="relative flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-[0.18em] text-foreground-muted">
            {dataStr}
          </p>
          <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            {saudacao},{" "}
            <span className="bg-gradient-to-r from-brand to-accent bg-clip-text text-transparent">
              {primeiroNome}
            </span>
            <span className="text-foreground-muted">.</span>
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-foreground-muted">
            {algumaPendencia
              ? "Algumas coisas precisam de você hoje. Comece por onde fizer sentido."
              : "Sem pendências críticas no momento. Bom trabalho."}
          </p>
        </div>

        <div className="flex flex-col items-end gap-1.5">
          {isSuperUser && (
            <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-accent-dark">
              <Sparkles className="h-3 w-3" aria-hidden="true" />
              Super usuário
            </span>
          )}
          {tenantName && (
            <span className="inline-flex items-center gap-1 rounded-full bg-brand/10 px-2.5 py-1 text-[10px] font-medium text-brand">
              <Building2 className="h-3 w-3" aria-hidden="true" />
              {tenantName}
            </span>
          )}
        </div>
      </div>
    </section>
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
}: {
  href: string;
  label: string;
  count: number;
  hint: string;
  icon: React.ComponentType<{ className?: string }>;
  intent: Intent;
  loading?: boolean;
}) {
  const style = INTENT_STYLES[intent];
  const zerado = count === 0;

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
        {count === 0 ? "tudo em dia" : hint}
      </p>
    </Link>
  );
}

// ============================================================================
// UnidadeSection — Processos da sua unidade
// ============================================================================

interface ProcessoMin {
  id: number;
  numero_processo: string;
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
}: {
  idUnidade: number | null | undefined;
  processos: ProcessoMin[];
  total: number;
  loading: boolean;
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
            href={`/processos?id_unidade=${idUnidade}`}
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
        {idUnidade && !loading && processos.length === 0 && (
          <p className="px-3 py-6 text-center text-sm text-foreground-muted">
            Nenhum processo ativo passando agora.
          </p>
        )}
        {processos.length > 0 && (
          <ul className="divide-y divide-border">
            {processos.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/processos/${p.id}`}
                  className="group flex items-center gap-3 rounded-md px-3 py-2 transition-colors hover:bg-surface-2"
                >
                  <span className="text-[10px] font-mono text-foreground-subtle tabular-nums">
                    {fmtDataCurta(p.data_hora_abertura)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold text-primary group-hover:underline">
                        {p.nup ?? p.numero_processo}
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
    href: "/protocolo/balcao",
    label: "Protocolar",
    sub: "Receber documento físico",
    icon: Inbox,
  },
  {
    href: "/processos/novo",
    label: "Novo processo",
    sub: "Abrir processo interno",
    icon: PenSquare,
  },
  {
    href: "/processos",
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

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  Eye,
  FileDown,
  FileText,
  Hourglass,
  Inbox,
  Lock,
  Printer,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { cn } from "@/lib/utils";

type TabId = "visao" | "movimentacoes" | "documentos" | "relacionados";
const VALID_TABS: TabId[] = ["visao", "movimentacoes", "documentos", "relacionados"];

function isTabId(v: string | null): v is TabId {
  return v !== null && (VALID_TABS as string[]).includes(v);
}

import { AcoesProcesso } from "@/components/AcoesProcesso";
import { AnexosProcesso } from "@/components/AnexosProcesso";
import { MinutasProcesso } from "@/components/MinutasProcesso";
import { CancelarComplementacaoDialog } from "@/components/CancelarComplementacaoDialog";
import { ChecklistDocumentosCard } from "@/components/ChecklistDocumentosCard";
import { ClassificarSigiloDialog } from "@/components/ClassificarSigiloDialog";
import { ComplementacaoAbertaCard } from "@/components/ComplementacaoAbertaCard";
import { ComplementacoesHistoricoLista } from "@/components/ComplementacoesHistoricoLista";
import { SolicitarComplementacaoDialog } from "@/components/SolicitarComplementacaoDialog";
import { ProcessoApensados } from "@/components/ProcessoApensados";
import { ProcessoVolumes } from "@/components/ProcessoVolumes";
import { AssinaturasProcesso } from "@/components/AssinaturasProcesso";
import { ProcessoTrail } from "@/components/ProcessoTrail";
import { ProcessoWorkflowPanel } from "@/components/ProcessoWorkflowPanel";
import { PdfViewerDialog } from "@/components/PdfViewerDialog";
import { ActionsMenu } from "@/components/ui/actions-menu";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { RichTextView } from "@/components/ui/rich-text-editor";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  api,
  comprovanteUrl,
  etiquetaDuplaUrl,
  etiquetaUnicaUrl,
  processoCapaUrl,
  processoCompletoUrl,
  NIVEL_SIGILO_LABEL,
  type MovimentacaoItem,
} from "@/lib/api";
import { prazoBadge, statusProcessoBadge } from "@/lib/badges";
import { useAuth } from "@/lib/auth";

function fmtDateTime(s: string | null | undefined) {
  if (!s) return "—";
  const d = new Date(s);
  return (
    d.toLocaleDateString("pt-BR") +
    " " +
    d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })
  );
}

function fmtDate(s: string | null | undefined) {
  if (!s) return "—";
  return new Date(s).toLocaleDateString("pt-BR");
}

const ACAO_INTENT: Record<string, "info" | "warning" | "success" | "neutral" | "danger"> = {
  ABERTURA: "info",
  ENCAMINHAMENTO: "warning",
  RECEBIMENTO: "success",
  ARQUIVAMENTO: "neutral",
  CANCELAMENTO: "danger",
};

// PR 5b + UX-1 Fase D — render do badge de prazo via helper de lib/badges.
// Mantém exatamente as labels antigas (incl. contagem "N d." no servidor).
function PrazoBadge({ prazo }: { prazo: import("@/lib/api").PrazoInfo }) {
  const spec = prazoBadge(prazo, "servidor");
  if (!spec) return null;
  const Icon = spec.icon;
  return (
    <Badge intent={spec.intent} icon={Icon}>
      {spec.label}
    </Badge>
  );
}

interface ViewerState {
  title: string;
  src: string;
  downloadUrl: string;
}

function MovimentacaoCard({
  m,
  onOpenViewer,
}: {
  m: MovimentacaoItem;
  onOpenViewer: (v: ViewerState) => void;
}) {
  const intent = ACAO_INTENT[m.acao_flag] ?? "neutral";
  return (
    <div className="border-l-2 border-primary pl-4">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <Badge intent={intent}>{m.acao}</Badge>
        <span className="text-xs text-muted-foreground tabular-nums">
          {fmtDateTime(m.data_hora_movimentacao)}
        </span>
      </div>
      <div className="text-sm">
        <span className="text-muted-foreground">por</span>{" "}
        <b className="text-foreground">{m.usuario ?? "—"}</b>
        {m.unidade_responsavel && (
          <>
            {" · "}
            <span className="text-muted-foreground">unidade</span>{" "}
            <b className="text-foreground">{m.unidade_responsavel}</b>
          </>
        )}
      </div>
      {m.despacho && (
        <div className="mt-2 rounded-md bg-muted p-3 text-sm">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Despacho
          </div>
          <p className="whitespace-pre-wrap text-foreground">{m.despacho.despacho}</p>
        </div>
      )}
      {m.encaminhamento && (
        <div className="mt-2 rounded-md border border-warning/30 bg-warning-soft p-3 text-sm">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-warning-soft-foreground">
              Encaminhamento
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  onOpenViewer({
                    title: `Comprovante de envio — enc #${m.encaminhamento!.id}`,
                    src: comprovanteUrl(m.encaminhamento!.id, "envio"),
                    downloadUrl: comprovanteUrl(m.encaminhamento!.id, "envio", false),
                  })
                }
              >
                <FileDown className="h-4 w-4" aria-hidden="true" /> Comprovante envio
              </Button>
              {m.encaminhamento.recebido && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    onOpenViewer({
                      title: `Comprovante de recebimento — enc #${m.encaminhamento!.id}`,
                      src: comprovanteUrl(m.encaminhamento!.id, "recebimento"),
                      downloadUrl: comprovanteUrl(
                        m.encaminhamento!.id,
                        "recebimento",
                        false,
                      ),
                    })
                  }
                >
                  <FileDown className="h-4 w-4" aria-hidden="true" /> Comprovante recebimento
                </Button>
              )}
            </div>
          </div>
          <div className="grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-2">
            <div>
              <span className="text-muted-foreground">De:</span>{" "}
              {m.encaminhamento.unidade_origem ?? "—"}
            </div>
            <div>
              <span className="text-muted-foreground">Para:</span>{" "}
              {m.encaminhamento.unidade_destino}
            </div>
            <div>
              <span className="text-muted-foreground">Prioridade:</span>{" "}
              {m.encaminhamento.prioridade ?? "—"}
            </div>
            <div>
              <span className="text-muted-foreground">Folhas:</span>{" "}
              <span className="tabular-nums">{m.encaminhamento.quantidade_folhas}</span>
            </div>
            <div>
              <span className="text-muted-foreground">Prazo:</span>{" "}
              {fmtDate(m.encaminhamento.data_prazo)}
            </div>
            <div>
              <span className="text-muted-foreground">Recebido:</span>{" "}
              {m.encaminhamento.recebido ? "Sim" : "Não"}
              {m.encaminhamento.cancelado ? " (cancelado)" : ""}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ProcessoDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  const { can } = useAuth();
  const processoId = Number(params.id);
  const [viewer, setViewer] = useState<ViewerState | null>(null);

  const tabParam = searchParams.get("tab");
  const activeTab: TabId = isTabId(tabParam) ? tabParam : "visao";

  function setTab(t: TabId) {
    const url = new URL(window.location.href);
    if (t === "visao") {
      url.searchParams.delete("tab");
    } else {
      url.searchParams.set("tab", t);
    }
    router.replace(url.pathname + url.search, { scroll: false });
  }

  const q = useQuery({
    queryKey: ["processo", processoId],
    queryFn: () => api.processos.get(processoId),
    enabled: !!processoId,
  });
  // PR 4c — checklist documental read-only do processo (visível na aba Documentos).
  const checklistQ = useQuery({
    queryKey: ["processo-checklist", processoId],
    queryFn: () => api.processos.checklistDocumentos(processoId),
    enabled: !!processoId,
  });
  // PR 4d — Complementação documental (histórico + ações servidor).
  const qc = useQueryClient();
  const complementacoesQ = useQuery({
    queryKey: ["processo-complementacoes", processoId],
    queryFn: () => api.processos.listarComplementacoes(processoId),
    enabled: !!processoId,
  });
  const [solicitarOpen, setSolicitarOpen] = useState(false);
  const [cancelarOpen, setCancelarOpen] = useState(false);
  const solicitarM = useMutation({
    mutationFn: (body: { mensagem: string; documentos_solicitados: string[] }) =>
      api.processos.solicitarComplementacao(processoId, body),
    onSuccess: () => {
      toast.success("Complementação solicitada.");
      setSolicitarOpen(false);
      qc.invalidateQueries({ queryKey: ["processo-complementacoes", processoId] });
      qc.invalidateQueries({ queryKey: ["processo-checklist", processoId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const cancelarM = useMutation({
    mutationFn: ({
      id,
      motivo,
    }: {
      id: number;
      motivo: string | null;
    }) => api.processos.cancelarComplementacao(processoId, id, { motivo }),
    onSuccess: () => {
      toast.success("Complementação cancelada.");
      setCancelarOpen(false);
      qc.invalidateQueries({ queryKey: ["processo-complementacoes", processoId] });
      qc.invalidateQueries({ queryKey: ["processo-checklist", processoId] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const gerarBg = useMutation({
    mutationFn: () => api.jobs.processoCompleto(processoId),
    onSuccess: () => {
      toast.success("Geração em background enfileirada.");
      router.push("/jobs");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (q.isLoading) {
    return (
      <div className="space-y-6">
        <SkeletonLine width="40%" className="h-7" />
        <SkeletonLine width="25%" className="h-3" />
        <Skeleton className="h-11 w-full rounded-md" />
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-32 rounded-xl" />
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="space-y-4">
        <Link
          href="/m/protocolo/processos"
          className="
            inline-flex items-center gap-1 text-sm text-primary hover:underline
            focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded
          "
        >
          ← Voltar para lista
        </Link>
        <EmptyState
          icon={Inbox}
          title="Não foi possível carregar este processo"
          description={
            q.error instanceof Error
              ? q.error.message
              : "Tente novamente em instantes ou volte para a lista."
          }
          action={
            <Button asChild size="sm">
              <Link href="/m/protocolo/processos">Voltar para lista</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const p = q.data;
  const podeAtualizarProcesso = can("processo", "atualizar");

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileText}
        breadcrumbs={[
          { label: "Processos", href: "/m/protocolo/processos" },
          { label: p.numero_processo },
        ]}
        title={
          <span className="font-mono">
            {p.nup ?? p.numero_processo}
          </span>
        }
        description={
          <span className="text-foreground-muted">
            {p.nup && (
              <>
                <span className="font-mono">Legado: {p.numero_processo}</span>
                {" · "}
              </>
            )}
            Aberto em {fmtDateTime(p.data_hora_abertura)}
            {p.manifestante && ` · ${p.manifestante}`}
          </span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            {/* Bloco de badges (status macro + sigilo + externo + prazo).
                D-LINGUAGEM-ENCERRADO: helper retorna "Em tramitacao" /
                "Encerrado" no modo servidor — alinha com contexto cidadao
                e evita ambiguidade do antigo "Inativo". */}
            <div className="flex flex-wrap gap-1">
              {(() => {
                const s = statusProcessoBadge(p, "servidor");
                const StatusIcon = s.icon;
                return (
                  <Badge intent={s.intent} icon={StatusIcon}>
                    {s.label}
                  </Badge>
                );
              })()}
              {!p.publico && (
                <Badge intent="warning" icon={Lock}>
                  {NIVEL_SIGILO_LABEL[p.nivel_sigilo]}
                </Badge>
              )}
              {p.externo && (
                <Badge intent="info" icon={Eye}>
                  Externo
                </Badge>
              )}
              {/* PR 5b — badge de prazo (null em sem_prazo). */}
              <PrazoBadge prazo={p.prazo} />
            </div>
            {/* Acoes — D-PRINT-MENU: impressoes/relatorios agrupadas
                num ActionsMenu "Imprimir". URLs/handlers e permissoes
                preservados byte-a-byte. PDF completo segue visivel como
                primario; ClassificarSigilo segue como dialog separado. */}
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                size="sm"
                onClick={() =>
                  setViewer({
                    title: `Processo completo — ${p.numero_processo}`,
                    src: processoCompletoUrl(p.id),
                    downloadUrl: processoCompletoUrl(p.id, false),
                  })
                }
                title="PDF do processo completo"
              >
                <FileText className="h-4 w-4" aria-hidden="true" />
                PDF completo
              </Button>
              <ActionsMenu
                label="Imprimir"
                icon={Printer}
                items={[
                  {
                    label: "Capa",
                    icon: FileText,
                    onClick: () =>
                      setViewer({
                        title: `Capa — ${p.numero_processo}`,
                        src: processoCapaUrl(p.id),
                        downloadUrl: processoCapaUrl(p.id, false),
                      }),
                  },
                  {
                    label: "Etiqueta",
                    icon: Tags,
                    onClick: () =>
                      setViewer({
                        title: `Etiqueta — ${p.numero_processo}`,
                        src: etiquetaUnicaUrl(p.id),
                        downloadUrl: etiquetaUnicaUrl(p.id, false),
                      }),
                  },
                  {
                    label: "Etiqueta dupla",
                    icon: Tags,
                    onClick: () =>
                      setViewer({
                        title: `Etiquetas (dupla) — ${p.numero_processo}`,
                        src: etiquetaDuplaUrl(p.id),
                        downloadUrl: etiquetaDuplaUrl(p.id, false),
                      }),
                  },
                  {
                    label: gerarBg.isPending
                      ? "Enfileirando…"
                      : "Gerar PDF em background",
                    icon: Hourglass,
                    onClick: () => gerarBg.mutate(),
                    disabled: gerarBg.isPending,
                  },
                ]}
              />
              <ClassificarSigiloDialog
                processo={p}
                onClassified={() => q.refetch()}
              />
            </div>
          </div>
        }
      />

      <div
        role="tablist"
        aria-label="Seções do processo"
        className="flex gap-1 overflow-x-auto border-b border-border"
      >
        {(
          [
            { id: "visao", label: "Visão geral" },
            {
              id: "movimentacoes",
              label: "Movimentações",
              count: p.movimentacoes.length,
            },
            { id: "documentos", label: "Documentos", count: p.anexos.length },
            { id: "relacionados", label: "Relacionados" },
          ] as const
        ).map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex h-11 shrink-0 items-center gap-2 px-4 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "border-b-2 border-primary text-primary"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
              {"count" in t && t.count != null && (
                <span
                  className={cn(
                    "rounded-full px-1.5 text-xs tabular-nums",
                    active
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {t.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {activeTab === "visao" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Visão geral</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Assunto
                  </dt>
                  <dd>{p.assunto ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Tipo de processo
                  </dt>
                  <dd>{p.tipo_processo ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Manifestante
                  </dt>
                  <dd>
                    {p.manifestante ?? "—"}{" "}
                    <span className="text-xs text-muted-foreground">
                      {p.manifestante_cpf_cnpj ?? ""}
                    </span>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Unidade proprietária
                  </dt>
                  <dd>{p.unidade_proprietaria ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Local atual
                  </dt>
                  <dd>{p.local_atual ?? "—"}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Número origem
                  </dt>
                  <dd>{p.numero_origem ?? "—"}</dd>
                </div>
                {p.observacao && (
                  <div className="md:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      Observação
                    </dt>
                    <dd className="whitespace-pre-wrap">{p.observacao}</dd>
                  </div>
                )}
                {p.corpo && (
                  <div className="md:col-span-2">
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      Corpo
                    </dt>
                    <dd>
                      {/^\s*<[a-zA-Z]/.test(p.corpo) ? (
                        <RichTextView html={p.corpo} />
                      ) : (
                        <p className="whitespace-pre-wrap text-sm">{p.corpo}</p>
                      )}
                    </dd>
                  </div>
                )}
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Trajeto entre unidades</CardTitle>
            </CardHeader>
            <CardContent>
              <ProcessoTrail processoId={p.id} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Ações de tramitação</CardTitle>
            </CardHeader>
            <CardContent>
              <AcoesProcesso processo={p} />
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "movimentacoes" && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>
                Movimentações{" "}
                <span className="text-foreground-muted">
                  ({p.movimentacoes.length})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {p.movimentacoes.length === 0 ? (
                <EmptyState
                  icon={Clock}
                  title="Sem movimentações registradas"
                  description="Use 'Ações de tramitação' na aba Visão geral para registrar a primeira movimentação."
                />
              ) : (
                <div className="space-y-5">
                  {p.movimentacoes.map((m) => (
                    <MovimentacaoCard key={m.id} m={m} onOpenViewer={setViewer} />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Workflow</CardTitle>
            </CardHeader>
            <CardContent>
              <ProcessoWorkflowPanel processoId={p.id} />
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "documentos" && (
        <div className="space-y-6">
          {/* PR 4d — Bloco de complementação documental.
              PR 4d-fix: enquanto o histórico ainda carrega, NÃO oferece
              "Solicitar complementação" (backend é fonte de verdade,
              mas evita clique confuso quando já existe uma aberta e a UI
              ainda não tem o dado). Mostra placeholder no lugar. */}
          {(() => {
            const todas = complementacoesQ.data ?? [];
            const aberta = todas.find((c) => c.status === "aberta") ?? null;
            const anteriores = todas.filter((c) => c.status !== "aberta");
            const blocoComplementacao = complementacoesQ.isLoading ? (
              <div
                data-testid="complementacao-loading"
                className="h-16 animate-pulse rounded-lg bg-surface-2/40"
              />
            ) : aberta ? (
              <ComplementacaoAbertaCard
                data={aberta}
                modo="servidor"
                onCancelar={
                  podeAtualizarProcesso ? () => setCancelarOpen(true) : undefined
                }
              />
            ) : podeAtualizarProcesso ? (
              <div className="flex justify-end">
                <Button
                  variant="secondary"
                  onClick={() => setSolicitarOpen(true)}
                  disabled={!checklistQ.data}
                >
                  Solicitar complementação
                </Button>
              </div>
            ) : null;
            return (
              <>
                {blocoComplementacao}
                <ChecklistDocumentosCard
                  data={checklistQ.data}
                  loading={checklistQ.isLoading}
                  modo="servidor"
                />
                <ComplementacoesHistoricoLista data={anteriores} />
                <SolicitarComplementacaoDialog
                  open={solicitarOpen}
                  onClose={() => setSolicitarOpen(false)}
                  checklist={checklistQ.data}
                  onSubmit={(body) => solicitarM.mutate(body)}
                  submitting={solicitarM.isPending}
                />
                <CancelarComplementacaoDialog
                  open={cancelarOpen}
                  onClose={() => setCancelarOpen(false)}
                  onSubmit={(body) =>
                    aberta && cancelarM.mutate({ id: aberta.id, motivo: body.motivo })
                  }
                  submitting={cancelarM.isPending}
                />
              </>
            );
          })()}

          <Card>
            <CardHeader>
              <CardTitle>Anexos</CardTitle>
            </CardHeader>
            <CardContent>
              <AnexosProcesso processo={p} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Documentos redigidos</CardTitle>
            </CardHeader>
            <CardContent>
              <MinutasProcesso processo={p} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Assinaturas</CardTitle>
            </CardHeader>
            <CardContent>
              <AssinaturasProcesso processo={p} />
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "relacionados" && (
        <div className="space-y-6">
          <ProcessoApensados
            processoId={p.id}
            numeroProcesso={p.numero_processo}
            idProcessoPai={p.id_processo_pai}
          />
          <ProcessoVolumes processoId={p.id} />
        </div>
      )}

      {viewer && (
        <PdfViewerDialog
          open={!!viewer}
          onClose={() => setViewer(null)}
          title={viewer.title}
          src={viewer.src}
          downloadUrl={viewer.downloadUrl}
        />
      )}
    </div>
  );
}

"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CheckCircle2,
  Eye,
  FileDown,
  FileText,
  Lock,
  Pause,
  Tags,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { AcoesProcesso } from "@/components/AcoesProcesso";
import { AnexosProcesso } from "@/components/AnexosProcesso";
import { ProcessoApensados } from "@/components/ProcessoApensados";
import { ProcessoVolumes } from "@/components/ProcessoVolumes";
import { AssinaturasProcesso } from "@/components/AssinaturasProcesso";
import { ProcessoTrail } from "@/components/ProcessoTrail";
import { ProcessoWorkflowPanel } from "@/components/ProcessoWorkflowPanel";
import { PdfViewerDialog } from "@/components/PdfViewerDialog";
import { PageHeader } from "@/components/ui/page-header";
import { RichTextView } from "@/components/ui/rich-text-editor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import {
  api,
  comprovanteUrl,
  etiquetaDuplaUrl,
  etiquetaUnicaUrl,
  processoCapaUrl,
  processoCompletoUrl,
  type MovimentacaoItem,
} from "@/lib/api";

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
  const toast = useToast();
  const processoId = Number(params.id);
  const [viewer, setViewer] = useState<ViewerState | null>(null);

  const q = useQuery({
    queryKey: ["processo", processoId],
    queryFn: () => api.processos.get(processoId),
    enabled: !!processoId,
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
    return <div className="text-muted-foreground">Carregando processo...</div>;
  }
  if (q.error || !q.data) {
    return (
      <div className="space-y-4">
        <Link href="/processos" className="text-sm text-primary hover:underline">
          ← Voltar para lista
        </Link>
        <div
          role="alert"
          className="rounded-md bg-danger-soft px-4 py-3 text-sm text-danger-soft-foreground"
        >
          {q.error instanceof Error ? q.error.message : "Erro ao carregar processo"}
        </div>
      </div>
    );
  }

  const p = q.data;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={FileText}
        breadcrumbs={[
          { label: "Processos", href: "/processos" },
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
            <div className="flex flex-wrap gap-1">
              {p.ativo ? (
                <Badge intent="success" icon={CheckCircle2}>
                  Ativo
                </Badge>
              ) : (
                <Badge intent="neutral" icon={Pause}>
                  Inativo
                </Badge>
              )}
              {!p.publico && (
                <Badge intent="warning" icon={Lock}>
                  Sigiloso
                </Badge>
              )}
              {p.externo && (
                <Badge intent="info" icon={Eye}>
                  Externo
                </Badge>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setViewer({
                    title: `Capa — ${p.numero_processo}`,
                    src: processoCapaUrl(p.id),
                    downloadUrl: processoCapaUrl(p.id, false),
                  })
                }
                title="Ver capa"
              >
                <FileText className="h-4 w-4" aria-hidden="true" />
                Capa
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setViewer({
                    title: `Etiqueta — ${p.numero_processo}`,
                    src: etiquetaUnicaUrl(p.id),
                    downloadUrl: etiquetaUnicaUrl(p.id, false),
                  })
                }
                title="Ver etiqueta"
              >
                <Tags className="h-4 w-4" aria-hidden="true" />
                Etiqueta
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() =>
                  setViewer({
                    title: `Etiquetas (dupla) — ${p.numero_processo}`,
                    src: etiquetaDuplaUrl(p.id),
                    downloadUrl: etiquetaDuplaUrl(p.id, false),
                  })
                }
                title="Etiqueta dupla"
              >
                <Tags className="h-4 w-4" aria-hidden="true" />
                Dupla
              </Button>
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
                Completo
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => gerarBg.mutate()}
                disabled={gerarBg.isPending}
                title="Gera o PDF em background e abre a fila de jobs"
              >
                {gerarBg.isPending ? "Enfileirando..." : "Em fila"}
              </Button>
            </div>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <CardTitle className="font-mono">{p.numero_processo}</CardTitle>
            <span className="text-sm text-muted-foreground tabular-nums">
              aberto em {fmtDateTime(p.data_hora_abertura)}
            </span>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-1 gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted-foreground">Assunto</dt>
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
                <dt className="text-xs uppercase tracking-wide text-muted-foreground">Corpo</dt>
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
          <CardTitle>Ações de tramitação</CardTitle>
        </CardHeader>
        <CardContent>
          <AcoesProcesso processo={p} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Movimentações ({p.movimentacoes.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {p.movimentacoes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nenhuma movimentação registrada.
            </p>
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
          <CardTitle>Anexos</CardTitle>
        </CardHeader>
        <CardContent>
          <AnexosProcesso processo={p} />
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
          <CardTitle>Workflow</CardTitle>
        </CardHeader>
        <CardContent>
          <ProcessoWorkflowPanel processoId={p.id} />
        </CardContent>
      </Card>

      <ProcessoApensados
        processoId={p.id}
        numeroProcesso={p.numero_processo}
        idProcessoPai={p.id_processo_pai}
      />

      <ProcessoVolumes processoId={p.id} />

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

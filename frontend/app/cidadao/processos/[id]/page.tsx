"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  CalendarClock,
  Clock,
  FileText,
  History,
  Info,
  Paperclip,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ChecklistDocumentosCard } from "@/components/ChecklistDocumentosCard";
import { fmtDia, fmtDiaHora, problemaDoArquivo } from "@/components/cidadao/formato";
import { ProtocoloRecebido } from "@/components/cidadao/ProtocoloRecebido";
import { SeletorArquivo } from "@/components/cidadao/SeletorArquivo";
import { ComplementacaoAbertaCard } from "@/components/ComplementacaoAbertaCard";
import { ComplementacoesHistoricoLista } from "@/components/ComplementacoesHistoricoLista";
import { ProximosPassosCard } from "@/components/ProximosPassosCard";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { SectionCard } from "@/components/ui/section-card";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { prazoBadge, statusProcessoBadge } from "@/lib/badges";
import { useRequireCidadao } from "@/lib/cidadao-auth";

function DetailSkeleton() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-28 rounded-xl" />
      <Skeleton className="h-20 rounded-xl" />
      <Skeleton className="h-48 rounded-xl" />
      <Skeleton className="h-32 rounded-xl" />
    </div>
  );
}

function Dado({ rotulo, children, largo }: { rotulo: string; children: React.ReactNode; largo?: boolean }) {
  return (
    <div className={largo ? "md:col-span-2" : undefined}>
      <dt className="text-xs font-medium text-foreground-muted">{rotulo}</dt>
      <dd className="mt-0.5 whitespace-pre-wrap break-words text-sm text-foreground">{children}</dd>
    </div>
  );
}

export default function CidadaoProcessoDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const idValido = Number.isInteger(id) && id > 0;
  const { cidadao, loading } = useRequireCidadao();

  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["cidadao-processo", id],
    queryFn: () => api.cidadao.getProcesso(id),
    enabled: !!cidadao && idValido,
  });
  const checklistQ = useQuery({
    queryKey: ["cidadao-checklist", id],
    queryFn: () => api.cidadao.checklistDocumentos(id),
    enabled: !!cidadao && idValido,
  });
  // PR 4d — histórico de complementações do cidadão.
  const complementacoesQ = useQuery({
    queryKey: ["cidadao-complementacoes", id],
    queryFn: () => api.cidadao.listarComplementacoes(id),
    enabled: !!cidadao && idValido,
  });
  const responderM = useMutation({
    mutationFn: (complementacaoId: number) =>
      api.cidadao.responderComplementacao(id, complementacaoId),
    onSuccess: () => {
      toast.success("Pronto: avisamos a prefeitura de que você enviou os documentos.");
      qc.invalidateQueries({ queryKey: ["cidadao-checklist", id] });
      qc.invalidateQueries({ queryKey: ["cidadao-complementacoes", id] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const [uploadKey, setUploadKey] = useState<string | null>(null);
  const [uploadNome, setUploadNome] = useState<string>("");
  const [file, setFile] = useState<File | null>(null);
  const [fileErr, setFileErr] = useState<string | null>(null);

  const uploadM = useMutation({
    mutationFn: () => {
      if (!file || !uploadKey) throw new Error("Escolha o arquivo antes de enviar.");
      return api.cidadao.uploadAnexo(id, file, file.name, uploadKey);
    },
    onSuccess: () => {
      toast.success("Documento enviado.");
      qc.invalidateQueries({ queryKey: ["cidadao-processo", id] });
      qc.invalidateQueries({ queryKey: ["cidadao-checklist", id] });
      qc.invalidateQueries({ queryKey: ["cidadao-complementacoes", id] });
      fecharUpload();
    },
    // O erro aparece dentro do diálogo, junto do arquivo — não num toast atrás dele.
  });

  function abrirUpload(key: string, nome: string) {
    uploadM.reset();
    setUploadKey(key);
    setUploadNome(nome);
    setFile(null);
    setFileErr(null);
  }
  function fecharUpload() {
    setUploadKey(null);
    setFile(null);
    setFileErr(null);
  }
  function escolherArquivo(f: File | null) {
    const problema = f ? problemaDoArquivo(f) : null;
    setFileErr(problema);
    setFile(problema ? null : f);
  }

  if (loading) {
    return (
      <div className="space-y-3">
        <SkeletonLine width="20%" className="h-4" />
        <DetailSkeleton />
      </div>
    );
  }
  if (!cidadao) return null;

  if (!idValido) {
    return (
      <div className="space-y-3">
        <BackLink />
        <EmptyState
          icon={Info}
          title="Endereço de processo inválido"
          description="Abra o processo pela lista de Meus processos."
        />
      </div>
    );
  }

  if (q.isLoading) {
    return (
      <div className="space-y-3">
        <BackLink />
        <DetailSkeleton />
      </div>
    );
  }
  if (q.error || !q.data) {
    return (
      <div className="space-y-3">
        <BackLink />
        <EmptyState
          icon={Info}
          title="Não foi possível abrir esta solicitação"
          description={
            q.error instanceof Error
              ? q.error.message
              : "Tente novamente em instantes ou volte para suas solicitações."
          }
          action={
            <Button asChild size="sm">
              <Link href="/cidadao/processos">Voltar para Meus processos</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const p = q.data;
  const identifier = p.nup ?? p.numero_processo;
  const statusBadge = statusProcessoBadge(p, "cidadao");
  const StatusIcon = statusBadge.icon;
  const prazoBadgeSpec = prazoBadge(p.prazo, "cidadao");
  const PrazoIcon = prazoBadgeSpec?.icon;
  const localAtual = p.local_atual ?? "Aguardando triagem";

  return (
    <div className="space-y-4">
      <BackLink />

      <ProtocoloRecebido idProcesso={p.id} numero={identifier} />

      {/* Identidade: o número do protocolo é o que o cidadão procura e anota. */}
      <Card>
        <CardContent className="space-y-4 pt-4 sm:pt-[var(--density-space)]">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-foreground-subtle">
              Protocolo
            </p>
            <h1 className="mt-0.5 break-all font-mono text-2xl font-semibold tabular-nums text-titulo">
              {identifier}
            </h1>
            <p className="mt-1 text-sm text-foreground-muted">
              Aberto em <span className="tabular-nums">{fmtDiaHora(p.data_hora_abertura)}</span>
              {p.nup && p.numero_processo && p.nup !== p.numero_processo && (
                <span className="block text-xs text-foreground-subtle">
                  Número interno: <span className="font-mono tabular-nums">{p.numero_processo}</span>
                </span>
              )}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <Badge intent={statusBadge.intent} icon={StatusIcon}>
                {statusBadge.label}
              </Badge>
              {p.especie_nome && <Badge intent="neutral">{p.especie_nome}</Badge>}
              {prazoBadgeSpec && PrazoIcon && (
                <Badge intent={prazoBadgeSpec.intent} icon={PrazoIcon}>
                  {prazoBadgeSpec.label}
                </Badge>
              )}
            </div>
          </div>

          <dl className="grid grid-cols-1 gap-4 border-t border-border pt-4 md:grid-cols-2">
            <Dado rotulo="Sobre o quê">{p.assunto ?? "—"}</Dado>
            {p.tipo_processo && <Dado rotulo="Tipo">{p.tipo_processo}</Dado>}
            <Dado rotulo="Onde está agora">{localAtual}</Dado>
            {p.prazo.prazo_estimado_em && (
              <Dado rotulo="Previsão de atendimento">
                <span className="inline-flex items-center gap-1.5 tabular-nums">
                  <CalendarClock className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
                  {fmtDia(p.prazo.prazo_estimado_em)}
                </span>
              </Dado>
            )}
            {/* A classificação documental (CCD) é arquivo interno da
                prefeitura — não diz nada ao cidadão e saiu daqui. */}
            {p.corpo && (
              <Dado rotulo="O que você pediu" largo>
                {p.corpo}
              </Dado>
            )}
            {p.observacao && (
              <Dado rotulo="Mais informações" largo>
                {p.observacao}
              </Dado>
            )}
          </dl>
        </CardContent>
      </Card>

      {/* Próximos passos — sempre logo após a visão geral, para o cidadão
          ver o que fazer agora sem precisar rolar. Calculado no frontend
          a partir dos dados já presentes na tela. */}
      <ProximosPassosCard
        processo={p}
        checklist={checklistQ.data}
        complementacaoAberta={checklistQ.data?.complementacao_aberta}
      />

      {/* Complementação aberta (se houver) */}
      {checklistQ.data?.complementacao_aberta && (
        <ComplementacaoAbertaCard
          data={checklistQ.data.complementacao_aberta}
          modo="cidadao"
          onAnexar={abrirUpload}
          onResponder={() => {
            const cid = checklistQ.data?.complementacao_aberta?.id;
            if (cid) responderM.mutate(cid);
          }}
          respondendo={responderM.isPending}
        />
      )}

      {/* Checklist documental — modo cidadão (microcopy "Documentos necessários") */}
      <ChecklistDocumentosCard
        data={checklistQ.data}
        loading={checklistQ.isLoading}
        modo="cidadao"
        onAnexar={abrirUpload}
      />

      {/* Histórico de complementações anteriores (se houver) */}
      {complementacoesQ.data && (
        <ComplementacoesHistoricoLista
          data={complementacoesQ.data.filter((c) => c.status !== "aberta")}
          title="Complementações anteriores"
        />
      )}

      {/* Andamento vem antes dos anexos: "onde está meu pedido?" é a
          pergunta de quem abre esta tela. */}
      <SectionCard
        icon={History}
        title={`Andamento (${p.movimentacoes.length})`}
        description="Cada passo do seu pedido dentro da prefeitura, do mais antigo ao mais recente."
      >
        {p.movimentacoes.length === 0 ? (
          <EmptyState
            icon={Clock}
            title="Sem movimentações ainda"
            description="Assim que o servidor agir nesta solicitação, o andamento aparecerá aqui."
          />
        ) : (
          <ol className="space-y-3">
            {p.movimentacoes.map((m) => (
              <li key={m.id} className="border-l-2 border-primary pl-4">
                <div className="text-xs text-foreground-muted tabular-nums">
                  {fmtDiaHora(m.data_hora_movimentacao)}
                </div>
                <div className="text-sm">
                  <span className="font-medium text-foreground">{m.acao}</span>
                  {m.unidade_responsavel && (
                    <span className="text-foreground-muted"> em {m.unidade_responsavel}</span>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </SectionCard>

      <SectionCard icon={Paperclip} title={`Anexos (${p.anexos.length})`}>
        {p.anexos.length === 0 ? (
          <EmptyState
            icon={Paperclip}
            title="Sem anexos públicos"
            description="Quando o servidor anexar documentos a esta solicitação, eles aparecerão aqui."
          />
        ) : (
          <ul className="space-y-2">
            {p.anexos.map((a) => (
              <li
                key={a.id}
                className="flex items-center gap-3 rounded-md border border-border bg-surface-1 px-3 py-2"
              >
                <FileText className="h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm">{a.descricao ?? a.e_doc ?? `Anexo ${a.id}`}</div>
                  {a.qtd_paginas != null && (
                    <div className="text-xs text-foreground-muted">
                      {a.qtd_paginas} {a.qtd_paginas === 1 ? "página" : "páginas"}
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      {/* Envio de um documento pedido — body/endpoint preservados. */}
      <Dialog
        open={uploadKey !== null}
        onClose={() => {
          if (!uploadM.isPending) fecharUpload();
        }}
        title={`Enviar: ${uploadNome}`}
        size="sm"
        footer={
          <>
            <Button variant="ghost" onClick={fecharUpload} disabled={uploadM.isPending}>
              Cancelar
            </Button>
            <Button
              loading={uploadM.isPending}
              onClick={() => {
                if (!file) {
                  if (!fileErr) setFileErr("Escolha o arquivo antes de enviar.");
                  document.getElementById("checklist-file")?.focus();
                  return;
                }
                uploadM.mutate();
              }}
            >
              {uploadM.isPending ? "Enviando…" : "Enviar documento"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-foreground-muted">
            Escolha o arquivo de <strong className="text-foreground">{uploadNome}</strong>. Pode ser uma foto
            tirada agora com o celular, desde que dê para ler.
          </p>
          <FormField label="Arquivo" required error={fileErr ?? undefined}>
            <SeletorArquivo id="checklist-file" arquivo={file} onEscolher={escolherArquivo} />
          </FormField>
          {uploadM.isError && <Alert intent="danger">{(uploadM.error as Error).message}</Alert>}
        </div>
      </Dialog>
    </div>
  );
}

function BackLink() {
  return (
    <Link
      href="/cidadao/processos"
      className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Voltar para Meus processos
    </Link>
  );
}

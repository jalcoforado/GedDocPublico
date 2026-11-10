"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, Paperclip, Stamp, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { FormField } from "@/components/ui/form-field";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { AnexoDesentranhar } from "@/components/AnexoDesentranhar";
import { PdfViewerDialog } from "@/components/PdfViewerDialog";
import {
  anexoCarimbadoUrl,
  anexoDownloadUrl,
  anexoInlineUrl,
  api,
  type AnexoNoProcesso,
  type CotaAnexacaoOut,
  type ProcessoDetail,
} from "@/lib/api";

function isPdf(a: AnexoNoProcesso): boolean {
  return !!a.e_doc && a.e_doc.toLowerCase().endsWith(".pdf");
}

interface ViewerState {
  title: string;
  src: string;
  downloadUrl: string;
}

export function AnexosProcesso({ processo }: { processo: ProcessoDetail }) {
  const qc = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const [openUpload, setOpenUpload] = useState(false);
  const [viewer, setViewer] = useState<ViewerState | null>(null);

  const deleteM = useMutation({
    mutationFn: (anexoId: number) =>
      api.processos.deleteAnexo(processo.id, anexoId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["processo", processo.id] });
      toast.success("Anexo excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const carimbarBg = useMutation({
    mutationFn: () => api.jobs.carimbarAnexos(processo.id),
    onSuccess: () => {
      toast.success("Carimbo enfileirado em background.");
      router.push("/m/administracao/jobs");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // E3 — carimbo grava numero_processo em cada página; rascunho não tem um
  // ainda (backend recusa com 409).
  const temPdf = processo.anexos.some(isPdf) && processo.situacao !== "rascunho";

  function tipoNome(a: AnexoNoProcesso) {
    return a.tipo_anexo ?? "—";
  }

  const podeAnexar = processo.ativo && processo.movimentacoes.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {processo.anexos.length} anexo{processo.anexos.length === 1 ? "" : "s"}
        </div>
        <div className="flex gap-2">
          {temPdf && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => carimbarBg.mutate()}
              disabled={carimbarBg.isPending}
              title="Pré-carimba todos os anexos PDF em background (aquece cache)"
            >
              {carimbarBg.isPending ? "Enfileirando..." : "Pré-carimbar PDFs"}
            </Button>
          )}
          <Button onClick={() => setOpenUpload(true)} disabled={!podeAnexar}>
            Adicionar anexo
          </Button>
        </div>
      </div>

      {processo.anexos.length === 0 ? (
        <EmptyState
          icon={Paperclip}
          title="Sem anexos"
          description="Nenhum documento foi anexado a este processo."
          className="p-6"
        />
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-card">
          {processo.anexos.map((a) => (
            <li key={a.id} className="flex flex-col gap-2 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="truncate text-sm font-medium text-foreground">
                    {a.descricao ?? "(sem descrição)"}
                  </span>
                  {!a.publico && <Badge intent="warning">sigiloso</Badge>}
                </div>
                <div className="truncate text-xs text-muted-foreground">
                  {tipoNome(a)} · {a.qtd_paginas ?? "?"} pág
                  {a.e_doc ? ` · ${a.e_doc}` : ""}
                  {a.documento_numero != null ? ` · Doc. nº ${a.documento_numero}` : ""}
                  {a.pagina_processo != null ? ` · fls. ${a.pagina_processo}` : ""}
                </div>
              </div>
              {/* Eram até cinco botões, que quebravam em duas linhas: à vista os
                  dois primeiros, o resto no ⋯ e Excluir por último. Desentranhar
                  tem diálogo próprio e só aparece com permissão. */}
              <div className="flex flex-nowrap items-center gap-1 sm:shrink-0 sm:justify-end">
                {a.id_anexo_processo != null && (
                  <AnexoDesentranhar
                    processoId={processo.id}
                    anexoProcessoId={a.id_anexo_processo}
                    descricaoAnexo={a.descricao}
                  />
                )}
                <AcoesDaLinha
                  acoes={[
                    {
                      label: "Visualizar",
                      icon: Eye,
                      oculta: !isPdf(a),
                      onClick: () =>
                        setViewer({
                          title: a.descricao ?? `Anexo #${a.id}`,
                          src: anexoInlineUrl(a.id),
                          downloadUrl: anexoDownloadUrl(a.id),
                        }),
                    },
                    {
                      label: "Carimbar",
                      icon: Stamp,
                      oculta: !isPdf(a),
                      onClick: () =>
                        setViewer({
                          title: `Carimbado — ${a.descricao ?? `Anexo #${a.id}`}`,
                          src: anexoCarimbadoUrl(a.id),
                          downloadUrl: anexoCarimbadoUrl(a.id, false),
                        }),
                    },
                    {
                      label: "Baixar",
                      icon: Download,
                      onClick: () =>
                        window.open(anexoDownloadUrl(a.id), "_blank", "noopener,noreferrer"),
                    },
                    {
                      label: "Excluir",
                      icon: Trash2,
                      perigo: true,
                      onClick: async () => {
                        const ok = await confirm({
                          title: "Excluir anexo",
                          message: `Excluir "${a.descricao ?? `Anexo #${a.id}`}"? Esta ação não pode ser desfeita.`,
                          confirmLabel: "Excluir",
                          intent: "danger",
                        });
                        if (ok) deleteM.mutate(a.id);
                      },
                    },
                  ]}
                />
              </div>
            </li>
          ))}
        </ul>
      )}

      <UploadDialog
        open={openUpload}
        onClose={() => setOpenUpload(false)}
        processoId={processo.id}
        cota={processo.cota_anexacao}
        onDone={() => qc.invalidateQueries({ queryKey: ["processo", processo.id] })}
      />

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

/** F6 — orçamento do processo, mostrado ANTES de tentar anexar. */
function CotaAnexacaoBar({
  cota,
  arquivoBytes,
}: {
  cota: CotaAnexacaoOut;
  arquivoBytes: number;
}) {
  const mb = (b: number) => (b / (1024 * 1024)).toFixed(1);
  const projetado = cota.usado_bytes + arquivoBytes;
  const pct = Math.min(100, (projetado / cota.limite_bytes) * 100);
  const excede = projetado > cota.limite_bytes;

  return (
    <div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Espaço do processo ({cota.nivel_sigilo})</span>
        <span>
          {mb(projetado)} / {mb(cota.limite_bytes)} MB
        </span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={excede ? "h-full bg-danger" : "h-full bg-brand"}
          style={{ width: `${pct}%` }}
        />
      </div>
      {excede && (
        <p className="mt-1 text-xs text-danger">
          Este arquivo ultrapassa a cota do processo.
        </p>
      )}
    </div>
  );
}

function UploadDialog({
  open,
  onClose,
  processoId,
  cota,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processoId: number;
  cota: CotaAnexacaoOut;
  onDone: () => void;
}) {
  const tiposQ = useQuery({
    queryKey: ["tipos-anexo"],
    queryFn: () => api.tiposAnexo.list(),
  });

  const [file, setFile] = useState<File | null>(null);
  const [descricao, setDescricao] = useState("");
  const [idTipo, setIdTipo] = useState<number | "">("");
  const [publico, setPublico] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const uploadM = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Selecione um arquivo");
      return api.processos.uploadAnexo(processoId, {
        file,
        descricao: descricao || file.name,
        id_tipo_anexo: idTipo || undefined,
        publico,
      });
    },
    onSuccess: () => {
      onDone();
      reset();
      onClose();
    },
    onError: (e: Error) => setErr(e.message),
  });

  function reset() {
    setFile(null);
    setDescricao("");
    setIdTipo("");
    setPublico(true);
    setErr(null);
    setTentou(false);
  }

  // Erro sob o campo só depois de tentar enviar.
  const [tentou, setTentou] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setTentou(true);
    if (!file) {
      document.getElementById("file")?.focus();
      return;
    }
    uploadM.mutate();
  }

  return (
    <Dialog
      open={open}
      onClose={() => {
        reset();
        onClose();
      }}
      title="Adicionar anexo"
      footer={
        <>
          <Button
            variant="ghost"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Cancelar
          </Button>
          <Button onClick={submit} loading={uploadM.isPending}>
            {uploadM.isPending ? "Enviando…" : "Enviar anexo"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-4">
        <CotaAnexacaoBar cota={cota} arquivoBytes={file?.size ?? 0} />
        <FormField
          label="Arquivo"
          required
          hint={
            file
              ? `${file.name} — ${(file.size / 1024).toFixed(1)} KB`
              : "PDF, imagem, texto, planilha ou documento do Office."
          }
          error={tentou && !file ? "Escolha o arquivo a anexar." : undefined}
        >
          <input
            id="file"
            type="file"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !descricao) setDescricao(f.name);
            }}
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods"
            className="block w-full text-sm text-foreground file:mr-3 file:rounded-button file:border-0 file:bg-brand file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-primary-foreground hover:file:bg-brand-light"
          />
        </FormField>
        <FormField
          label="Descrição"
          opcional
          hint="Em branco, vale o nome do arquivo."
        >
          <Input
            id="desc"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            placeholder="Ex.: RG do requerente"
          />
        </FormField>
        <FormField label="Tipo de anexo" opcional>
          <Select
            id="tipo"
            value={idTipo}
            onChange={(e) => setIdTipo(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">Sem tipo</option>
            {tiposQ.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.tipo_anexo}
              </option>
            ))}
          </Select>
        </FormField>
        <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast hover:bg-surface-2">
          <Checkbox
            checked={publico}
            onChange={(e) => setPublico(e.target.checked)}
            className="mt-0.5 h-4 w-4"
          />
          <span className="text-sm">
            <span className="block font-medium text-foreground">Público</span>
            <span className="block text-xs text-foreground-muted">
              Aparece na consulta pública do processo.
            </span>
          </span>
        </label>
        {err && (
          <div
            role="alert"
            className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
          >
            {err}
          </div>
        )}
      </form>
    </Dialog>
  );
}

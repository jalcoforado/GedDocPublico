"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
      router.push("/jobs");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const temPdf = processo.anexos.some(isPdf);

  function tipoNome(a: AnexoNoProcesso) {
    return a.tipo_anexo ?? "—";
  }

  const podeAnexar = processo.ativo && processo.movimentacoes.length > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-sm text-gray-600">
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
        <p className="text-sm text-gray-500">Sem anexos.</p>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-card">
          {processo.anexos.map((a) => (
            <li key={a.id} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-foreground">
                  {a.descricao ?? "(sem descrição)"}
                </div>
                <div className="text-xs text-muted-foreground">
                  {tipoNome(a)} · {a.qtd_paginas ?? "?"} pág
                  {a.publico ? "" : " · sigiloso"}
                  {a.e_doc ? ` · ${a.e_doc}` : ""}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {isPdf(a) && (
                  <>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setViewer({
                          title: a.descricao ?? `Anexo #${a.id}`,
                          src: anexoInlineUrl(a.id),
                          downloadUrl: anexoDownloadUrl(a.id),
                        })
                      }
                    >
                      Visualizar
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() =>
                        setViewer({
                          title: `Carimbado — ${a.descricao ?? `Anexo #${a.id}`}`,
                          src: anexoCarimbadoUrl(a.id),
                          downloadUrl: anexoCarimbadoUrl(a.id, false),
                        })
                      }
                    >
                      Carimbar
                    </Button>
                  </>
                )}
                <a
                  href={anexoDownloadUrl(a.id)}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex h-9 items-center rounded-md border border-transparent px-3 text-xs font-medium text-primary hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  Baixar
                </a>
                {a.id_anexo_processo != null && (
                  <AnexoDesentranhar
                    processoId={processo.id}
                    anexoProcessoId={a.id_anexo_processo}
                    descricaoAnexo={a.descricao}
                  />
                )}
                <Button
                  variant="danger"
                  size="sm"
                  onClick={async () => {
                    const ok = await confirm({
                      title: "Excluir anexo",
                      message: `Excluir "${a.descricao ?? `Anexo #${a.id}`}"? Esta ação não pode ser desfeita.`,
                      confirmLabel: "Excluir",
                      intent: "danger",
                    });
                    if (ok) deleteM.mutate(a.id);
                  }}
                >
                  Excluir
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <UploadDialog
        open={openUpload}
        onClose={() => setOpenUpload(false)}
        processoId={processo.id}
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

function UploadDialog({
  open,
  onClose,
  processoId,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processoId: number;
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
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!file) {
      setErr("Selecione um arquivo");
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
            variant="secondary"
            onClick={() => {
              reset();
              onClose();
            }}
          >
            Cancelar
          </Button>
          <Button onClick={submit} disabled={uploadM.isPending || !file}>
            {uploadM.isPending ? "Enviando..." : "Enviar"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label htmlFor="file">Arquivo *</Label>
          <input
            id="file"
            type="file"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              setFile(f);
              if (f && !descricao) setDescricao(f.name);
            }}
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods"
            className="block w-full text-sm text-gray-700 file:mr-3 file:rounded file:border-0 file:bg-aprimora file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white hover:file:bg-aprimora-light"
          />
          {file && (
            <p className="mt-1 text-xs text-muted-foreground">
              {file.name} — {(file.size / 1024).toFixed(1)} KB
            </p>
          )}
        </div>
        <div>
          <Label htmlFor="desc">Descrição</Label>
          <Input
            id="desc"
            value={descricao}
            onChange={(e) => setDescricao(e.target.value)}
            placeholder="Ex: RG do requerente"
          />
        </div>
        <div>
          <Label htmlFor="tipo">Tipo de anexo</Label>
          <Select
            id="tipo"
            value={idTipo}
            onChange={(e) => setIdTipo(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">—</option>
            {tiposQ.data?.map((t) => (
              <option key={t.id} value={t.id}>
                {t.tipo_anexo}
              </option>
            ))}
          </Select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={publico}
            onChange={(e) => setPublico(e.target.checked)}
          />
          Público (visível para consulta)
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

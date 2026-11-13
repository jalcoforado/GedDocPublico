"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Download,
  Eye,
  File as FileIcon,
  FileImage,
  FileSpreadsheet,
  FileText,
  Globe,
  Lock,
  Paperclip,
  Stamp,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
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
  type CotaAnexacaoOut,
  type ProcessoDetail,
} from "@/lib/api";
import { cn } from "@/lib/utils";

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
        numeroProcesso={processo.numero_processo}
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

const EXTENSOES_ACEITAS = [
  ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".csv",
  ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods",
];

/** "1,2 MB", "830 KB" — no formato brasileiro, como o resto da tela. */
export function tamanhoLegivel(bytes: number): string {
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toLocaleString("pt-BR", { maximumFractionDigits: kb < 10 ? 1 : 0 })} KB`;
  }
  return `${(kb / 1024).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} MB`;
}

function extensao(nome: string): string {
  const i = nome.lastIndexOf(".");
  return i < 0 ? "" : nome.slice(i).toLowerCase();
}

export function arquivoAceito(nome: string): boolean {
  return EXTENSOES_ACEITAS.includes(extensao(nome));
}

function IconeDoArquivo({ nome }: { nome: string }) {
  const ext = extensao(nome);
  const Icone = [".png", ".jpg", ".jpeg", ".gif", ".webp"].includes(ext)
    ? FileImage
    : [".xls", ".xlsx", ".csv", ".ods"].includes(ext)
      ? FileSpreadsheet
      : [".pdf", ".doc", ".docx", ".odt", ".txt"].includes(ext)
        ? FileText
        : FileIcon;
  return <Icone className="h-5 w-5" aria-hidden="true" />;
}

/**
 * F6 — orçamento do processo, mostrado ANTES de tentar anexar. A barra separa
 * o que já está no processo do que este arquivo vai ocupar: quem escolhe um
 * PDF de 150 MB vê o pedaço dele crescer antes de clicar em Enviar.
 */
function CotaAnexacaoBar({
  cota,
  arquivoBytes,
}: {
  cota: CotaAnexacaoOut;
  arquivoBytes: number;
}) {
  const pct = (b: number) => Math.min(100, (b / cota.limite_bytes) * 100);
  const projetado = cota.usado_bytes + arquivoBytes;
  const excede = projetado > cota.limite_bytes;
  const livre = Math.max(0, cota.limite_bytes - projetado);

  return (
    <div className="rounded-md border border-border bg-surface-1 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-3 text-xs">
        <span className="font-medium text-foreground">
          Espaço do processo
          <span className="ml-1.5 font-normal text-foreground-muted">nível {cota.nivel_sigilo}</span>
        </span>
        <span className="tabular-nums text-foreground-muted">
          {tamanhoLegivel(projetado)} de {tamanhoLegivel(cota.limite_bytes)}
        </span>
      </div>
      <div
        className="mt-2 flex h-1.5 w-full overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={`${tamanhoLegivel(projetado)} usados de ${tamanhoLegivel(cota.limite_bytes)}`}
      >
        <div className="h-full bg-foreground-subtle" style={{ width: `${pct(cota.usado_bytes)}%` }} />
        {arquivoBytes > 0 && (
          <div
            className={cn("h-full", excede ? "bg-danger" : "bg-brand")}
            style={{ width: `${pct(projetado) - pct(cota.usado_bytes)}%` }}
          />
        )}
      </div>
      {excede ? (
        <p className="mt-1.5 text-xs font-medium text-danger-soft-foreground">
          Este arquivo passa do espaço do processo — faltam{" "}
          {tamanhoLegivel(projetado - cota.limite_bytes)}.
        </p>
      ) : arquivoBytes > 0 ? (
        <p className="mt-1.5 text-xs text-foreground-muted">
          Este arquivo ocupa {tamanhoLegivel(arquivoBytes)}; sobram {tamanhoLegivel(livre)}.
        </p>
      ) : null}
    </div>
  );
}

/**
 * Onde se escolhe o arquivo: área de soltar (arrastar do explorador de
 * arquivos) que também abre o seletor ao clicar. Escolhido o arquivo, a área
 * vira o cartão dele — nome, tamanho, trocar, tirar.
 *
 * O `<input type="file">` continua no DOM (fora da vista): é ele que o
 * rótulo do FormField aponta, que o teclado alcança e que o leitor de tela
 * anuncia.
 */
function EscolherArquivo({
  file,
  onChange,
  invalido,
  describedBy,
}: {
  file: File | null;
  onChange: (f: File | null, recusado?: string) => void;
  invalido: boolean;
  describedBy?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [arrastando, setArrastando] = useState(false);

  function receber(f: File | undefined) {
    if (!f) return;
    if (!arquivoAceito(f.name)) {
      onChange(null, `“${f.name}” não é um tipo aceito. Use PDF, imagem, texto, planilha ou documento do Office.`);
      return;
    }
    onChange(f);
  }

  return (
    <div
      onDragEnter={(e) => {
        e.preventDefault();
        setArrastando(true);
      }}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastando(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setArrastando(false);
        receber(e.dataTransfer.files?.[0]);
      }}
    >
      <input
        ref={inputRef}
        id="file"
        type="file"
        className="sr-only"
        aria-invalid={invalido || undefined}
        aria-describedby={describedBy}
        accept={EXTENSOES_ACEITAS.join(",")}
        onChange={(e) => {
          receber(e.target.files?.[0]);
          // Limpa para que escolher o MESMO arquivo de novo ainda dispare onChange.
          e.target.value = "";
        }}
      />
      {file ? (
        <div
          className={cn(
            "flex items-center gap-3 rounded-lg border bg-surface-1 px-3 py-3 transition-colors duration-fast",
            arrastando ? "border-brand bg-brand/5" : "border-border",
          )}
        >
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-brand/10 text-brand">
            <IconeDoArquivo nome={file.name} />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium text-foreground" title={file.name}>
              {file.name}
            </span>
            <span className="block text-xs text-foreground-muted">
              {tamanhoLegivel(file.size)}
              {extensao(file.name) && ` · ${extensao(file.name).slice(1).toUpperCase()}`}
            </span>
          </span>
          <Button type="button" variant="ghost" size="sm" onClick={() => inputRef.current?.click()}>
            Trocar
          </Button>
          <button
            type="button"
            onClick={() => onChange(null)}
            aria-label="Tirar o arquivo"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className={cn(
            "flex w-full flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors duration-fast",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
            arrastando
              ? "border-brand bg-brand/5"
              : invalido
                ? "border-danger bg-surface-1 hover:bg-surface-2"
                : "border-border bg-surface-1 hover:border-brand/60 hover:bg-surface-2",
          )}
        >
          <span
            className={cn(
              "flex h-11 w-11 items-center justify-center rounded-full transition-colors duration-fast",
              arrastando ? "bg-brand text-primary-foreground" : "bg-brand/10 text-brand",
            )}
          >
            <Upload className="h-5 w-5" aria-hidden="true" />
          </span>
          <span className="text-sm font-medium text-foreground">
            {arrastando ? "Solte para anexar" : "Arraste o arquivo para cá"}
          </span>
          <span className="text-xs text-foreground-muted">
            ou <span className="font-medium text-brand underline-offset-2 hover:underline">escolha no computador</span>
          </span>
          <span className="mt-1 text-xs text-foreground-subtle">
            PDF, imagem, texto, planilha ou documento do Office
          </span>
        </button>
      )}
    </div>
  );
}

type Visibilidade = "publico" | "sigiloso";

export function UploadDialog({
  open,
  onClose,
  processoId,
  numeroProcesso,
  cota,
  onDone,
}: {
  open: boolean;
  onClose: () => void;
  processoId: number;
  numeroProcesso: string | null;
  cota: CotaAnexacaoOut;
  onDone: () => void;
}) {
  const tiposQ = useQuery({
    queryKey: ["tipos-anexo"],
    queryFn: () => api.tiposAnexo.list(),
  });

  const [file, setFile] = useState<File | null>(null);
  const [recusa, setRecusa] = useState<string | null>(null);
  const [descricao, setDescricao] = useState("");
  // A descrição acompanha o nome do arquivo até a pessoa escrever a sua:
  // trocar o arquivo não deixa para trás o nome do anterior.
  const [descricaoEditada, setDescricaoEditada] = useState(false);
  const [idTipo, setIdTipo] = useState<number | "">("");
  const [visibilidade, setVisibilidade] = useState<Visibilidade>("publico");
  const [err, setErr] = useState<string | null>(null);
  // Erro sob o campo só depois de tentar enviar.
  const [tentou, setTentou] = useState(false);

  const excede = !!file && cota.usado_bytes + file.size > cota.limite_bytes;

  const uploadM = useMutation({
    mutationFn: () => {
      if (!file) throw new Error("Selecione um arquivo");
      return api.processos.uploadAnexo(processoId, {
        file,
        descricao: descricao.trim() || file.name,
        id_tipo_anexo: idTipo || undefined,
        publico: visibilidade === "publico",
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
    setRecusa(null);
    setDescricao("");
    setDescricaoEditada(false);
    setIdTipo("");
    setVisibilidade("publico");
    setErr(null);
    setTentou(false);
  }

  function fechar() {
    reset();
    onClose();
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setTentou(true);
    if (!file) {
      document.getElementById("file")?.focus();
      return;
    }
    if (excede) return;
    uploadM.mutate();
  }

  const erroArquivo = recusa ?? (tentou && !file ? "Escolha o arquivo a anexar." : undefined);

  return (
    <Dialog
      open={open}
      onClose={fechar}
      title="Adicionar anexo"
      description={
        numeroProcesso
          ? `O arquivo entra no processo ${numeroProcesso}.`
          : "O arquivo entra neste processo."
      }
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={fechar}>
            Cancelar
          </Button>
          <Button onClick={submit} loading={uploadM.isPending} disabled={excede}>
            {uploadM.isPending ? "Enviando…" : "Enviar anexo"}
          </Button>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="space-y-5">
        <div className="space-y-1">
          <Label htmlFor="file" required>
            Arquivo
          </Label>
          <EscolherArquivo
            file={file}
            invalido={!!erroArquivo}
            describedBy={erroArquivo ? "file-error" : undefined}
            onChange={(f, motivo) => {
              setRecusa(motivo ?? null);
              setFile(f);
              if (!descricaoEditada) setDescricao(f ? f.name.replace(/\.[^.]+$/, "") : "");
            }}
          />
          {erroArquivo && (
            <p id="file-error" role="alert" className="text-xs font-medium text-danger-soft-foreground">
              {erroArquivo}
            </p>
          )}
        </div>

        <GradeCampos>
          <FormField label="Descrição" opcional hint="Em branco, vale o nome do arquivo.">
            <Input
              id="desc"
              value={descricao}
              onChange={(e) => {
                setDescricao(e.target.value);
                setDescricaoEditada(e.target.value !== "");
              }}
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
        </GradeCampos>

        <EscolhaSegmentada<Visibilidade>
          nome="anexo-visibilidade"
          titulo="Quem pode ver"
          valor={visibilidade}
          onChange={setVisibilidade}
          opcoes={[
            {
              valor: "publico",
              rotulo: "Público",
              icon: Globe,
              descricao: "Aparece na consulta pública do processo.",
            },
            {
              valor: "sigiloso",
              rotulo: "Sigiloso",
              icon: Lock,
              descricao: "Não aparece na consulta pública do processo.",
            },
          ]}
        />

        <CotaAnexacaoBar cota={cota} arquivoBytes={file?.size ?? 0} />

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

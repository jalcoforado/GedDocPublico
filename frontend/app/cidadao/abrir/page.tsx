"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  FileText,
  Paperclip,
  Upload,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type CidadaoAssunto, type CidadaoEspecie } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";
import { cn } from "@/lib/utils";

type Step = 1 | 2 | 3;

// Tem de espelhar `max_upload_size_mb` do backend (app/config.py, hoje 20 e
// também no MAX_UPLOAD_SIZE_MB do compose). Anunciava 25: o portal aceitava um
// arquivo de 22 MB, subia tudo e só então o servidor recusava com "Arquivo
// excede 20 MB". Ao mudar o limite no backend, mudar aqui junto.
const MAX_UPLOAD_MB = 20;
const ALLOWED_EXT = [
  "pdf", "png", "jpg", "jpeg", "gif", "webp",
  "doc", "docx", "xls", "xlsx", "odt", "ods",
];

function extOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

function StepIndicator({ step }: { step: Step }) {
  const items: { n: Step; label: string }[] = [
    { n: 1, label: "Dados" },
    { n: 2, label: "Documento" },
    { n: 3, label: "Confirmação" },
  ];
  return (
    <ol
      aria-label="Etapas"
      className="flex items-center justify-between gap-1 sm:gap-2"
    >
      {items.map((it, idx) => {
        const done = step > it.n;
        const active = step === it.n;
        return (
          <li
            key={it.n}
            className="flex flex-1 items-center gap-2"
            aria-current={active ? "step" : undefined}
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors",
                done && "border-primary bg-primary text-primary-foreground",
                active && !done && "border-primary bg-card text-primary",
                !done && !active && "border-border bg-card text-muted-foreground",
              )}
              aria-hidden="true"
            >
              {done ? <Check className="h-4 w-4" /> : it.n}
            </div>
            <span
              className={cn(
                "hidden text-xs font-medium sm:inline",
                active ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {it.label}
            </span>
            {idx < items.length - 1 && (
              <div
                className={cn(
                  "h-px flex-1 transition-colors",
                  done ? "bg-primary" : "bg-border",
                )}
                aria-hidden="true"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export default function CidadaoAbrirPage() {
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();

  const [step, setStep] = useState<Step>(1);

  // Dados
  const [idAssunto, setIdAssunto] = useState<number | null>(null);
  const [idEspecie, setIdEspecie] = useState<number | null>(null);
  const [corpo, setCorpo] = useState("");
  const [obs, setObs] = useState("");

  // Documento
  const [file, setFile] = useState<File | null>(null);
  const [fileErr, setFileErr] = useState<string | null>(null);

  // Submit
  const [err, setErr] = useState<string | null>(null);

  const assuntosQ = useQuery({
    queryKey: ["cidadao-assuntos"],
    queryFn: () => api.cidadao.assuntos(),
    enabled: !!cidadao,
  });
  const especiesQ = useQuery({
    queryKey: ["cidadao-especies"],
    queryFn: () => api.cidadao.especies(),
    enabled: !!cidadao,
  });

  const enviarM = useMutation({
    mutationFn: async () => {
      if (!idAssunto) throw new Error("Escolha um assunto");
      if (corpo.trim().length < 10)
        throw new Error("Descrição precisa ter no mínimo 10 caracteres");
      const created = await api.cidadao.abrirProcesso({
        id_assunto: idAssunto,
        corpo,
        observacao: obs || undefined,
        id_especie_documental: idEspecie ?? undefined,
      });
      if (file) {
        try {
          await api.cidadao.uploadAnexo(created.id, file, file.name);
        } catch (e) {
          toast.error(
            `Processo aberto, mas falha ao anexar documento: ${(e as Error).message}`,
          );
        }
      }
      return created;
    },
    onSuccess: (data) => {
      toast.success(
        data.nup ? `Protocolado: ${data.nup}` : `Protocolado: ${data.numero_processo}`,
      );
      router.push(`/cidadao/processos/${data.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setFileErr(null);
    const f = e.target.files?.[0] ?? null;
    if (!f) {
      setFile(null);
      return;
    }
    const ext = extOf(f.name);
    if (!ALLOWED_EXT.includes(ext)) {
      setFileErr(
        `Tipo .${ext} não permitido. Use: ${ALLOWED_EXT.join(", ")}`,
      );
      setFile(null);
      return;
    }
    if (f.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setFileErr(`Arquivo excede ${MAX_UPLOAD_MB} MB`);
      setFile(null);
      return;
    }
    setFile(f);
  }

  const canAdvance1 = !!idAssunto && corpo.trim().length >= 10;
  const canAdvance2 = !fileErr; // arquivo é opcional
  const assuntoSelecionado: CidadaoAssunto | undefined = assuntosQ.data?.find(
    (a) => a.id === idAssunto,
  );
  const especieSelecionada: CidadaoEspecie | undefined = especiesQ.data?.find(
    (e) => e.id === idEspecie,
  );

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/processos"
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Abrir novo processo</CardTitle>
          <div className="mt-4">
            <StepIndicator step={step} />
          </div>
        </CardHeader>
        <CardContent>
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <Label htmlFor="assunto" required>
                  Assunto
                </Label>
                <Select
                  id="assunto"
                  value={idAssunto ?? ""}
                  onChange={(e) =>
                    setIdAssunto(e.target.value ? Number(e.target.value) : null)
                  }
                  required
                >
                  <option value="">Selecione...</option>
                  {assuntosQ.data?.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.assunto}
                      {a.tipo_processo ? ` (${a.tipo_processo})` : ""}
                    </option>
                  ))}
                </Select>
              </div>

              <div>
                <Label>Tipo do documento</Label>
                <p className="mb-2 text-xs text-muted-foreground">
                  Como você está se manifestando? (opcional)
                </p>
                <div className="flex flex-wrap gap-2">
                  {especiesQ.data?.map((e) => {
                    const active = idEspecie === e.id;
                    return (
                      <button
                        key={e.id}
                        type="button"
                        onClick={() => setIdEspecie(active ? null : e.id)}
                        aria-pressed={active}
                        className={cn(
                          "rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-card text-foreground hover:border-primary/50",
                        )}
                      >
                        {e.nome}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <Label htmlFor="corpo" required>
                  Descreva sua solicitação
                </Label>
                <Textarea
                  id="corpo"
                  value={corpo}
                  onChange={(e) => setCorpo(e.target.value)}
                  required
                  minLength={10}
                  rows={6}
                  placeholder="Inclua o máximo de detalhes possível."
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Mínimo 10 caracteres ({corpo.trim().length}/10).
                </p>
              </div>

              <div>
                <Label htmlFor="obs">Observação adicional (opcional)</Label>
                <Textarea
                  id="obs"
                  value={obs}
                  onChange={(e) => setObs(e.target.value)}
                  rows={3}
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <Button
                  type="button"
                  disabled={!canAdvance1}
                  onClick={() => setStep(2)}
                >
                  Avançar
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <Label>Documento (opcional)</Label>
                <p className="mb-2 text-xs text-muted-foreground">
                  Anexe um arquivo de até {MAX_UPLOAD_MB} MB. Será publicado junto
                  com a solicitação. Formatos: {ALLOWED_EXT.join(", ")}.
                </p>

                {file ? (
                  <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/30 p-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <FileText className="h-5 w-5" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">
                        {file.name}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {(file.size / 1024).toFixed(1)} KB · .{extOf(file.name)}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setFile(null);
                        setFileErr(null);
                      }}
                      className="text-muted-foreground hover:text-danger"
                      aria-label="Remover arquivo"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ) : (
                  <label
                    htmlFor="file-input"
                    className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-border bg-muted/20 px-4 py-8 text-center transition-colors hover:border-primary/50 hover:bg-muted/40"
                  >
                    <Upload className="h-8 w-8 text-muted-foreground" />
                    <div className="text-sm font-medium text-foreground">
                      Selecionar arquivo
                    </div>
                    <div className="text-xs text-muted-foreground">
                      ou pular esta etapa
                    </div>
                    <input
                      id="file-input"
                      type="file"
                      onChange={handleFileChange}
                      accept={ALLOWED_EXT.map((e) => `.${e}`).join(",")}
                      className="sr-only"
                    />
                  </label>
                )}

                {fileErr && (
                  <div
                    role="alert"
                    className="mt-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
                  >
                    {fileErr}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-between gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setStep(1)}
                >
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  Voltar
                </Button>
                <Button
                  type="button"
                  disabled={!canAdvance2}
                  onClick={() => setStep(3)}
                >
                  Avançar
                  <ArrowRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Confirme os dados abaixo antes de enviar.
              </p>

              <dl className="space-y-3 rounded-lg border border-border bg-muted/20 p-4 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Assunto
                  </dt>
                  <dd className="font-medium">
                    {assuntoSelecionado?.assunto ?? "—"}
                    {assuntoSelecionado?.tipo_processo
                      ? ` (${assuntoSelecionado.tipo_processo})`
                      : ""}
                  </dd>
                </div>
                {especieSelecionada && (
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      Tipo de documento
                    </dt>
                    <dd>{especieSelecionada.nome}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Descrição
                  </dt>
                  <dd className="whitespace-pre-wrap">{corpo}</dd>
                </div>
                {obs && (
                  <div>
                    <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                      Observação
                    </dt>
                    <dd className="whitespace-pre-wrap">{obs}</dd>
                  </div>
                )}
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Documento
                  </dt>
                  <dd className="flex items-center gap-2">
                    {file ? (
                      <>
                        <Paperclip className="h-4 w-4 text-muted-foreground" />
                        {file.name}{" "}
                        <span className="text-xs text-muted-foreground">
                          ({(file.size / 1024).toFixed(1)} KB)
                        </span>
                      </>
                    ) : (
                      <span className="text-muted-foreground">
                        Nenhum arquivo anexado
                      </span>
                    )}
                  </dd>
                </div>
              </dl>

              {err && (
                <div
                  role="alert"
                  className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
                >
                  {err}
                </div>
              )}

              <div className="flex items-center justify-between gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setStep(2)}
                  disabled={enviarM.isPending}
                >
                  <ArrowLeft className="mr-1 h-4 w-4" />
                  Voltar
                </Button>
                <Button
                  type="button"
                  onClick={() => {
                    setErr(null);
                    enviarM.mutate();
                  }}
                  disabled={enviarM.isPending}
                >
                  {enviarM.isPending ? (
                    "Enviando..."
                  ) : (
                    <>
                      <CheckCircle2 className="mr-1 h-4 w-4" />
                      Confirmar e enviar
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

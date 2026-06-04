"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Clock,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton, SkeletonLine } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { portalApi } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

type Step = 1 | 2;
const MIN_CHARS = 10;

function fmtPrazo(dias: number): string {
  return dias === 1 ? "até 1 dia" : `até ${dias} dias`;
}

export default function SolicitarServicoPage() {
  const { slug } = useParams<{ slug: string }>();
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();

  const [step, setStep] = useState<Step>(1);
  const [corpo, setCorpo] = useState("");
  const [obs, setObs] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const servicoQ = useQuery({
    queryKey: ["portal-servico", slug],
    queryFn: () => portalApi.servico(slug),
    enabled: !!cidadao,
  });

  // PR UX-1 Fase B: contrato com backend preservado intacto — `corpo` e
  // `observacao` (opcional) seguem para portalApi.abrirPorServico(...).
  const enviarM = useMutation({
    mutationFn: () =>
      portalApi.abrirPorServico(slug, { corpo, observacao: obs || undefined }),
    onSuccess: (data) => {
      toast.success(
        data.nup ? `Protocolado: ${data.nup}` : `Protocolado: ${data.numero_processo}`,
      );
      router.push(`/cidadao/processos/${data.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  if (loading) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <SkeletonLine width="40%" className="h-4" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    );
  }
  if (!cidadao) return null;

  const trimmedLen = corpo.trim().length;
  const canAdvance = trimmedLen >= MIN_CHARS;
  const servico = servicoQ.data;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href={`/cidadao/servicos/${slug}`}
        className="
          inline-flex items-center gap-1 rounded text-sm text-primary
          hover:underline focus-visible:outline-none focus-visible:ring-2
          focus-visible:ring-ring
        "
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar ao serviço
      </Link>

      <Card>
        <CardHeader>
          {servicoQ.isLoading ? (
            <SkeletonLine width="55%" className="h-6" />
          ) : (
            <CardTitle>
              Solicitar: {servico?.nome ?? "serviço"}
            </CardTitle>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {servico && !servico.solicitar_habilitado && (
            <div
              role="alert"
              className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
            >
              O atendimento online deste serviço está pausado pela prefeitura no
              momento. Você ainda pode acompanhar suas solicitações em{" "}
              <Link href="/cidadao/processos" className="font-medium underline">
                Meus processos
              </Link>
              .
            </div>
          )}

          {/* Resumo do serviço — prazo + documentos */}
          {servico && (servico.prazo_estimado_dias != null ||
            (servico.documentos_exigidos && servico.documentos_exigidos.length > 0)) && (
            <div className="rounded-lg border border-border bg-surface-1 p-3">
              {servico.prazo_estimado_dias != null && (
                <div className="mb-2 flex items-center gap-2 text-sm text-foreground-muted">
                  <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                  <span>
                    Prazo estimado: {fmtPrazo(servico.prazo_estimado_dias)}
                  </span>
                </div>
              )}
              {servico.documentos_exigidos &&
                servico.documentos_exigidos.length > 0 && (
                  <>
                    <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                      <FileText className="h-4 w-4" aria-hidden="true" />
                      Documentos necessários
                    </h3>
                    <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
                      {servico.documentos_exigidos.map((d, i) => (
                        <li key={i}>
                          {d.nome}
                          {d.obrigatorio && (
                            <abbr
                              title="Documento obrigatório"
                              className="ml-0.5 text-danger no-underline"
                            >
                              *
                            </abbr>
                          )}
                          {d.descricao && (
                            <span className="text-foreground-subtle"> — {d.descricao}</span>
                          )}
                        </li>
                      ))}
                    </ul>
                    {servico.documentos_exigidos.some((d) => d.obrigatorio) && (
                      <p className="mt-1 text-[10px] text-foreground-subtle">
                        <span className="text-danger">*</span> obrigatório
                      </p>
                    )}
                    <p className="mt-2 text-xs text-foreground-subtle">
                      Você poderá anexar os documentos depois de abrir a
                      solicitação.
                    </p>
                  </>
                )}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <div>
                <Label htmlFor="corpo" required>
                  Descreva sua solicitação
                </Label>
                <Textarea
                  id="corpo"
                  value={corpo}
                  onChange={(e) => setCorpo(e.target.value)}
                  rows={6}
                  minLength={MIN_CHARS}
                  placeholder="Conte com seus detalhes o que você precisa. Quanto mais claro, mais rápido conseguimos atender."
                />
                <div className="mt-1 flex items-center gap-2 text-xs">
                  <div
                    className="h-1 flex-1 overflow-hidden rounded-full bg-muted"
                    aria-hidden="true"
                  >
                    <div
                      className={cn(
                        "h-full transition-all duration-base",
                        canAdvance ? "bg-success-soft-foreground" : "bg-brand",
                      )}
                      style={{
                        width: `${Math.min(100, (trimmedLen / MIN_CHARS) * 100)}%`,
                      }}
                    />
                  </div>
                  <span
                    className={cn(
                      "tabular-nums",
                      canAdvance
                        ? "text-success-soft-foreground"
                        : "text-foreground-muted",
                    )}
                  >
                    {trimmedLen}/{MIN_CHARS}
                  </span>
                </div>
                {!canAdvance && (
                  <p className="mt-1 text-xs text-foreground-subtle">
                    Inclua pelo menos {MIN_CHARS} caracteres para continuar.
                  </p>
                )}
              </div>
              <div>
                <Label htmlFor="obs">Observação (opcional)</Label>
                <Textarea
                  id="obs"
                  value={obs}
                  onChange={(e) => setObs(e.target.value)}
                  rows={3}
                  placeholder="Algum detalhe adicional?"
                />
              </div>
              <div className="flex justify-end pt-2">
                <Button
                  type="button"
                  disabled={
                    !canAdvance ||
                    (servico ? !servico.solicitar_habilitado : false)
                  }
                  onClick={() => setStep(2)}
                >
                  Avançar
                  <ArrowRight className="ml-1 h-4 w-4" aria-hidden="true" />
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Confira os dados antes de enviar.
              </p>
              {servico?.texto_confirmacao && (
                <div className="rounded-md bg-info-soft px-3 py-2 text-sm text-info-soft-foreground">
                  {servico.texto_confirmacao}
                </div>
              )}
              <dl className="space-y-3 rounded-lg border border-border bg-surface-1 p-4 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Serviço
                  </dt>
                  <dd className="font-medium">{servico?.nome}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted-foreground">
                    Sua solicitação
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
                  onClick={() => setStep(1)}
                  disabled={enviarM.isPending}
                >
                  <ArrowLeft className="mr-1 h-4 w-4" aria-hidden="true" />
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
                    "Enviando…"
                  ) : (
                    <>
                      <CheckCircle2
                        className="mr-1 h-4 w-4"
                        aria-hidden="true"
                      />
                      Confirmar e enviar
                    </>
                  )}
                </Button>
              </div>

              {enviarM.isSuccess && (
                <p className="text-xs text-success-soft-foreground">
                  Solicitação enviada. Você será levado(a) ao acompanhamento em
                  instantes.
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

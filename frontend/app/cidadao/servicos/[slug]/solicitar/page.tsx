"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CheckCircle2, FileText } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { portalApi } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";

type Step = 1 | 2;

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

  if (loading) return <p className="text-sm text-muted-foreground">Carregando...</p>;
  if (!cidadao) return null;

  const canAdvance = corpo.trim().length >= 10;
  const servico = servicoQ.data;

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href={`/cidadao/servicos/${slug}`}
        className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        Voltar ao serviço
      </Link>

      <Card>
        <CardHeader>
          <CardTitle>Solicitar: {servico?.nome ?? "serviço"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {servico && !servico.solicitar_habilitado && (
            <div
              role="alert"
              className="rounded-md bg-warning-soft px-3 py-2 text-sm text-warning-soft-foreground"
            >
              Este serviço não está disponível para solicitação online no momento.
            </div>
          )}

          {servico?.documentos_exigidos && servico.documentos_exigidos.length > 0 && (
            <div className="rounded-lg border border-border bg-surface-1 p-3">
              <h3 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                <FileText className="h-4 w-4" aria-hidden="true" />
                Documentos exigidos
              </h3>
              <ul className="mt-1 list-inside list-disc text-sm text-foreground-muted">
                {servico.documentos_exigidos.map((d, i) => (
                  <li key={i}>
                    {d.nome}
                    {d.obrigatorio && <span className="text-danger"> *</span>}
                    {d.descricao && (
                      <span className="text-foreground-subtle"> — {d.descricao}</span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-xs text-foreground-subtle">
                Você poderá anexar documentos depois de abrir a solicitação.
              </p>
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
                  minLength={10}
                  placeholder="Inclua o máximo de detalhes possível."
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  Mínimo 10 caracteres ({corpo.trim().length}/10).
                </p>
              </div>
              <div>
                <Label htmlFor="obs">Observação adicional (opcional)</Label>
                <Textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} />
              </div>
              <div className="flex justify-end pt-2">
                <Button
                  type="button"
                  disabled={!canAdvance || (servico && !servico.solicitar_habilitado)}
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
              <p className="text-sm text-muted-foreground">
                Confirme os dados antes de enviar.
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

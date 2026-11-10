"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Clock, ListChecks } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { ListaDocumentos } from "@/components/cidadao/ListaDocumentos";
import { marcarProtocoloRecebido } from "@/components/cidadao/ProtocoloRecebido";
import { useErrosDepoisDaTentativa } from "@/components/cidadao/useErrosDepoisDaTentativa";
import { Alert } from "@/components/ui/alert";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
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
  const passoRef = useRef<HTMLDivElement>(null);

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
      marcarProtocoloRecebido(data.id);
      toast.success(
        data.nup ? `Protocolado: ${data.nup}` : `Protocolado: ${data.numero_processo}`,
      );
      router.push(`/cidadao/processos/${data.id}`);
    },
    onError: (e: Error) => setErr(e.message),
  });

  const trimmedLen = corpo.trim().length;
  const canAdvance = trimmedLen >= MIN_CHARS;
  const v = useErrosDepoisDaTentativa({
    corpo: canAdvance
      ? null
      : trimmedLen === 0
        ? "Conte o que você precisa."
        : `Escreva um pouco mais: faltam ${MIN_CHARS - trimmedLen} letras.`,
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

  const servico = servicoQ.data;
  const pausado = servico ? !servico.solicitar_habilitado : false;

  function irPara(n: Step) {
    setStep(n);
    setTimeout(() => passoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function avancar() {
    if (!v.tentar()) {
      setTimeout(() => focarPrimeiroInvalido(passoRef.current ?? document), 0);
      return;
    }
    irPara(2);
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href={`/cidadao/servicos/${slug}`}
        className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar ao serviço
      </Link>

      {servicoQ.isLoading ? (
        <SkeletonLine width="55%" className="h-7" />
      ) : (
        <PageHeader
          icon={ListChecks}
          title={`Solicitar: ${servico?.nome ?? "serviço"}`}
          description="Conte o que você precisa. Os documentos você anexa depois, na página do pedido."
        />
      )}

      {pausado && (
        <div
          role="alert"
          className="rounded-lg border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning-soft-foreground"
        >
          O atendimento online deste serviço está pausado pela prefeitura no
          momento. Você ainda pode acompanhar suas solicitações em{" "}
          <Link href="/cidadao/processos" className="font-medium underline">
            Meus processos
          </Link>
          .
        </div>
      )}

      {/* Resumo do serviço — prazo + documentos, para a pessoa já ir separando. */}
      {servico &&
        (servico.prazo_estimado_dias != null || (servico.documentos_exigidos?.length ?? 0) > 0) && (
          <div className="space-y-3 rounded-card border border-border bg-surface-1 p-4">
            {servico.prazo_estimado_dias != null && (
              <p className="flex items-center gap-2 text-sm text-foreground-muted">
                <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>Prazo estimado: {fmtPrazo(servico.prazo_estimado_dias)}</span>
              </p>
            )}
            <ListaDocumentos documentos={servico.documentos_exigidos ?? []} />
            {(servico.documentos_exigidos?.length ?? 0) > 0 && (
              <p className="text-xs text-foreground-muted">
                Ainda não precisa enviar: você anexa os documentos depois de abrir a solicitação.
              </p>
            )}
          </div>
        )}

      <p className="text-xs font-medium text-foreground-muted" aria-live="polite">
        Etapa {step} de 2 — {step === 1 ? "o seu pedido" : "conferir e enviar"}
      </p>

      <div ref={passoRef} className="scroll-mt-24 space-y-4">
        {step === 1 && (
          <SectionCard title="O seu pedido">
            <FormField
              label="Descreva sua solicitação"
              required
              error={v.erro("corpo")}
              hint="Diga o que precisa e, se for o caso, o endereço ou o número do imóvel. Quanto mais claro, mais rápido."
            >
              <Textarea
                id="corpo"
                value={corpo}
                onChange={(e) => setCorpo(e.target.value)}
                onBlur={v.sair("corpo")}
                rows={6}
                placeholder="Ex.: Preciso da certidão para o imóvel da Rua das Flores, 120, que vou vender."
              />
            </FormField>
            {/* Medidor do mínimo: a pessoa vê quanto falta sem errar primeiro. */}
            <div className="-mt-2 flex items-center gap-2 text-xs" aria-hidden="true">
              <div className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn(
                    "h-full transition-all duration-base",
                    canAdvance ? "bg-success" : "bg-brand",
                  )}
                  style={{ width: `${Math.min(100, (trimmedLen / MIN_CHARS) * 100)}%` }}
                />
              </div>
              <span
                className={cn(
                  "tabular-nums",
                  canAdvance ? "text-success-soft-foreground" : "text-foreground-muted",
                )}
              >
                {trimmedLen}/{MIN_CHARS}
              </span>
            </div>
            <FormField label="Mais alguma informação?" opcional hint="Um ponto de referência, o melhor horário para falar com você…">
              <Textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} />
            </FormField>
          </SectionCard>
        )}

        {step === 2 && (
          <SectionCard
            title="Confira antes de enviar"
            description="Depois de enviado, o pedido não pode ser editado. Se precisar mudar algo, volte."
          >
            {servico?.texto_confirmacao && <Alert intent="info">{servico.texto_confirmacao}</Alert>}
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs font-medium text-foreground-muted">Serviço</dt>
                <dd className="mt-0.5 font-medium text-foreground">{servico?.nome}</dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-foreground-muted">O que você pediu</dt>
                <dd className="mt-0.5 whitespace-pre-wrap break-words text-foreground">{corpo}</dd>
              </div>
              {obs && (
                <div>
                  <dt className="text-xs font-medium text-foreground-muted">Mais informações</dt>
                  <dd className="mt-0.5 whitespace-pre-wrap break-words text-foreground">{obs}</dd>
                </div>
              )}
            </dl>
          </SectionCard>
        )}

        {err && <Alert intent="danger">{err}</Alert>}
        {enviarM.isSuccess && (
          <p role="status" className="text-sm text-success-soft-foreground">
            Solicitação enviada. Abrindo o acompanhamento…
          </p>
        )}
      </div>

      <BarraAcoesFormulario
        className="bottom-[var(--barra-inferior,0px)] sm:bottom-0"
        status={step === 1 ? "Etapa 1 de 2" : "Etapa 2 de 2 — tudo certo? Envie."}
      >
        {step === 1 ? (
          <>
            <Button asChild variant="ghost">
              <Link href={`/cidadao/servicos/${slug}`}>Cancelar</Link>
            </Button>
            {/* Desabilitado só quando a prefeitura pausou o serviço — não por
                validação: clicar com o texto curto mostra o que falta. */}
            <Button type="button" disabled={pausado} onClick={avancar}>
              Continuar
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </Button>
          </>
        ) : (
          <>
            <Button
              type="button"
              variant="secondary"
              onClick={() => irPara(1)}
              disabled={enviarM.isPending}
            >
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Voltar
            </Button>
            <Button
              type="button"
              loading={enviarM.isPending}
              onClick={() => {
                setErr(null);
                enviarM.mutate();
              }}
            >
              {enviarM.isPending ? "Enviando…" : "Enviar solicitação"}
            </Button>
          </>
        )}
      </BarraAcoesFormulario>
    </div>
  );
}

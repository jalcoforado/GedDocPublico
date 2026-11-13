"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, Paperclip, PenSquare } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { problemaDoArquivo, tamanhoLegivel } from "@/components/cidadao/formato";
import { marcarProtocoloRecebido } from "@/components/cidadao/ProtocoloRecebido";
import { SeletorArquivo } from "@/components/cidadao/SeletorArquivo";
import { useErrosDepoisDaTentativa } from "@/components/cidadao/useErrosDepoisDaTentativa";
import { Alert } from "@/components/ui/alert";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, focarPrimeiroInvalido } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type CidadaoAssunto, type CidadaoEspecie } from "@/lib/api";
import { useRequireCidadao } from "@/lib/cidadao-auth";
import { cn } from "@/lib/utils";

type Step = 1 | 2 | 3;
const MIN_CHARS = 10;

const ETAPAS: { n: Step; label: string }[] = [
  { n: 1, label: "O pedido" },
  { n: 2, label: "Anexo" },
  { n: 3, label: "Conferir" },
];

/**
 * O que cada espécie quer dizer, em palavras de quem não é do protocolo.
 * Chave = `codigo` da espécie (o backend oferece Requerimento, Petição e
 * Declaração ao portal). Espécie sem texto aqui aparece só com o nome.
 */
const ESPECIE_EM_PALAVRAS: Record<string, string> = {
  REQUERIMENTO: "Para pedir algo à prefeitura: um documento, um serviço, uma autorização.",
  PETICAO: "Para um pedido formal a uma autoridade, explicando os seus motivos.",
  DECLARACAO: "Para informar ou declarar um fato à prefeitura.",
};

function StepIndicator({ step }: { step: Step }) {
  return (
    <ol aria-label="Etapas" className="flex items-center gap-2">
      {ETAPAS.map((it, idx) => {
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
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-xs font-semibold transition-colors duration-fast",
                done && "border-primary bg-primary text-primary-foreground",
                active && "border-primary bg-card text-primary ring-2 ring-primary/20",
                !done && !active && "border-border bg-card text-foreground-muted",
              )}
              aria-hidden="true"
            >
              {done ? <Check className="h-4 w-4" /> : it.n}
            </div>
            <span
              className={cn(
                "whitespace-nowrap text-xs font-medium",
                active ? "text-foreground" : "text-foreground-muted",
              )}
            >
              <span className="sr-only">Etapa {it.n} de {ETAPAS.length}: </span>
              {it.label}
              {done && <span className="sr-only"> (feita)</span>}
            </span>
            {idx < ETAPAS.length - 1 && (
              <div
                className={cn("h-px min-w-3 flex-1 transition-colors duration-fast", done ? "bg-primary" : "bg-border")}
                aria-hidden="true"
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Resumo({
  rotulo,
  onAlterar,
  children,
}: {
  rotulo: string;
  onAlterar?: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border py-3 first:pt-0 last:border-0 last:pb-0">
      <div className="min-w-0">
        <dt className="text-xs font-medium text-foreground-muted">{rotulo}</dt>
        <dd className="mt-0.5 whitespace-pre-wrap break-words text-sm text-foreground">{children}</dd>
      </div>
      {onAlterar && (
        <button
          type="button"
          onClick={onAlterar}
          aria-label={`Alterar: ${rotulo}`}
          className="-mr-2 inline-flex min-h-9 shrink-0 items-center rounded-md px-2 text-sm font-medium text-primary transition-colors duration-fast hover:bg-muted"
        >
          Alterar
        </button>
      )}
    </div>
  );
}

export default function CidadaoAbrirPage() {
  const router = useRouter();
  const toast = useToast();
  const { cidadao, loading } = useRequireCidadao();
  const passoRef = useRef<HTMLDivElement>(null);

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
      if (!idAssunto) throw new Error("Escolha sobre o que é o pedido.");
      if (corpo.trim().length < MIN_CHARS)
        throw new Error(`A descrição precisa ter pelo menos ${MIN_CHARS} letras.`);
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
            `O processo foi aberto, mas o documento não subiu: ${(e as Error).message}. Você pode anexá-lo de novo na página do processo.`,
          );
        }
      }
      return created;
    },
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
  const v = useErrosDepoisDaTentativa({
    assunto: idAssunto ? null : "Escolha o tema do pedido. Se nenhum servir, escolha o mais parecido.",
    corpo:
      trimmedLen >= MIN_CHARS
        ? null
        : trimmedLen === 0
          ? "Conte o que você precisa."
          : `Escreva um pouco mais: faltam ${MIN_CHARS - trimmedLen} letras.`,
  });

  if (loading) return <Carregando className="text-sm text-foreground-muted" />;
  if (!cidadao) return null;

  function handleFile(f: File | null) {
    setFileErr(null);
    if (!f) {
      setFile(null);
      return;
    }
    const problema = problemaDoArquivo(f);
    if (problema) {
      setFileErr(problema);
      setFile(null);
      return;
    }
    setFile(f);
  }

  function irPara(n: Step) {
    setStep(n);
    // Nova etapa começa do topo — no celular, o botão fica lá embaixo.
    setTimeout(() => passoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
  }

  function avancarDo1() {
    if (!v.tentar(["assunto", "corpo"])) {
      setTimeout(() => focarPrimeiroInvalido(passoRef.current ?? document), 0);
      return;
    }
    irPara(2);
  }

  const assuntoSelecionado: CidadaoAssunto | undefined = assuntosQ.data?.find(
    (a) => a.id === idAssunto,
  );
  const especies = especiesQ.data ?? [];
  const especieSelecionada: CidadaoEspecie | undefined = especies.find((e) => e.id === idEspecie);
  const faltando = [
    !idAssunto && "o tema",
    trimmedLen < MIN_CHARS && "a descrição",
  ].filter(Boolean) as string[];

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/cidadao/processos"
        className="inline-flex min-h-9 items-center gap-1 rounded text-sm text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Voltar para Meus processos
      </Link>

      <PageHeader
        icon={PenSquare}
        title="Abrir processo"
        description="Faça um pedido à prefeitura. No fim você recebe um número para acompanhar."
      />

      <StepIndicator step={step} />

      <div ref={passoRef} className="scroll-mt-24 space-y-4">
        {step === 1 && (
          <SectionCard title="O que você precisa" description="Escolha o tema e conte, com as suas palavras, o que deseja.">
            <FormField
              label="Sobre o que é o seu pedido?"
              required
              error={v.erro("assunto")}
              hint="Escolha o tema mais próximo. Se nenhum servir, escolha o mais parecido e explique na descrição."
            >
              <Select
                id="assunto"
                value={idAssunto ?? ""}
                onChange={(e) => setIdAssunto(e.target.value ? Number(e.target.value) : null)}
                onBlur={v.sair("assunto")}
              >
                <option value="">{assuntosQ.isLoading ? "Carregando os temas…" : "Escolha um tema…"}</option>
                {assuntosQ.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.assunto}
                    {a.tipo_processo ? ` (${a.tipo_processo})` : ""}
                  </option>
                ))}
              </Select>
            </FormField>

            {especies.length > 0 && especies.length <= 3 ? (
              <EscolhaSegmentada
                nome="especie"
                titulo="Que tipo de pedido é este? (opcional)"
                moldura={false}
                valor={idEspecie ? String(idEspecie) : ""}
                onChange={(val) => setIdEspecie(val ? Number(val) : null)}
                opcoes={[
                  {
                    valor: "",
                    rotulo: "Não sei",
                    descricao: "Tudo bem: a prefeitura classifica o pedido para você.",
                  },
                  ...especies.map((e) => ({
                    valor: String(e.id),
                    rotulo: e.nome,
                    descricao: ESPECIE_EM_PALAVRAS[e.codigo],
                  })),
                ]}
              />
            ) : especies.length > 3 ? (
              // Muitas espécies: botões que quebram linha, um toque marca e outro desmarca.
              <fieldset>
                <legend className="mb-1 text-sm font-medium text-foreground">
                  Que tipo de pedido é este?
                  <span className="ml-1.5 text-xs font-normal text-foreground-subtle">opcional</span>
                </legend>
                <p className="mb-2 text-xs text-foreground-muted">Se não souber, deixe sem marcar — a prefeitura classifica.</p>
                <div className="flex flex-wrap gap-2">
                  {especies.map((e) => {
                    const active = idEspecie === e.id;
                    return (
                      <button
                        key={e.id}
                        type="button"
                        onClick={() => setIdEspecie(active ? null : e.id)}
                        aria-pressed={active}
                        className={cn(
                          "min-h-11 rounded-full border px-4 text-sm font-medium transition-colors duration-fast",
                          active
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-card text-foreground hover:border-primary/50 hover:bg-muted",
                        )}
                      >
                        {e.nome}
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            ) : null}

            <FormField
              label="Conte o que você precisa"
              required
              error={v.erro("corpo")}
              hint={
                <>
                  Diga o quê, onde e desde quando — quanto mais claro, mais rápido o atendimento.{" "}
                  <span className="tabular-nums">
                    ({trimmedLen < MIN_CHARS ? `mínimo ${MIN_CHARS} letras, ${trimmedLen} até agora` : "ok"})
                  </span>
                </>
              }
            >
              <Textarea
                id="corpo"
                value={corpo}
                onChange={(e) => setCorpo(e.target.value)}
                onBlur={v.sair("corpo")}
                rows={6}
                placeholder="Ex.: A lâmpada do poste em frente ao nº 120 da Rua das Flores está apagada há uma semana."
              />
            </FormField>

            <FormField
              label="Mais alguma informação?"
              opcional
              hint="Um ponto de referência, o melhor horário para falar com você…"
            >
              <Textarea id="obs" value={obs} onChange={(e) => setObs(e.target.value)} rows={3} />
            </FormField>
          </SectionCard>
        )}

        {step === 2 && (
          <SectionCard
            title="Quer anexar um documento?"
            description="Uma foto ou um arquivo que ajude a entender o pedido. Se não tiver, é só continuar."
          >
            <FormField
              label="Documento"
              opcional
              error={fileErr ?? undefined}
              hint="O arquivo segue junto com o pedido."
            >
              <SeletorArquivo id="file-input" arquivo={file} onEscolher={handleFile} />
            </FormField>
          </SectionCard>
        )}

        {step === 3 && (
          <SectionCard
            title="Confira antes de enviar"
            description="Se algo estiver errado, toque em Alterar. Depois de enviado, o pedido não pode ser editado."
          >
            <dl>
              <Resumo rotulo="Sobre o quê" onAlterar={() => irPara(1)}>
                {assuntoSelecionado?.assunto ?? "—"}
                {assuntoSelecionado?.tipo_processo ? ` (${assuntoSelecionado.tipo_processo})` : ""}
              </Resumo>
              {especieSelecionada && (
                <Resumo rotulo="Tipo de pedido" onAlterar={() => irPara(1)}>
                  {especieSelecionada.nome}
                </Resumo>
              )}
              <Resumo rotulo="O que você precisa" onAlterar={() => irPara(1)}>
                {corpo}
              </Resumo>
              {obs && (
                <Resumo rotulo="Mais informações" onAlterar={() => irPara(1)}>
                  {obs}
                </Resumo>
              )}
              <Resumo rotulo="Documento" onAlterar={() => irPara(2)}>
                {file ? (
                  <span className="inline-flex items-center gap-2">
                    <Paperclip className="h-4 w-4 shrink-0 text-foreground-muted" aria-hidden="true" />
                    <span className="break-all">{file.name}</span>
                    <span className="text-xs text-foreground-muted">({tamanhoLegivel(file.size)})</span>
                  </span>
                ) : (
                  <span className="text-foreground-muted">Nenhum arquivo anexado</span>
                )}
              </Resumo>
            </dl>
          </SectionCard>
        )}

        {err && <Alert intent="danger">{err}</Alert>}
      </div>

      {/* Acima da barra de navegação do celular (ver `--barra-inferior` no layout). */}
      <BarraAcoesFormulario
        className="bottom-[var(--barra-inferior,0px)] sm:bottom-0"
        status={
          step === 1
            ? faltando.length > 0
              ? `Etapa 1 de 3 — falta ${faltando.join(" e ")}.`
              : "Etapa 1 de 3 — pronta."
            : step === 2
              ? "Etapa 2 de 3 — o anexo é opcional."
              : "Etapa 3 de 3 — tudo certo? Envie."
        }
      >
        {step === 1 ? (
          <Button asChild variant="ghost">
            <Link href="/cidadao/processos">Cancelar</Link>
          </Button>
        ) : (
          <Button
            type="button"
            variant="secondary"
            onClick={() => irPara(step === 3 ? 2 : 1)}
            disabled={enviarM.isPending}
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            Voltar
          </Button>
        )}
        {step === 1 && (
          <Button type="button" onClick={avancarDo1}>
            Continuar
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        )}
        {step === 2 && (
          <Button type="button" onClick={() => irPara(3)}>
            {file ? "Continuar" : "Continuar sem anexo"}
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        )}
        {step === 3 && (
          <Button
            type="button"
            loading={enviarM.isPending}
            onClick={() => {
              setErr(null);
              enviarM.mutate();
            }}
          >
            {enviarM.isPending ? "Enviando…" : "Abrir processo"}
          </Button>
        )}
      </BarraAcoesFormulario>
    </div>
  );
}

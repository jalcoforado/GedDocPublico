"use client";

import { Carregando } from "@/components/ui/carregando";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock,
  FileText,
  Inbox,
  Keyboard,
  Lock,
  Plus,
  Printer,
  Receipt,
  Tag,
  User,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { FormField } from "@/components/ui/form-field";
import { resumoDoQueFalta } from "@/components/ui/roteiro-formulario";
import { SectionCard } from "@/components/ui/section-card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  ccdApi,
  protocoloApi,
  protocoloComprovantePdfUrl,
  protocoloEtiquetaPdfUrl,
  type CcdClasseTreeNode,
  type ProtocoloBalcaoResult,
  type SugestaoCcd,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useAssuntosAll } from "@/lib/assuntos";
import { useManifestantesBusca } from "@/lib/manifestantes";

type FormState = {
  id_especie_documental: number | "";
  id_manifestante: number | "";
  id_assunto: number | "";
  id_unidade_proprietaria: number | "";
  id_ccd_classe: number | "";
  numero_origem: string;
  observacao: string;
  publico: boolean;
};

function flatTreeForCombobox(
  nodes: CcdClasseTreeNode[],
): ComboboxOption[] {
  const out: ComboboxOption[] = [];
  function walk(ns: CcdClasseTreeNode[], depth: number) {
    for (const n of ns) {
      const indent = depth === 0 ? "" : "— ".repeat(depth);
      out.push({
        value: n.id,
        label: `${indent}${n.codigo} ${n.nome}`,
        hint: depth === 0 ? "raiz" : undefined,
      });
      if (n.filhos.length) walk(n.filhos, depth + 1);
    }
  }
  walk(nodes, 0);
  return out;
}

const PROTOCOLO_HISTORY_KEY = "aprimora.protocolo.balcao.recentes.v1";
const HISTORY_MAX = 8;

interface ProtocoloRecente {
  numero_processo: string;
  id: number;
  manifestante: string;
  especie_documental: string | null;
  data_recepcao: string | null;
}

function carregarRecentes(): ProtocoloRecente[] {
  try {
    const raw = window.localStorage.getItem(PROTOCOLO_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.slice(0, HISTORY_MAX) : [];
  } catch {
    return [];
  }
}

function gravarRecente(r: ProtocoloRecente, prev: ProtocoloRecente[]): ProtocoloRecente[] {
  const next = [r, ...prev.filter((p) => p.id !== r.id)].slice(0, HISTORY_MAX);
  try {
    window.localStorage.setItem(PROTOCOLO_HISTORY_KEY, JSON.stringify(next));
  } catch {
    // ignore quota
  }
  return next;
}

function fmtHora(s: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  return d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/** Tecla de atalho à vista (os atalhos são o que faz o balcão andar rápido). */
function Tecla({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-border bg-surface-2 px-1.5 py-0.5 font-mono text-[10px] text-foreground">
      {children}
    </kbd>
  );
}

export default function ProtocoloBalcaoPage() {
  const toast = useToast();
  const { user } = useAuth();

  const especiesQ = useQuery({
    queryKey: ["especies-documentais"],
    queryFn: () => protocoloApi.listEspecies(false),
  });
  const assuntosQ = useAssuntosAll();
  const ccdTreeQ = useQuery({
    queryKey: ["ccd-tree"],
    queryFn: () => ccdApi.tree(),
  });

  const [form, setForm] = useState<FormState>({
    id_especie_documental: "",
    id_manifestante: "",
    id_assunto: "",
    id_unidade_proprietaria: user?.id_unidade_trabalho ?? "",
    id_ccd_classe: "",
    numero_origem: "",
    observacao: "",
    publico: true,
  });
  const [err, setErr] = useState<string | null>(null);
  const [tentouEnviar, setTentouEnviar] = useState(false);
  const [recentes, setRecentes] = useState<ProtocoloRecente[]>([]);
  const [lastProtocolo, setLastProtocolo] = useState<ProtocoloBalcaoResult | null>(
    null,
  );
  const [sugestoes, setSugestoes] = useState<SugestaoCcd[]>([]);
  const [loadingSugestoes, setLoadingSugestoes] = useState(false);

  useEffect(() => {
    setRecentes(carregarRecentes());
  }, []);

  // Garante que unidade pega o default do usuário quando user carrega
  useEffect(() => {
    if (form.id_unidade_proprietaria === "" && user?.id_unidade_trabalho) {
      setForm((f) => ({ ...f, id_unidade_proprietaria: user.id_unidade_trabalho! }));
    }
  }, [user?.id_unidade_trabalho, form.id_unidade_proprietaria]);

  const especies = especiesQ.data ?? [];

  // Busca no servidor: a lista de manifestantes cresce sem limite e o
  // backend corta em page_size ≤ 200 (pedir 500 dava 422 e combo vazio).
  const manifestanteBusca = useManifestantesBusca(form.id_manifestante || null);

  const assuntoOptions = useMemo<ComboboxOption[]>(() => {
    return (assuntosQ.data ?? []).map((a) => ({
      value: a.id,
      label: a.assunto,
    }));
  }, [assuntosQ.data]);

  const ccdOptions = useMemo<ComboboxOption[]>(
    () => (ccdTreeQ.data ? flatTreeForCombobox(ccdTreeQ.data) : []),
    [ccdTreeQ.data],
  );

  // Sugestão automática de CCD quando o usuário escolhe um assunto e ainda
  // não definiu classe — debounced 300ms pra evitar request por keystroke.
  useEffect(() => {
    if (!form.id_assunto || form.id_ccd_classe) {
      setSugestoes([]);
      return;
    }
    const id_assunto = Number(form.id_assunto);
    const t = setTimeout(async () => {
      try {
        setLoadingSugestoes(true);
        const sug = await ccdApi.sugerir({ id_assunto, limit: 3 });
        setSugestoes(sug);
      } catch {
        setSugestoes([]);
      } finally {
        setLoadingSugestoes(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [form.id_assunto, form.id_ccd_classe]);

  // O que falta, na ordem da tela. O primeiro item recebe o foco quando se
  // tenta protocolar; a barra de ações mostra o resumo o tempo todo.
  const faltando: { rotulo: string; campoId: string }[] = [
    ...(form.id_especie_documental === "" ? [{ rotulo: "Espécie", campoId: "especie-0" }] : []),
    ...(form.id_manifestante === "" ? [{ rotulo: "Manifestante", campoId: "manifestante-cb" }] : []),
    ...(form.id_assunto === "" ? [{ rotulo: "Assunto", campoId: "assunto-cb" }] : []),
    ...(form.id_unidade_proprietaria === ""
      ? [{ rotulo: "Unidade proprietária", campoId: "unidade-cb" }]
      : []),
  ];
  // Erro sob o campo só depois da primeira tentativa de protocolar.
  const falta = (campoId: string) =>
    tentouEnviar && faltando.some((f) => f.campoId === campoId);

  const submitM = useMutation({
    mutationFn: () =>
      protocoloApi.protocolarBalcao({
        id_especie_documental: Number(form.id_especie_documental),
        id_manifestante: Number(form.id_manifestante),
        id_assunto: Number(form.id_assunto),
        id_unidade_proprietaria: Number(form.id_unidade_proprietaria),
        id_ccd_classe: form.id_ccd_classe ? Number(form.id_ccd_classe) : null,
        numero_origem: form.numero_origem || null,
        observacao: form.observacao || null,
        publico: form.publico,
      }),
    onSuccess: (data) => {
      setLastProtocolo(data);
      setRecentes((prev) =>
        gravarRecente(
          {
            id: data.id,
            numero_processo: data.numero_processo,
            manifestante: data.manifestante,
            especie_documental: data.especie_documental,
            data_recepcao: data.data_recepcao,
          },
          prev,
        ),
      );
      toast.success(`Protocolado: ${data.numero_processo}`);
      setErr(null);
    },
    onError: (e: Error) => {
      setErr(e.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  function submit(e?: React.FormEvent) {
    e?.preventDefault();
    setErr(null);
    setTentouEnviar(true);
    if (faltando.length > 0) {
      // Os campos obrigatórios são combos e botões, sem aria-invalid: o foco
      // vai pelo id. Centraliza antes, para não parar sob a barra fixa.
      const el = document.getElementById(faltando[0].campoId);
      el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
      el?.focus({ preventScroll: true });
      return;
    }
    submitM.mutate();
  }

  function novoProtocolo() {
    // Reset apenas campos do processo, mantém unidade default + público
    setForm((f) => ({
      ...f,
      id_especie_documental: "",
      id_manifestante: "",
      id_assunto: "",
      id_ccd_classe: "",
      numero_origem: "",
      observacao: "",
    }));
    setSugestoes([]);
    setLastProtocolo(null);
    setErr(null);
    setTentouEnviar(false);
    // Foca o manifestante: no balcão, é quem está na frente do atendente.
    requestAnimationFrame(() => {
      document.getElementById("manifestante-cb")?.focus();
    });
  }

  // Ctrl+Enter atalho para protocolar
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter" && !submitM.isPending) {
        e.preventDefault();
        if (lastProtocolo) novoProtocolo();
        else submit();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [submitM.isPending, lastProtocolo, form]);

  const minhaUnidadeId = user?.id_unidade_trabalho ?? null;
  const minhaUnidadeNome =
    minhaUnidadeId == null
      ? null
      : (user?.lotacoes?.find((l) => l.id === minhaUnidadeId)?.nome ?? null);
  const usandoMinhaUnidade =
    minhaUnidadeId != null && form.id_unidade_proprietaria === minhaUnidadeId;

  const resumo = resumoDoQueFalta([{ id: "balcao", titulo: "Balcão", faltando }]);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Inbox}
        title="Balcão de protocolo"
        description="Registre o documento recebido no balcão, por mensageiro ou ofício. O número oficial sai na hora."
      />

      {err && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-foreground"
        >
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{err}</span>
        </div>
      )}

      {lastProtocolo ? (
        <SuccessCard
          protocolo={lastProtocolo}
          onNext={novoProtocolo}
        />
      ) : (
        <form
          onSubmit={submit}
          noValidate
          className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]"
        >
          <div className="min-w-0 space-y-4">
            <SectionCard
              id="balcao-documento"
              step={1}
              icon={FileText}
              title="Documento recebido"
              description="O que chegou ao balcão."
            >
              {/* Espécies são poucas mas variam por prefeitura: ficam todas à
                  vista (um clique), como botões de escolha única. */}
              <fieldset aria-describedby={falta("especie-0") ? "especie-erro" : undefined}>
                <legend className="mb-1.5 text-sm font-medium text-foreground">
                  Espécie
                  <span className="ml-0.5 text-danger" aria-hidden="true">
                    *
                  </span>
                </legend>
                <div className="flex flex-wrap gap-2">
                  {especiesQ.isLoading && (
                    <Carregando className="text-sm text-foreground-muted" />
                  )}
                  {especies.map((esp, i) => {
                    const isSelected = form.id_especie_documental === esp.id;
                    return (
                      <button
                        key={esp.id}
                        id={i === 0 ? "especie-0" : undefined}
                        type="button"
                        aria-pressed={isSelected}
                        onClick={() =>
                          setForm({ ...form, id_especie_documental: esp.id })
                        }
                        className={cn(
                          "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors duration-fast focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                          isSelected
                            ? "border-brand bg-brand/10 font-medium text-brand"
                            : "border-border bg-surface-1 text-foreground hover:border-border-strong hover:bg-surface-2",
                        )}
                      >
                        {isSelected && <Check className="h-3.5 w-3.5" aria-hidden="true" />}
                        {esp.nome}
                      </button>
                    );
                  })}
                </div>
                {falta("especie-0") && (
                  <p
                    id="especie-erro"
                    className="mt-1.5 flex items-start gap-1 text-xs font-medium text-danger-soft-foreground"
                  >
                    <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    Escolha a espécie do documento (ofício, requerimento…).
                  </p>
                )}
              </fieldset>

              <FormField
                label="Número de origem"
                opcional
                hint="O número que veio no documento, se houver."
              >
                <CampoComUnidade
                  id="numero-origem"
                  prefixo="Nº"
                  value={form.numero_origem}
                  onChange={(e) =>
                    setForm({ ...form, numero_origem: e.target.value })
                  }
                  placeholder="Ex.: Ofício 123/2026"
                />
              </FormField>
            </SectionCard>

            <SectionCard
              id="balcao-pedido"
              step={2}
              icon={User}
              title="Quem pede e o quê"
              description="Manifestante, assunto e a unidade que vai cuidar do processo."
            >
              <FormField
                label="Manifestante"
                required
                hint="Busque pelo nome, CPF ou CNPJ."
                error={
                  falta("manifestante-cb")
                    ? "Escolha o manifestante. Sem cadastro? Use “Cadastrar novo”."
                    : undefined
                }
                acao={
                  <Link
                    href="/m/protocolo/manifestantes"
                    className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
                  >
                    <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                    Cadastrar novo
                  </Link>
                }
              >
                <Combobox
                  id="manifestante-cb"
                  options={manifestanteBusca.options}
                  selectedOption={manifestanteBusca.selectedOption}
                  onQueryChange={manifestanteBusca.onQueryChange}
                  value={form.id_manifestante || null}
                  onChange={(v) =>
                    setForm({
                      ...form,
                      id_manifestante: typeof v === "number" ? v : "",
                    })
                  }
                  placeholder="Buscar manifestante…"
                  searchPlaceholder="Nome, CPF ou CNPJ…"
                  loading={manifestanteBusca.loading}
                  footer={
                    <Link
                      href="/m/protocolo/manifestantes"
                      className="inline-flex items-center gap-1 text-primary hover:underline"
                    >
                      <Plus className="h-3.5 w-3.5" aria-hidden="true" />
                      Cadastrar novo manifestante
                    </Link>
                  }
                />
              </FormField>

              <FormField
                label="Assunto"
                required
                error={falta("assunto-cb") ? "Escolha o assunto do documento." : undefined}
              >
                <Combobox
                  id="assunto-cb"
                  options={assuntoOptions}
                  value={form.id_assunto || null}
                  onChange={(v) =>
                    setForm({
                      ...form,
                      id_assunto: typeof v === "number" ? v : "",
                    })
                  }
                  placeholder="Buscar assunto…"
                  searchPlaceholder="Buscar assunto…"
                  loading={assuntosQ.isLoading}
                />
              </FormField>

              <div>
                <FormField
                  label="Classe CCD"
                  opcional
                  hint="Recomendado: a classe define o prazo de guarda do documento."
                >
                  <Combobox
                    id="ccd-cb"
                    options={ccdOptions}
                    value={form.id_ccd_classe || null}
                    onChange={(v) =>
                      setForm({
                        ...form,
                        id_ccd_classe: typeof v === "number" ? v : "",
                      })
                    }
                    placeholder="Buscar classe pelo código ou nome…"
                    searchPlaceholder="Código ou nome…"
                    loading={ccdTreeQ.isLoading}
                  />
                </FormField>
                {!form.id_ccd_classe && (loadingSugestoes || sugestoes.length > 0) && (
                  <div className="mt-2 space-y-1.5">
                    <p className="text-xs text-foreground-muted">
                      {loadingSugestoes
                        ? "Buscando sugestões…"
                        : "Sugestões para este assunto (um clique escolhe):"}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {sugestoes.map((s) => (
                        <button
                          key={s.id_ccd_classe}
                          type="button"
                          onClick={() =>
                            setForm({ ...form, id_ccd_classe: s.id_ccd_classe })
                          }
                          className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-brand/30 bg-brand/5 px-2.5 py-1 text-xs text-brand transition-colors duration-fast hover:bg-brand/10"
                          title={`Aderência: ${(s.score * 100).toFixed(0)}% · palavras em comum: ${s.matched_keywords.join(", ")}`}
                        >
                          <span className="font-mono font-semibold">{s.codigo}</span>
                          <span className="truncate">{s.nome}</span>
                          <span className="text-[10px] tabular-nums text-foreground-muted">
                            {(s.score * 100).toFixed(0)}%
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <FormField
                label="Unidade proprietária"
                required
                hint={
                  usandoMinhaUnidade
                    ? `Preenchida com a sua unidade${minhaUnidadeNome ? ` (${minhaUnidadeNome})` : ""}. Troque se o documento for de outra.`
                    : "A unidade responsável pelo processo. Busque pelo nome ou pela sigla."
                }
                error={
                  falta("unidade-cb")
                    ? "Escolha a unidade responsável pelo processo."
                    : undefined
                }
                acao={
                  minhaUnidadeId != null && !usandoMinhaUnidade ? (
                    <button
                      type="button"
                      title={minhaUnidadeNome ?? undefined}
                      onClick={() =>
                        setForm({ ...form, id_unidade_proprietaria: minhaUnidadeId })
                      }
                      className="font-medium text-primary hover:underline"
                    >
                      Usar a minha unidade
                    </button>
                  ) : undefined
                }
              >
                <UnidadePicker
                  id="unidade-cb"
                  value={
                    typeof form.id_unidade_proprietaria === "number"
                      ? form.id_unidade_proprietaria
                      : null
                  }
                  onChange={(v) =>
                    setForm({ ...form, id_unidade_proprietaria: v ?? "" })
                  }
                  placeholder="Buscar unidade…"
                />
              </FormField>

              <FormField
                label="Observação"
                opcional
                hint="Aparece nas listagens e nas buscas."
              >
                <Textarea
                  id="observacao"
                  value={form.observacao}
                  onChange={(e) =>
                    setForm({ ...form, observacao: e.target.value })
                  }
                  placeholder="Ex.: Entregue pelo próprio requerente; pede retorno por telefone."
                  rows={3}
                />
              </FormField>

              {/* Ligar/desligar: checkbox, com o padrão (público) dito no texto. */}
              <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast hover:bg-surface-2">
                <input
                  type="checkbox"
                  checked={!form.publico}
                  onChange={(e) =>
                    setForm({ ...form, publico: !e.target.checked })
                  }
                  className="mt-0.5 h-4 w-4 accent-brand"
                />
                <span className="flex-1 text-sm">
                  <span className="flex items-center gap-2 font-medium text-foreground">
                    <Lock className="h-3.5 w-3.5" aria-hidden="true" />
                    Sigiloso
                  </span>
                  <span className="block text-xs text-foreground-muted">
                    Marque se o conteúdo é restrito (LGPD, sigilo profissional).
                    Sem marcar, o processo é público.
                  </span>
                </span>
              </label>
            </SectionCard>

            {/* O botão nunca fica desabilitado por validação: clicar (ou
                Ctrl+Enter) é o que mostra, sob cada campo, o que falta. */}
            <BarraAcoesFormulario
              status={
                <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  {resumo ? (
                    <span
                      className={
                        tentouEnviar ? "font-medium text-warning-soft-foreground" : undefined
                      }
                    >
                      {resumo}
                    </span>
                  ) : (
                    <span>Tudo pronto.</span>
                  )}
                  <span>
                    <Tecla>Ctrl + Enter</Tecla> protocola
                  </span>
                </span>
              }
            >
              <Button type="submit" loading={submitM.isPending} className="min-w-44">
                {!submitM.isPending && <Receipt className="h-4 w-4" aria-hidden="true" />}
                {submitM.isPending ? "Protocolando…" : "Protocolar"}
              </Button>
            </BarraAcoesFormulario>
          </div>

          <aside className="space-y-4 lg:sticky lg:top-24">
            <div className="rounded-card border border-border bg-card p-4 shadow-card">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Clock className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
                Protocolos recentes
              </div>
              {recentes.length === 0 ? (
                <p className="text-xs text-foreground-muted">
                  Os últimos {HISTORY_MAX} protocolos feitos neste navegador aparecem aqui.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {recentes.map((r) => (
                    <li
                      key={r.id}
                      className="rounded-md border border-border bg-surface-1 px-2.5 py-1.5"
                    >
                      <Link
                        href={`/m/protocolo/processos/${r.id}`}
                        className="group flex items-center justify-between gap-2 text-xs"
                      >
                        <span className="min-w-0 flex-1 truncate">
                          <span className="font-mono font-semibold text-primary group-hover:underline">
                            {r.numero_processo}
                          </span>
                          <span className="ml-1.5 text-foreground-muted">
                            {r.especie_documental ?? "—"} ·{" "}
                            {r.manifestante.slice(0, 28)}
                          </span>
                        </span>
                        <span className="shrink-0 tabular-nums text-foreground-muted">
                          {fmtHora(r.data_recepcao)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-card border border-border bg-card p-4 text-xs text-foreground-muted shadow-card">
              <div className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-foreground">
                <Keyboard className="h-4 w-4 text-foreground-muted" aria-hidden="true" />
                Atalhos
              </div>
              <ul className="space-y-1.5">
                <li>
                  <Tecla>Ctrl + Enter</Tecla> protocola (e, depois, começa o próximo)
                </li>
                <li>
                  <Tecla>Tab</Tecla> vai para o próximo campo
                </li>
                <li>
                  <Tecla>Esc</Tecla> fecha a lista aberta
                </li>
              </ul>
            </div>
          </aside>
        </form>
      )}
    </div>
  );
}

function SuccessCard({
  protocolo,
  onNext,
}: {
  protocolo: ProtocoloBalcaoResult;
  onNext: () => void;
}) {
  return (
    <div className="rounded-card border border-success/30 bg-success-soft p-6 shadow-card">
      <div className="flex items-start gap-3">
        <span
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-success text-success-foreground"
          aria-hidden="true"
        >
          <CheckCircle2 className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-success-soft-foreground">
            Protocolado{protocolo.nup ? " (NUP federal)" : ""}
          </p>
          <h2 className="mt-1 font-mono text-2xl font-bold tracking-tight text-foreground">
            {protocolo.nup ?? protocolo.numero_processo}
          </h2>
          {protocolo.nup && (
            <p className="mt-0.5 font-mono text-xs text-foreground-muted">
              Legado: {protocolo.numero_processo}
            </p>
          )}
          <p className="mt-1 text-sm text-foreground-muted">
            {protocolo.especie_documental ?? "Espécie não informada"} ·{" "}
            {protocolo.manifestante}
          </p>
          <p className="mt-0.5 text-xs text-foreground-muted">
            {protocolo.assunto} → {protocolo.unidade_proprietaria}
          </p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={onNext} className="min-w-44">
          <Plus className="h-4 w-4" aria-hidden="true" />
          Protocolar próximo
        </Button>
        <Button asChild variant="secondary">
          <a
            href={protocoloEtiquetaPdfUrl(protocolo.id)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Tag className="h-4 w-4" aria-hidden="true" />
            Etiqueta
          </a>
        </Button>
        <Button asChild variant="secondary">
          <a
            href={protocoloComprovantePdfUrl(protocolo.id)}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Printer className="h-4 w-4" aria-hidden="true" />
            Comprovante (2 vias)
          </a>
        </Button>
        <Button asChild variant="secondary">
          <Link href={`/m/protocolo/processos/${protocolo.id}`}>
            Ver processo
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>

      <p className="mt-4 text-xs text-foreground-muted">
        <Tecla>Ctrl + Enter</Tecla> começa o próximo · etiqueta e comprovante abrem em nova aba.
      </p>
    </div>
  );
}

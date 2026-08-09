"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Building2,
  CheckCircle2,
  FilePlus2,
  Globe,
  Hash,
  Info,
  LayoutTemplate,
  Loader2,
  Lock,
  Mail,
  Tag,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { useConfirm } from "@/components/ui/confirm";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import { SectionCard } from "@/components/ui/section-card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import { api, organogramaApi, type ProcessoCreateInput } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

/** Espelha o regex de `backend/app/services/placeholders.py::resolve()`. */
const TOKEN_RE = /\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}/g;

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

/**
 * Resolve só os placeholders já conhecidos ANTES do processo existir
 * (requerente, assunto, unidade, data, usuário). `{{processo.numero}}`,
 * `{{processo.data_abertura}}` e `{{servico.nome}}` ficam literais — não há
 * como saber o número (gerado pelo banco) nem o serviço (fluxo manual, não
 * originado do portal) neste ponto.
 */
function resolvePlaceholdersParcial(corpoHtml: string, contexto: Record<string, string>): string {
  return corpoHtml.replace(TOKEN_RE, (match, chave: string) =>
    chave in contexto ? escapeHtml(contexto[chave]) : match,
  );
}

type FormState = {
  id_tipo_processo: number | "";
  id_assunto: number | "";
  id_manifestante: number | "";
  id_unidade_proprietaria: number | "";
  observacao: string;
  corpo: string;
  numero_origem: string;
  publico: boolean;
  externo: boolean;
  canal_entrada: "interno" | "email";
};

const DRAFT_KEY = "aprimora.novo-processo.draft.v1";

function ToggleCard({
  checked,
  onChange,
  icon: Icon,
  title,
  description,
  iconBgClass,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  iconBgClass: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        "group flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-all duration-fast",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        checked
          ? "border-brand/40 bg-brand/5 shadow-xs"
          : "border-border bg-surface-1 hover:border-border-strong hover:bg-surface-2",
      )}
    >
      <span
        className={cn(
          "inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md transition-colors",
          checked ? iconBgClass : "bg-surface-3 text-foreground-muted",
        )}
        aria-hidden="true"
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-foreground">{title}</span>
          <span
            className={cn(
              "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors",
              checked ? "bg-brand" : "bg-border",
            )}
          >
            <span
              className={cn(
                "inline-block h-4 w-4 rounded-full bg-white shadow-sm transition-transform",
                checked ? "translate-x-4" : "translate-x-0.5",
              )}
            />
          </span>
        </div>
        <p className="mt-0.5 text-xs text-foreground-muted">{description}</p>
      </div>
    </button>
  );
}

export default function NovoProcessoPage() {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const { user } = useAuth();

  const [form, setForm] = useState<FormState>({
    id_tipo_processo: "",
    id_assunto: "",
    id_manifestante: "",
    id_unidade_proprietaria: user?.id_unidade_trabalho ?? "",
    observacao: "",
    corpo: "",
    numero_origem: "",
    publico: true,
    externo: false,
    canal_entrada: "interno",
  });
  const [err, setErr] = useState<string | null>(null);
  const [draftHydrated, setDraftHydrated] = useState(false);

  // Hydrate from localStorage draft once on mount
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(DRAFT_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<FormState>;
        setForm((f) => ({ ...f, ...parsed }));
      }
    } catch {
      // ignore corrupted drafts
    }
    setDraftHydrated(true);
  }, []);

  // Persist draft (debounced)
  useEffect(() => {
    if (!draftHydrated) return;
    const t = setTimeout(() => {
      try {
        window.localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
      } catch {
        // localStorage may be unavailable
      }
    }, 400);
    return () => clearTimeout(t);
  }, [form, draftHydrated]);

  const tiposProcessoQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });
  const assuntosQ = useQuery({
    queryKey: ["assuntos-all"],
    queryFn: () => api.assuntos.list({ page_size: 500 }),
  });
  const manifestantesQ = useQuery({
    queryKey: ["manifestantes-all"],
    queryFn: () => api.manifestantes.list({ page_size: 500 }),
  });
  const templatesQ = useQuery({
    queryKey: ["templates-documento", "ativos"],
    queryFn: () => api.templatesDocumento.list({ apenas_ativos: true }),
  });
  // Mesma queryKey do UnidadePicker — reaproveita o cache se ele já buscou.
  const organogramaQ = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
  });

  const tipoOptions = useMemo<ComboboxOption<{ id: number }>[]>(() => {
    return (tiposProcessoQ.data ?? []).map((t) => ({
      value: t.id,
      label: t.tipo_processo,
    }));
  }, [tiposProcessoQ.data]);

  const manifestanteOptions = useMemo<ComboboxOption[]>(() => {
    return (manifestantesQ.data?.items ?? []).map((m) => ({
      value: m.id,
      label: m.nome ?? "(sem nome)",
      hint: m.cpf_cnpj ?? undefined,
    }));
  }, [manifestantesQ.data]);

  const assuntoOptions = useMemo<ComboboxOption<{ id_tipo_processo: number }>[]>(() => {
    const all = assuntosQ.data?.items ?? [];
    const filtered = form.id_tipo_processo
      ? all.filter((a) => a.id_tipo_processo === form.id_tipo_processo)
      : all;
    return filtered.map((a) => ({
      value: a.id,
      label: a.assunto,
      data: { id_tipo_processo: a.id_tipo_processo },
    }));
  }, [assuntosQ.data, form.id_tipo_processo]);

  function handleTipoChange(v: number | string | null) {
    const id = typeof v === "number" ? v : "";
    // Clear assunto if it doesn't belong to this tipo
    const currentAssunto = assuntosQ.data?.items.find((a) => a.id === form.id_assunto);
    const keepAssunto =
      currentAssunto && (id === "" || currentAssunto.id_tipo_processo === id);
    setForm({ ...form, id_tipo_processo: id, id_assunto: keepAssunto ? form.id_assunto : "" });
  }

  const templateOptions = useMemo<ComboboxOption[]>(() => {
    return (templatesQ.data ?? []).map((t) => ({
      value: t.id,
      label: t.nome,
      hint: t.categoria ?? undefined,
    }));
  }, [templatesQ.data]);

  const [templateSelecionado, setTemplateSelecionado] = useState<number | "">("");

  async function aplicarTemplate(templateId: number) {
    const template = templatesQ.data?.find((t) => t.id === templateId);
    if (!template) return;

    if (form.corpo.trim()) {
      const ok = await confirm({
        title: "Substituir o conteúdo?",
        message: `O texto atual do corpo será substituído pelo modelo "${template.nome}".`,
        confirmLabel: "Substituir",
      });
      if (!ok) {
        setTemplateSelecionado("");
        return;
      }
    }

    const manifestante = manifestantesQ.data?.items.find((m) => m.id === form.id_manifestante);
    const assunto = assuntosQ.data?.items.find((a) => a.id === form.id_assunto);
    const unidade = organogramaQ.data?.find((u) => u.id === form.id_unidade_proprietaria);

    const contexto: Record<string, string> = {
      "requerente.nome": manifestante?.nome ?? "",
      "requerente.cpf_cnpj": manifestante?.cpf_cnpj ?? "",
      "requerente.email": manifestante?.email ?? "",
      "requerente.telefone":
        manifestante?.telefone_celular ||
        manifestante?.telefone_residencial ||
        manifestante?.telefone_comercial ||
        "",
      "processo.assunto": assunto?.assunto ?? "",
      "processo.observacao": form.observacao,
      "unidade.nome": unidade?.unidade_trabalho ?? "",
      "unidade.sigla": unidade?.sigla ?? "",
      "data_hoje": new Date().toLocaleDateString("pt-BR"),
      "usuario.nome": user?.nome ?? "",
    };

    setForm({ ...form, corpo: resolvePlaceholdersParcial(template.corpo_html, contexto) });
    setTemplateSelecionado("");
    toast.info(`Modelo "${template.nome}" carregado.`);
  }

  const createM = useMutation({
    mutationFn: (data: ProcessoCreateInput) => api.processos.create(data),
    onSuccess: (p) => {
      try {
        window.localStorage.removeItem(DRAFT_KEY);
      } catch {
        // ignore
      }
      toast.success(`Processo ${p.numero_processo} criado.`);
      router.push(`/m/protocolo/processos/${p.id}`);
    },
    onError: (e: Error) => {
      setErr(e.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!form.id_assunto || !form.id_manifestante || !form.id_unidade_proprietaria) {
      setErr("Preencha manifestante, assunto e unidade proprietária.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    createM.mutate({
      id_assunto: Number(form.id_assunto),
      id_manifestante: Number(form.id_manifestante),
      id_unidade_proprietaria: Number(form.id_unidade_proprietaria),
      observacao: form.observacao || null,
      corpo: form.corpo || null,
      numero_origem: form.numero_origem || null,
      publico: form.publico,
      externo: form.externo,
      canal_entrada: form.canal_entrada,
      virtual: true,
    });
  }

  function descartarRascunho() {
    try {
      window.localStorage.removeItem(DRAFT_KEY);
    } catch {
      // ignore
    }
    setForm({
      id_tipo_processo: "",
      id_assunto: "",
      id_manifestante: "",
      id_unidade_proprietaria: user?.id_unidade_trabalho ?? "",
      observacao: "",
      corpo: "",
      numero_origem: "",
      publico: true,
      externo: false,
      canal_entrada: "interno",
    });
    setErr(null);
    toast.info("Rascunho descartado.");
  }

  const hasDraft =
    draftHydrated &&
    (form.id_assunto !== "" ||
      form.id_manifestante !== "" ||
      form.observacao !== "" ||
      form.corpo !== "" ||
      form.numero_origem !== "");

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader
        variant="hero"
        icon={FilePlus2}
        breadcrumbs={[
          { label: "Processos", href: "/m/protocolo/processos" },
          { label: "Novo" },
        ]}
        title="Abrir novo processo"
        description="O número definitivo será gerado automaticamente ao salvar. Suas alterações ficam em rascunho local enquanto você preenche."
        actions={
          hasDraft && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={descartarRascunho}
              title="Limpa todos os campos e remove o rascunho salvo no navegador"
            >
              Descartar rascunho
            </Button>
          )
        }
      />

      {err && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-foreground"
        >
          <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{err}</span>
        </div>
      )}

      <form onSubmit={submit} className="space-y-4" noValidate>
        {/* === Passo 1: Identificação === */}
        <SectionCard
          step={1}
          icon={Users}
          title="Identificação"
          description="Quem está abrindo o processo e onde ele vai tramitar."
        >
          <div>
            <Label htmlFor="manif" required>
              Manifestante
            </Label>
            <Combobox
              id="manif"
              options={manifestanteOptions}
              value={form.id_manifestante === "" ? null : form.id_manifestante}
              onChange={(v) =>
                setForm({ ...form, id_manifestante: typeof v === "number" ? v : "" })
              }
              placeholder="Buscar por nome ou CPF/CNPJ…"
              searchPlaceholder="Nome, CPF ou CNPJ…"
              loading={manifestantesQ.isLoading}
              footer={
                <Link
                  href="/cadastros/manifestantes/novo"
                  className="inline-flex items-center gap-1 text-brand hover:underline"
                >
                  <span aria-hidden="true">+</span> Cadastrar novo manifestante
                </Link>
              }
            />
          </div>

          <p className="flex items-start gap-1.5 text-xs text-foreground-subtle">
            <Lock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
            Manifestante e assunto não podem ser alterados depois que o processo for aberto.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label htmlFor="tipo">Tipo de processo</Label>
              <Combobox
                id="tipo"
                options={tipoOptions}
                value={form.id_tipo_processo === "" ? null : form.id_tipo_processo}
                onChange={handleTipoChange}
                placeholder="(todos)"
                searchPlaceholder="Buscar tipo…"
                emptyText="Nenhum tipo de processo."
                loading={tiposProcessoQ.isLoading}
              />
              <p className="mt-1 text-xs text-foreground-subtle">
                Opcional. Filtra a lista de assuntos abaixo.
              </p>
            </div>

            <div>
              <Label htmlFor="assunto" required>
                Assunto
              </Label>
              <Combobox
                id="assunto"
                options={assuntoOptions}
                value={form.id_assunto === "" ? null : form.id_assunto}
                onChange={(v) =>
                  setForm({ ...form, id_assunto: typeof v === "number" ? v : "" })
                }
                placeholder="Buscar assunto…"
                searchPlaceholder="Buscar assunto…"
                emptyText={
                  form.id_tipo_processo
                    ? "Nenhum assunto neste tipo."
                    : "Nenhum assunto cadastrado."
                }
                loading={assuntosQ.isLoading}
              />
            </div>
          </div>

          <div>
            <Label required>Unidade proprietária</Label>
            <UnidadePicker
              value={
                form.id_unidade_proprietaria === ""
                  ? null
                  : form.id_unidade_proprietaria
              }
              onChange={(v) =>
                setForm({ ...form, id_unidade_proprietaria: v ?? "" })
              }
              placeholder="Escolher unidade proprietária no organograma"
            />
            <p className="mt-1 text-xs text-foreground-subtle">
              Sugerida: sua unidade
              {user?.id_unidade_trabalho ? ` (#${user.id_unidade_trabalho})` : ""}.
            </p>
          </div>
        </SectionCard>

        {/* === Passo 2: Conteúdo === */}
        <SectionCard
          step={2}
          icon={Tag}
          title="Conteúdo"
          description="Descrição breve e corpo completo do processo."
        >
          <div>
            <Label htmlFor="obs">Observação</Label>
            <Textarea
              id="obs"
              value={form.observacao}
              onChange={(e) => setForm({ ...form, observacao: e.target.value })}
              rows={2}
              placeholder="Resumo curto que aparece nas listagens (uma linha basta)."
            />
            <p className="mt-1 text-xs text-foreground-subtle">
              Texto simples. Usado em buscas e listagens.
            </p>
          </div>

          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <Label htmlFor="corpo">Corpo do processo</Label>
              {templateOptions.length > 0 && (
                <div className="flex w-64 items-center gap-1.5">
                  <LayoutTemplate
                    className="h-4 w-4 shrink-0 text-foreground-subtle"
                    aria-hidden="true"
                  />
                  <Combobox
                    options={templateOptions}
                    value={templateSelecionado === "" ? null : templateSelecionado}
                    onChange={(v) => {
                      if (typeof v === "number") {
                        setTemplateSelecionado(v);
                        void aplicarTemplate(v);
                      }
                    }}
                    placeholder="Carregar de um modelo…"
                    searchPlaceholder="Buscar modelo…"
                    loading={templatesQ.isLoading}
                  />
                </div>
              )}
            </div>
            <RichTextEditor
              ariaLabel="Corpo do processo"
              value={form.corpo}
              onChange={(html) => setForm({ ...form, corpo: html })}
              placeholder="Descreva o pedido com detalhes. Use Ctrl+B / Ctrl+I, listas, títulos…"
              minHeight={200}
              onUploadImage={async (file) => {
                const { url } = await api.editorImagens.upload(file);
                return url;
              }}
            />
            <p className="mt-1 text-xs text-foreground-subtle">
              Texto formatado. Aparece no PDF e na ficha do processo.
            </p>
          </div>
        </SectionCard>

        {/* === Passo 3: Configurações === */}
        <SectionCard
          step={3}
          icon={Hash}
          title="Configurações"
          description="Visibilidade, origem externa e número de protocolo prévio."
        >
          <div>
            <Label htmlFor="origem">
              Número de origem
              <span className="ml-1 font-normal text-foreground-subtle">(opcional)</span>
            </Label>
            <Input
              id="origem"
              value={form.numero_origem}
              onChange={(e) => setForm({ ...form, numero_origem: e.target.value })}
              placeholder="Ex: protocolo externo, ofício, número de outro sistema"
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <ToggleCard
              checked={form.publico}
              onChange={(v) => setForm({ ...form, publico: v })}
              icon={form.publico ? Globe : Lock}
              iconBgClass="bg-success-soft text-success"
              title={form.publico ? "Público" : "Sigiloso"}
              description={
                form.publico
                  ? "Qualquer servidor pode visualizar este processo."
                  : "Apenas usuários autorizados poderão ver. Audit log marcará acessos."
              }
            />
            <ToggleCard
              checked={form.externo}
              onChange={(v) => setForm({ ...form, externo: v })}
              icon={Users}
              iconBgClass="bg-info-soft text-info"
              title={form.externo ? "Origem externa" : "Origem interna"}
              description={
                form.externo
                  ? "Processo iniciado por cidadão ou orgão externo."
                  : "Processo aberto por servidor interno da prefeitura."
              }
            />
            <ToggleCard
              checked={form.canal_entrada === "email"}
              onChange={(v) =>
                setForm({ ...form, canal_entrada: v ? "email" : "interno" })
              }
              icon={form.canal_entrada === "email" ? Mail : Building2}
              iconBgClass="bg-brand/10 text-brand"
              title={form.canal_entrada === "email" ? "Recebido por e-mail" : "Registrado internamente"}
              description={
                form.canal_entrada === "email"
                  ? "Documento chegou por e-mail e está sendo protocolado agora."
                  : "Não veio de balcão, portal do cidadão nem e-mail."
              }
            />
          </div>
        </SectionCard>

        {/* === Sticky footer com ações === */}
        <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface-1/95 px-4 py-3 backdrop-blur-md sm:mx-0 sm:rounded-xl sm:border">
          <span className="text-xs text-foreground-subtle">
            {hasDraft ? (
              <span className="inline-flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-success" aria-hidden="true" />
                Rascunho salvo automaticamente.
              </span>
            ) : (
              "Preencha os campos obrigatórios para abrir o processo."
            )}
          </span>
          <div className="flex flex-wrap gap-2">
            <Link href="/m/protocolo/processos">
              <Button variant="ghost" type="button">
                Cancelar
              </Button>
            </Link>
            <Button type="submit" disabled={createM.isPending} size="md">
              {createM.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Abrindo…
                </>
              ) : (
                <>
                  Abrir processo
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </>
              )}
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}

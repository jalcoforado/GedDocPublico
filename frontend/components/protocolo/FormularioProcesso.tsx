"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
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
import { useEffect, useMemo, useRef, useState } from "react";

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
import {
  api,
  organogramaApi,
  type ProcessoCreateInput,
  type ProcessoDetail,
  type RascunhoUpdateInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useAssuntosAll } from "@/lib/assuntos";
import { useManifestantesBusca } from "@/lib/manifestantes";
import { telefoneParaExibir } from "@/lib/mascaras";

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

interface OpcaoConfig<V extends string> {
  valor: V;
  rotulo: string;
  descricao: string;
  icon: React.ComponentType<{ className?: string }>;
}

/**
 * Escolha entre dois valores com título fixo e as duas opções à vista.
 *
 * Substitui o interruptor (ToggleCard), cujo título trocava com o estado:
 * desligado, ele mostrava "Sigiloso" ou "Origem interna" com a chave
 * apagada — lido como "não sigiloso", "não interna", o oposto do gravado.
 * Interruptor é para ligar/desligar; escolher entre dois valores pede as
 * duas opções nomeadas. Por baixo são `<input type="radio">` nativos: setas,
 * Tab e leitor de tela funcionam sem código próprio.
 */
function EscolhaConfig<V extends string>({
  nome,
  titulo,
  valor,
  opcoes,
  onChange,
}: {
  nome: string;
  titulo: string;
  valor: V;
  opcoes: [OpcaoConfig<V>, OpcaoConfig<V>];
  onChange: (v: V) => void;
}) {
  const atual = opcoes.find((o) => o.valor === valor) ?? opcoes[0];
  return (
    <fieldset className="rounded-lg border border-border bg-surface-1 p-3">
      <legend className="sr-only">{titulo}</legend>
      <div aria-hidden="true" className="mb-2 text-sm font-medium text-foreground">
        {titulo}
      </div>
      <div className="grid grid-cols-2 gap-1 rounded-md bg-surface-2 p-1">
        {opcoes.map((o) => {
          const marcada = o.valor === valor;
          const Icon = o.icon;
          return (
            <label
              key={o.valor}
              className={cn(
                // `relative` prende o rádio `sr-only` (absoluto) dentro da
                // opção. Sem ele o rádio ficava ancorado longe, e o foco do
                // clique rolava a página até lá.
                "relative flex cursor-pointer items-center justify-center gap-1.5 rounded px-2 py-1.5 text-sm transition-colors duration-fast",
                "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                marcada
                  ? "bg-card font-medium text-foreground shadow-xs"
                  : "text-foreground-muted hover:text-foreground",
              )}
            >
              <input
                type="radio"
                name={nome}
                value={o.valor}
                checked={marcada}
                onChange={() => onChange(o.valor)}
                aria-describedby={marcada ? `${nome}-descricao` : undefined}
                className="sr-only"
              />
              <Icon className={cn("h-4 w-4 shrink-0", marcada && "text-brand")} aria-hidden="true" />
              {o.rotulo}
            </label>
          );
        })}
      </div>
      <p id={`${nome}-descricao`} className="mt-2 text-xs text-foreground-muted">
        {atual.descricao}
      </p>
    </fieldset>
  );
}

/** O rascunho, como o formulário o mostra. */
function formDoRascunho(p: ProcessoDetail): FormState {
  return {
    id_tipo_processo: p.id_tipo_processo ?? "",
    id_assunto: p.id_assunto ?? "",
    id_manifestante: p.id_manifestante ?? "",
    id_unidade_proprietaria: p.id_unidade_proprietaria ?? "",
    observacao: p.observacao ?? "",
    corpo: p.corpo ?? "",
    numero_origem: p.numero_origem ?? "",
    publico: p.publico,
    externo: p.externo,
    canal_entrada: p.canal_entrada === "email" ? "email" : "interno",
  };
}

/**
 * Formulário de abertura de processo, e também de edição do rascunho
 * (SI-16): com `rascunhoId`, carrega o rascunho, salva com PUT e oferece
 * "Salvar e abrir processo" no lugar de "Salvar como rascunho".
 *
 * Na edição não há autosave no navegador (`DRAFT_KEY`): o rascunho já está
 * no servidor, e misturar os dois faria o autosave de um processo novo
 * aparecer dentro de outro.
 */
export function FormularioProcesso({ rascunhoId }: { rascunhoId?: number }) {
  const router = useRouter();
  const toast = useToast();
  const confirm = useConfirm();
  const { user } = useAuth();
  const qc = useQueryClient();
  const editando = rascunhoId !== undefined;

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

  // Edição: o rascunho vem do servidor, uma vez só (refetch em foco não pode
  // apagar o que está sendo digitado).
  const rascunhoQ = useQuery({
    queryKey: ["processo", rascunhoId],
    queryFn: () => api.processos.get(rascunhoId as number),
    enabled: editando,
  });
  const [rascunhoCarregado, setRascunhoCarregado] = useState(false);
  useEffect(() => {
    if (!editando || rascunhoCarregado || !rascunhoQ.data) return;
    setForm(formDoRascunho(rascunhoQ.data));
    setRascunhoCarregado(true);
  }, [editando, rascunhoCarregado, rascunhoQ.data]);

  // Hydrate from localStorage draft once on mount
  useEffect(() => {
    if (editando) return;
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
  }, [editando]);

  // Persist draft (debounced)
  useEffect(() => {
    if (editando || !draftHydrated) return;
    const t = setTimeout(() => {
      try {
        window.localStorage.setItem(DRAFT_KEY, JSON.stringify(form));
      } catch {
        // localStorage may be unavailable
      }
    }, 400);
    return () => clearTimeout(t);
  }, [form, draftHydrated, editando]);

  const tiposProcessoQ = useQuery({
    queryKey: ["tipos-processo"],
    queryFn: () => api.tiposProcesso.list(),
  });
  const assuntosQ = useAssuntosAll();
  // Busca no servidor: a lista de manifestantes cresce sem limite e o
  // backend corta em page_size ≤ 200 (pedir 500 dava 422 e combo vazio).
  const manifestanteBusca = useManifestantesBusca(
    form.id_manifestante === "" ? null : form.id_manifestante,
  );
  const templatesQ = useQuery({
    queryKey: ["templates-documento", "ativos"],
    queryFn: () => api.templatesDocumento.list({ apenas_ativos: true }),
  });
  // Mesma queryKey do UnidadePicker (balcão, dashboard) — cache compartilhado.
  const organogramaQ = useQuery({
    queryKey: ["organograma"],
    queryFn: () => organogramaApi.tree(),
  });

  // Unidade proprietária na mesma lista com busca dos campos acima. Era o
  // UnidadePicker (árvore do organograma num modal), que não tinha o X e, por
  // só buscar as unidades ao abrir, mostrava o placeholder mesmo com a
  // unidade sugerida já escolhida.
  const unidadeOptions = useMemo<ComboboxOption[]>(() => {
    return (organogramaQ.data ?? [])
      .map((u) => ({ value: u.id, label: u.unidade_trabalho, hint: u.sigla ?? undefined }))
      .sort((a, b) => a.label.localeCompare(b.label, "pt-BR"));
  }, [organogramaQ.data]);

  const tipoOptions = useMemo<ComboboxOption<{ id: number }>[]>(() => {
    return (tiposProcessoQ.data ?? []).map((t) => ({
      value: t.id,
      label: t.tipo_processo,
    }));
  }, [tiposProcessoQ.data]);

  const assuntoOptions = useMemo<ComboboxOption<{ id_tipo_processo: number }>[]>(() => {
    const all = assuntosQ.data ?? [];
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
    const currentAssunto = assuntosQ.data?.find((a) => a.id === form.id_assunto);
    const keepAssunto =
      currentAssunto && (id === "" || currentAssunto.id_tipo_processo === id);
    setForm({ ...form, id_tipo_processo: id, id_assunto: keepAssunto ? form.id_assunto : "" });
  }

  const templateOptions = useMemo<ComboboxOption[]>(() => {
    return (templatesQ.data ?? []).map((t) => ({
      value: t.id,
      label: t.nome,
      hint: t.descricao ?? undefined,
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

    const manifestante = manifestanteBusca.selecionado;
    const assunto = assuntosQ.data?.find((a) => a.id === form.id_assunto);
    const unidade = organogramaQ.data?.find((u) => u.id === form.id_unidade_proprietaria);

    const contexto: Record<string, string> = {
      "requerente.nome": manifestante?.nome ?? "",
      "requerente.cpf_cnpj": manifestante?.cpf_cnpj ?? "",
      "requerente.email": manifestante?.email ?? "",
      "requerente.telefone": telefoneParaExibir(
        manifestante?.telefone_celular ||
          manifestante?.telefone_residencial ||
          manifestante?.telefone_comercial,
      ),
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

  // Trava contra clique duplo. O `isPending` da mutação só desabilita o botão
  // depois que o React redesenha, e dois cliques rápidos passavam os dois:
  // nasciam dois rascunhos iguais. A trava é síncrona; só o erro a solta (no
  // sucesso a tela navega, e soltar antes abriria a mesma janela de novo).
  const enviando = useRef(false);
  function enviarUmaVez(enviar: () => void) {
    if (enviando.current) return;
    enviando.current = true;
    enviar();
  }

  const createM = useMutation({
    mutationFn: (data: ProcessoCreateInput) => api.processos.create(data),
    onSuccess: (p) => {
      try {
        window.localStorage.removeItem(DRAFT_KEY);
      } catch {
        // ignore
      }
      // As listas (inclusive "Rascunhos") têm de mostrar o processo novo ao voltar.
      qc.invalidateQueries({ queryKey: ["processos"] });
      // E3 — rascunho nasce sem número; a mensagem não pode prometer um.
      toast.success(
        p.numero_processo
          ? `Processo ${p.numero_processo} criado.`
          : "Processo salvo como rascunho — sem número ainda.",
      );
      router.push(`/m/protocolo/processos/${p.id}`);
    },
    onError: (e: Error) => {
      enviando.current = false;
      setErr(e.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });

  // SI-16 — edição do rascunho. "Salvar e abrir" grava antes de abrir: o
  // número tem de nascer para o conteúdo que está na tela.
  const salvarRascunhoM = useMutation({
    mutationFn: async ({ abrir }: { abrir: boolean }) => {
      const id = rascunhoId as number;
      const salvo = await api.processos.editarRascunho(id, montarEdicao());
      return abrir ? api.processos.abrirRascunho(id) : salvo;
    },
    onSuccess: (p) => {
      // A tela do processo lê o cache (staleTime de 30 s), que ainda guarda o
      // rascunho de antes da edição — foi dele que este formulário se
      // preencheu. Grava a resposta do servidor ali, e as listas recarregam.
      qc.setQueryData(["processo", p.id], p);
      qc.invalidateQueries({ queryKey: ["processos"] });
      toast.success(
        p.numero_processo
          ? `Processo ${p.numero_processo} aberto.`
          : "Rascunho salvo. Ele continua sem número até você abri-lo.",
      );
      router.push(`/m/protocolo/processos/${p.id}`);
    },
    onError: (e: Error) => {
      enviando.current = false;
      setErr(e.message);
      window.scrollTo({ top: 0, behavior: "smooth" });
    },
  });
  const salvando = createM.isPending || salvarRascunhoM.isPending;

  function montarEdicao(): RascunhoUpdateInput {
    const { rascunho: _r, virtual: _v, ...edicao } = montarPayload(true);
    return edicao;
  }

  function validar(): boolean {
    if (!form.id_assunto || !form.id_manifestante || !form.id_unidade_proprietaria) {
      setErr("Preencha manifestante, assunto e unidade proprietária.");
      window.scrollTo({ top: 0, behavior: "smooth" });
      return false;
    }
    return true;
  }

  function montarPayload(rascunho: boolean): ProcessoCreateInput {
    return {
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
      rascunho,
    };
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    if (!validar()) return;
    enviarUmaVez(() =>
      editando
        ? salvarRascunhoM.mutate({ abrir: true })
        : createM.mutate(montarPayload(false)),
    );
  }

  // E3 (benchmark SUiTE) — distinto do rascunho LOCAL acima (autosave no
  // navegador, `DRAFT_KEY`): este cria o processo de verdade no backend,
  // só sem número ainda. Ele ganha número em "Abrir processo" (SI-16) ou no
  // primeiro encaminhamento.
  function salvarComoRascunho() {
    setErr(null);
    if (!validar()) return;
    enviarUmaVez(() =>
      editando
        ? salvarRascunhoM.mutate({ abrir: false })
        : createM.mutate(montarPayload(true)),
    );
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
    !editando &&
    draftHydrated &&
    (form.id_assunto !== "" ||
      form.id_manifestante !== "" ||
      form.observacao !== "" ||
      form.corpo !== "" ||
      form.numero_origem !== "");

  if (editando) {
    if (rascunhoQ.isLoading || (rascunhoQ.data && !rascunhoCarregado)) {
      return (
        <p className="mx-auto max-w-3xl py-10 text-center text-sm text-foreground-muted">
          Carregando rascunho…
        </p>
      );
    }
    // Não existe, não é do usuário (o servidor responde 404) ou já foi aberto.
    if (!rascunhoQ.data || rascunhoQ.data.situacao !== "rascunho") {
      return (
        <div className="mx-auto max-w-3xl space-y-3 py-10 text-center">
          <p className="text-sm text-foreground-muted">
            {rascunhoQ.data
              ? "Este processo já foi aberto e tem número: não é mais um rascunho editável."
              : "Rascunho não encontrado. Só quem criou o rascunho pode editá-lo."}
          </p>
          <Button asChild size="sm" variant="secondary">
            <Link
              href={
                rascunhoQ.data
                  ? `/m/protocolo/processos/${rascunhoQ.data.id}`
                  : "/m/protocolo/processos?situacao=rascunho"
              }
            >
              {rascunhoQ.data ? "Ver o processo" : "Ver meus rascunhos"}
            </Link>
          </Button>
        </div>
      );
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader
        variant="hero"
        icon={FilePlus2}
        breadcrumbs={
          editando
            ? [
                { label: "Processos", href: "/m/protocolo/processos" },
                { label: "Rascunho", href: `/m/protocolo/processos/${rascunhoId}` },
                { label: "Editar" },
              ]
            : [
                { label: "Processos", href: "/m/protocolo/processos" },
                { label: "Novo" },
              ]
        }
        title={editando ? "Editar rascunho" : "Abrir novo processo"}
        description={
          editando
            ? "O rascunho continua sem número até você abrir o processo. Só você vê este rascunho."
            : "O número definitivo será gerado automaticamente ao abrir. Suas alterações ficam em rascunho local enquanto você preenche."
        }
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
              options={manifestanteBusca.options}
              selectedOption={manifestanteBusca.selectedOption}
              onQueryChange={manifestanteBusca.onQueryChange}
              value={form.id_manifestante === "" ? null : form.id_manifestante}
              onChange={(v) =>
                setForm({ ...form, id_manifestante: typeof v === "number" ? v : "" })
              }
              placeholder="Buscar por nome ou CPF/CNPJ…"
              searchPlaceholder="Nome, CPF ou CNPJ…"
              loading={manifestanteBusca.loading}
              footer={
                <Link
                  href="/m/protocolo/manifestantes"
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
            <Label htmlFor="unidade" required>
              Unidade proprietária
            </Label>
            <Combobox
              id="unidade"
              options={unidadeOptions}
              value={
                form.id_unidade_proprietaria === ""
                  ? null
                  : form.id_unidade_proprietaria
              }
              onChange={(v) =>
                setForm({ ...form, id_unidade_proprietaria: typeof v === "number" ? v : "" })
              }
              placeholder="Buscar unidade…"
              searchPlaceholder="Nome ou sigla da unidade…"
              emptyText="Nenhuma unidade encontrada."
              loading={organogramaQ.isLoading}
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
          description="Número de origem, visibilidade, origem e canal de entrada."
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
            {/* Rótulos e textos mantidos de propósito (decisão de 2026-11-04):
                hoje `publico=false` grava o nível `interno`
                (services/sigilo.py), que todo servidor alcança pela credencial
                padrão, e nenhum acesso é registrado em auditoria. O
                comportamento do sigilo será ajustado em tarefa própria; ao
                mudá-lo, revisar estes textos. */}
            <EscolhaConfig
              nome="visibilidade"
              titulo="Visibilidade"
              valor={form.publico ? "publico" : "sigiloso"}
              onChange={(v) => setForm({ ...form, publico: v === "publico" })}
              opcoes={[
                {
                  valor: "publico",
                  rotulo: "Público",
                  icon: Globe,
                  descricao: "Qualquer servidor pode visualizar este processo.",
                },
                {
                  valor: "sigiloso",
                  rotulo: "Sigiloso",
                  icon: Lock,
                  descricao: "Apenas usuários autorizados poderão ver. Audit log marcará acessos.",
                },
              ]}
            />
            <EscolhaConfig
              nome="origem-processo"
              titulo="Origem"
              valor={form.externo ? "externa" : "interna"}
              onChange={(v) => setForm({ ...form, externo: v === "externa" })}
              opcoes={[
                {
                  valor: "interna",
                  rotulo: "Interna",
                  icon: Building2,
                  descricao: "Processo aberto por servidor interno da prefeitura.",
                },
                {
                  valor: "externa",
                  rotulo: "Externa",
                  icon: Users,
                  descricao: "Processo iniciado por cidadão ou órgão externo.",
                },
              ]}
            />
            <EscolhaConfig
              nome="canal-entrada"
              titulo="Canal de entrada"
              valor={form.canal_entrada}
              onChange={(v) => setForm({ ...form, canal_entrada: v })}
              opcoes={[
                {
                  valor: "interno",
                  rotulo: "Registro interno",
                  icon: Building2,
                  descricao: "Não veio de balcão, portal do cidadão nem e-mail.",
                },
                {
                  valor: "email",
                  rotulo: "E-mail",
                  icon: Mail,
                  descricao: "Documento chegou por e-mail e está sendo protocolado agora.",
                },
              ]}
            />
          </div>
        </SectionCard>

        {/* === Sticky footer com ações === */}
        <div className="sticky bottom-0 -mx-4 flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface-1/95 px-4 py-3 backdrop-blur-md sm:mx-0 sm:rounded-xl sm:border">
          <span className="text-xs text-foreground-subtle">
            {editando ? (
              "Abrir o processo gera o número. Depois disso, ele não volta a ser rascunho."
            ) : hasDraft ? (
              <span className="inline-flex items-center gap-1">
                <CheckCircle2 className="h-3 w-3 text-success" aria-hidden="true" />
                Rascunho salvo automaticamente.
              </span>
            ) : (
              "Preencha os campos obrigatórios para abrir o processo."
            )}
          </span>
          <div className="flex flex-wrap gap-2">
            <Link
              href={
                editando ? `/m/protocolo/processos/${rascunhoId}` : "/m/protocolo/processos"
              }
            >
              <Button variant="ghost" type="button">
                Cancelar
              </Button>
            </Link>
            <Button
              type="button"
              variant="secondary"
              size="md"
              disabled={salvando}
              onClick={salvarComoRascunho}
              title={
                editando
                  ? "Grava as alterações. O processo continua sem número."
                  : "Cria o processo sem número. Você pode editá-lo depois e abri-lo quando estiver pronto."
              }
            >
              {editando ? "Salvar rascunho" : "Salvar como rascunho"}
            </Button>
            <Button type="submit" disabled={salvando} size="md">
              {salvando ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  Salvando…
                </>
              ) : (
                <>
                  {editando ? "Salvar e abrir processo" : "Abrir processo"}
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

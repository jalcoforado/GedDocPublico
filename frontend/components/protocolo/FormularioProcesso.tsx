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
  Lock,
  Mail,
  Plus,
  Tag,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { PageHeader } from "@/components/ui/page-header";
import { BarraAcoesFormulario } from "@/components/ui/barra-acoes-formulario";
import { Button } from "@/components/ui/button";
import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { useConfirm } from "@/components/ui/confirm";
import { EscolhaSegmentada } from "@/components/ui/escolha-segmentada";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { RichTextEditor } from "@/components/ui/rich-text-editor";
import {
  LayoutFormulario,
  RoteiroFormulario,
  resumoDoQueFalta,
  type EtapaRoteiro,
} from "@/components/ui/roteiro-formulario";
import { SectionCard } from "@/components/ui/section-card";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { UnidadePicker } from "@/components/UnidadePicker";
import {
  api,
  organogramaApi,
  type ProcessoCreateInput,
  type ProcessoDetail,
  type RascunhoUpdateInput,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
  // Mesma queryKey do UnidadePicker (o campo abaixo) — cache compartilhado.
  // Aqui só serve para o resumo mostrar o nome da unidade escolhida.
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

  // O que falta, na ordem dos campos na tela. Alimenta o roteiro, o status da
  // barra de ações e (depois da primeira tentativa de enviar) os erros sob
  // cada campo — uma conta só, para os três nunca discordarem.
  const faltando: EtapaRoteiro["faltando"] = [
    ...(form.id_manifestante === "" ? [{ rotulo: "Manifestante", campoId: "manif" }] : []),
    ...(form.id_assunto === "" ? [{ rotulo: "Assunto", campoId: "assunto" }] : []),
    ...(form.id_unidade_proprietaria === ""
      ? [{ rotulo: "Unidade proprietária", campoId: "unidade" }]
      : []),
  ];
  const etapas: EtapaRoteiro[] = [
    { id: "etapa-identificacao", titulo: "Identificação", faltando },
    { id: "etapa-conteudo", titulo: "Conteúdo", faltando: [], opcional: true },
    { id: "etapa-configuracoes", titulo: "Configurações", faltando: [], opcional: true },
  ];

  // Erro sob o campo só depois de tentar enviar: ao abrir a tela, campo vazio
  // é o estado normal, não um erro.
  const [tentouEnviar, setTentouEnviar] = useState(false);
  const erroDe = (campoId: string, mensagem: string) =>
    tentouEnviar && faltando.some((f) => f.campoId === campoId) ? mensagem : undefined;

  function validar(): boolean {
    setTentouEnviar(true);
    if (faltando.length > 0) {
      // Os campos que faltam são combos (botões), que não carregam
      // aria-invalid — por isso o foco vai pelo id, não por
      // focarPrimeiroInvalido. Centraliza antes de focar: o foco sozinho
      // deixava o campo colado na barra de ações fixa.
      const el = document.getElementById(faltando[0].campoId);
      el?.scrollIntoView?.({ behavior: "smooth", block: "center" });
      el?.focus({ preventScroll: true });
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
    setTentouEnviar(false);
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

  // A unidade sugerida pelo nome, não pelo número: quem preenche reconhece
  // "Secretaria de Obras", não "#12". O nome vem das lotações do usuário e,
  // na falta, do organograma (mesmo cache do UnidadePicker).
  const minhaUnidadeId = user?.id_unidade_trabalho ?? null;
  const minhaUnidadeNome =
    minhaUnidadeId == null
      ? null
      : (user?.lotacoes?.find((l) => l.id === minhaUnidadeId)?.nome ??
        organogramaQ.data?.find((u) => u.id === minhaUnidadeId)?.unidade_trabalho ??
        null);
  const usandoMinhaUnidade =
    minhaUnidadeId != null && form.id_unidade_proprietaria === minhaUnidadeId;

  const falta = resumoDoQueFalta(etapas);
  const status = (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {hasDraft && (
        <span className="inline-flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3 text-success" aria-hidden="true" />
          Rascunho salvo automaticamente.
        </span>
      )}
      {falta ? (
        <span className={tentouEnviar ? "font-medium text-warning-soft-foreground" : undefined}>
          {falta}
        </span>
      ) : editando ? (
        "Abrir o processo gera o número. Depois disso, ele não volta a ser rascunho."
      ) : (
        "Tudo pronto para abrir o processo."
      )}
    </span>
  );

  return (
    // O cabeçalho ocupa a largura da tela, como nas outras; o formulário fica
    // na coluna de leitura e o roteiro ao lado, no espaço que sobrava em
    // branco em telas largas.
    <div className="space-y-4">
      <PageHeader
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
            : "O número é gerado ao abrir. Enquanto você preenche, o que já digitou fica guardado neste navegador."
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

      <form onSubmit={submit} noValidate>
        <LayoutFormulario roteiro={<RoteiroFormulario etapas={etapas} />}>
          {err && (
            <div
              role="alert"
              className="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger-soft-foreground"
            >
              <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{err}</span>
            </div>
          )}

          {/* === Etapa 1: quem pede, o quê, e quem cuida === */}
          <SectionCard
            id="etapa-identificacao"
            step={1}
            icon={Users}
            title="Identificação"
            description="Quem está pedindo, qual é o assunto e qual unidade cuida do processo."
          >
            <FormField
              label="Manifestante"
              required
              hint="Quem pede: busque pelo nome, CPF ou CNPJ."
              error={erroDe(
                "manif",
                "Escolha o manifestante. Se ele ainda não tem cadastro, use “Cadastrar novo”.",
              )}
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
                id="manif"
                options={manifestanteBusca.options}
                selectedOption={manifestanteBusca.selectedOption}
                onQueryChange={manifestanteBusca.onQueryChange}
                value={form.id_manifestante === "" ? null : form.id_manifestante}
                onChange={(v) =>
                  setForm({ ...form, id_manifestante: typeof v === "number" ? v : "" })
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

            {/* Tipo e assunto andam juntos: o tipo só filtra a lista de assuntos. */}
            <GradeCampos>
              <FormField label="Tipo de processo" opcional hint="Só filtra a lista de assuntos.">
                <Combobox
                  id="tipo"
                  options={tipoOptions}
                  value={form.id_tipo_processo === "" ? null : form.id_tipo_processo}
                  onChange={handleTipoChange}
                  placeholder="Todos os tipos"
                  searchPlaceholder="Buscar tipo…"
                  emptyText="Nenhum tipo de processo."
                  loading={tiposProcessoQ.isLoading}
                />
              </FormField>

              <FormField
                label="Assunto"
                required
                error={erroDe(
                  "assunto",
                  form.id_tipo_processo
                    ? "Escolha o assunto. Não achou? Limpe o tipo de processo para ver todos."
                    : "Escolha o assunto do pedido.",
                )}
              >
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
              </FormField>
            </GradeCampos>

            <p className="flex items-start gap-1.5 text-xs text-foreground-subtle">
              <Lock className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" />
              Manifestante e assunto não podem ser alterados depois que o processo for aberto.
            </p>

            <FormField
              label="Unidade proprietária"
              required
              hint={
                usandoMinhaUnidade
                  ? `Preenchida com a sua unidade${minhaUnidadeNome ? ` (${minhaUnidadeNome})` : ""}. Troque se o processo for de outra.`
                  : "A unidade responsável pelo processo. Busque pelo nome ou pela sigla."
              }
              error={erroDe("unidade", "Escolha a unidade responsável pelo processo.")}
              acao={
                minhaUnidadeId != null && !usandoMinhaUnidade ? (
                  <button
                    type="button"
                    onClick={() => setForm({ ...form, id_unidade_proprietaria: minhaUnidadeId })}
                    title={minhaUnidadeNome ?? undefined}
                    className="font-medium text-primary hover:underline"
                  >
                    Usar a minha unidade
                  </button>
                ) : undefined
              }
            >
              {/* Busca do Heitor (PR 146): nome ou sigla, sem acento, com o
                  caminho na hierarquia e o organograma a um clique. Escolhida
                  pelo PO em 2026-11-06 no lugar da lista simples do PR 144. */}
              <UnidadePicker
                id="unidade"
                value={
                  form.id_unidade_proprietaria === ""
                    ? null
                    : form.id_unidade_proprietaria
                }
                onChange={(v) => setForm({ ...form, id_unidade_proprietaria: v ?? "" })}
                placeholder="Buscar unidade…"
              />
            </FormField>
          </SectionCard>

          {/* === Etapa 2: o pedido em si === */}
          <SectionCard
            id="etapa-conteudo"
            step={2}
            icon={Tag}
            title="Conteúdo"
            description="Um resumo para as listas e o texto completo do pedido."
          >
            <FormField
              label="Observação"
              opcional
              hint="Uma linha que aparece nas listagens e nas buscas."
            >
              <Textarea
                id="obs"
                value={form.observacao}
                onChange={(e) => setForm({ ...form, observacao: e.target.value })}
                rows={2}
                placeholder="Ex.: Poda de árvore em frente ao nº 120 da Rua das Flores"
              />
            </FormField>

            <FormField
              label="Corpo do processo"
              opcional
              hint="Texto formatado. Aparece no PDF e na ficha do processo."
              acao={
                templateOptions.length > 0 ? (
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
                ) : undefined
              }
            >
              {/* O editor não aceita id: o rótulo aponta para o invólucro, e o
                  nome acessível do editor vem do ariaLabel. */}
              <div>
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
              </div>
            </FormField>
          </SectionCard>

          {/* === Etapa 3: detalhes que quase sempre ficam no padrão === */}
          <SectionCard
            id="etapa-configuracoes"
            step={3}
            icon={Hash}
            title="Configurações"
            description="Já vêm no padrão mais comum. Mude só se o caso pedir."
          >
            <FormField
              label="Número de origem"
              opcional
              hint="Número do documento em outro órgão ou sistema, se houver."
            >
              <Input
                id="origem"
                value={form.numero_origem}
                onChange={(e) => setForm({ ...form, numero_origem: e.target.value })}
                placeholder="Ex.: Ofício 123/2026"
              />
            </FormField>

            {/* Rótulos e textos mantidos de propósito (decisão de 2026-11-04):
                hoje `publico=false` grava o nível `interno`
                (services/sigilo.py), que todo servidor alcança pela credencial
                padrão, e nenhum acesso é registrado em auditoria. O
                comportamento do sigilo será ajustado em tarefa própria; ao
                mudá-lo, revisar estes textos. */}
            <EscolhaSegmentada
              nome="visibilidade"
              titulo="Visibilidade"
              moldura={false}
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
            <EscolhaSegmentada
              nome="origem-processo"
              titulo="Origem"
              moldura={false}
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
            <EscolhaSegmentada
              nome="canal-entrada"
              titulo="Canal de entrada"
              moldura={false}
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
          </SectionCard>

          {/* O botão principal nunca fica desabilitado por validação: clicar é
              o que mostra, sob cada campo, o que falta. Só trava enquanto envia. */}
          <BarraAcoesFormulario status={status}>
            <Button asChild variant="ghost">
              <Link
                href={editando ? `/m/protocolo/processos/${rascunhoId}` : "/m/protocolo/processos"}
              >
                Cancelar
              </Link>
            </Button>
            <Button
              type="button"
              variant="secondary"
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
            <Button type="submit" loading={salvando}>
              {salvando ? "Salvando…" : editando ? "Salvar e abrir processo" : "Abrir processo"}
              {!salvando && <ArrowRight className="h-4 w-4" aria-hidden="true" />}
            </Button>
          </BarraAcoesFormulario>
        </LayoutFormulario>
      </form>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { AlertCircle, AlertTriangle, GitBranch, Save } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormField } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { WorkflowEditor, type WorkflowEditorSelection } from "./WorkflowEditor";
import { WorkflowEditPanel } from "./WorkflowEditPanel";

import type { WorkflowDSL } from "@/lib/api";

interface Props {
  /** "novo" mostra campos slug; "editar" trava slug e versão. */
  mode: "novo" | "editar";
  initialSlug?: string;
  initialNome?: string;
  initialDescricao?: string | null;
  initialDsl: WorkflowDSL;
  versao?: number;
  saving: boolean;
  /** Backend ID quando editando — usado pro Cancelar voltar pra /workflow/[id] */
  workflowId?: number;
  onSave: (data: {
    slug: string;
    nome: string;
    descricao: string | null;
    dsl: WorkflowDSL;
  }) => Promise<void>;
}

interface ValidationIssue {
  level: "error" | "warning";
  msg: string;
  /** Erro de um campo do cabeçalho: aparece embaixo dele, não na lista. */
  campo?: "slug" | "nome";
}

function validateDsl(
  dsl: WorkflowDSL,
  slug: string,
  nome: string,
  mode: "novo" | "editar",
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];

  // Header
  if (mode === "novo") {
    if (!/^[a-z][a-z0-9_-]*$/.test(slug)) {
      issues.push({
        level: "error",
        msg: "O identificador deve começar com letra e usar só minúsculas, números, _ e -.",
        campo: "slug",
      });
    }
  }
  if (!nome.trim()) issues.push({ level: "error", msg: "Dê um nome ao workflow.", campo: "nome" });

  // Estados
  if (dsl.estados.length === 0) {
    issues.push({ level: "error", msg: "Adicione pelo menos um estado." });
  }
  const slugs = dsl.estados.map((e) => e.slug);
  const dup = slugs.filter((s, i) => slugs.indexOf(s) !== i);
  if (dup.length > 0) {
    issues.push({ level: "error", msg: `Slugs duplicados: ${[...new Set(dup)].join(", ")}` });
  }
  for (const est of dsl.estados) {
    if (!/^[a-z][a-z0-9_]*$/.test(est.slug)) {
      issues.push({
        level: "error",
        msg: `Slug inválido em estado "${est.slug}".`,
      });
    }
    if (!est.nome.trim()) {
      issues.push({ level: "error", msg: `Estado "${est.slug}" sem nome.` });
    }
  }

  if (!slugs.includes(dsl.estado_inicial)) {
    issues.push({
      level: "error",
      msg: `Estado inicial "${dsl.estado_inicial}" não existe.`,
    });
  }

  const finais = new Set(dsl.estados.filter((e) => e.final).map((e) => e.slug));
  if (finais.size === 0) {
    issues.push({
      level: "warning",
      msg: "Nenhum estado final — o workflow nunca encerra automaticamente.",
    });
  }

  // Transições
  const slugSet = new Set(slugs);
  for (const [i, t] of dsl.transicoes.entries()) {
    if (!slugSet.has(t.de)) {
      issues.push({ level: "error", msg: `Transição #${i} sai de estado inexistente "${t.de}".` });
    }
    if (!slugSet.has(t.para)) {
      issues.push({ level: "error", msg: `Transição #${i} vai para estado inexistente "${t.para}".` });
    }
    if (finais.has(t.de)) {
      issues.push({
        level: "error",
        msg: `Transição #${i} sai de estado final "${t.de}" — proibido.`,
      });
    }
    if (!t.label.trim()) {
      issues.push({ level: "error", msg: `Transição #${i} sem label.` });
    }
  }

  // Alcançabilidade — warning se algum estado não é alcançável a partir do inicial
  const adj = new Map<string, string[]>();
  for (const s of slugs) adj.set(s, []);
  for (const t of dsl.transicoes) {
    if (adj.has(t.de)) adj.get(t.de)!.push(t.para);
  }
  const reachable = new Set<string>([dsl.estado_inicial]);
  const queue = [dsl.estado_inicial];
  while (queue.length) {
    const s = queue.shift()!;
    for (const n of adj.get(s) ?? []) {
      if (!reachable.has(n)) {
        reachable.add(n);
        queue.push(n);
      }
    }
  }
  const orfaos = slugs.filter((s) => !reachable.has(s));
  if (orfaos.length > 0) {
    issues.push({
      level: "warning",
      msg: `Estados não alcançáveis do inicial: ${orfaos.join(", ")}`,
    });
  }

  return issues;
}

export function WorkflowEditPage({
  mode,
  initialSlug = "",
  initialNome = "",
  initialDescricao = null,
  initialDsl,
  versao,
  saving,
  workflowId,
  onSave,
}: Props) {
  const router = useRouter();
  const toast = useToast();

  const [slug, setSlug] = useState(initialSlug);
  const [nome, setNome] = useState(initialNome);
  const [descricao, setDescricao] = useState<string | null>(initialDescricao);
  const [dsl, setDsl] = useState<WorkflowDSL>(initialDsl);
  const [selection, setSelection] = useState<WorkflowEditorSelection>({
    type: null,
    id: null,
    transicaoIndex: null,
  });

  const issues = useMemo(
    () => validateDsl(dsl, slug, nome, mode),
    [dsl, slug, nome, mode],
  );
  const errors = issues.filter((i) => i.level === "error");
  // Erro de campo só depois que a pessoa mexeu nele ou tentou salvar: a tela
  // abria com "Slug… deve começar com letra" e "Nome é obrigatório" em
  // vermelho antes de qualquer digitação. Por isso o Criar não fica mais
  // desabilitado com erro — clicar é o que revela o que falta.
  const [tocados, setTocados] = useState<{ slug?: boolean; nome?: boolean }>({});
  const [tentouSalvar, setTentouSalvar] = useState(false);
  const erroDoCampo = (campo: "slug" | "nome") =>
    tentouSalvar || tocados[campo]
      ? errors.find((i) => i.campo === campo)?.msg
      : undefined;
  const errosDoFluxo = errors.filter((i) => !i.campo);
  const warnings = issues.filter((i) => i.level === "warning");

  const handleSave = useCallback(async () => {
    setTentouSalvar(true);
    if (errors.length > 0) {
      toast.error(`Corrija ${errors.length} erro(s) antes de salvar.`);
      return;
    }
    try {
      await onSave({
        slug,
        nome,
        descricao: descricao || null,
        dsl,
      });
    } catch (e) {
      toast.error((e as Error).message);
    }
  }, [errors.length, onSave, slug, nome, descricao, dsl, toast]);

  const handleCancel = useCallback(() => {
    if (mode === "editar" && workflowId) {
      router.push(`/m/protocolo/workflow/${workflowId}`);
    } else {
      router.push("/m/protocolo/workflow");
    }
  }, [mode, workflowId, router]);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={GitBranch}
        breadcrumbs={[
          { label: "Workflows", href: "/m/protocolo/workflow" },
          ...(mode === "editar" && workflowId
            ? [{ label: initialNome || "Workflow", href: `/m/protocolo/workflow/${workflowId}` }]
            : []),
          { label: mode === "novo" ? "Novo workflow" : "Editar" },
        ]}
        title={mode === "novo" ? "Novo workflow" : `Editar workflow${versao ? ` · v${versao}` : ""}`}
        description="Desenhe os estados e as transições no diagrama; clique num item para editar os detalhes ao lado."
        actions={
          <>
            <Button variant="ghost" onClick={handleCancel} disabled={saving}>
              Cancelar
            </Button>
            <Button onClick={handleSave} loading={saving}>
              {!saving && <Save className="h-4 w-4" aria-hidden="true" />}
              {saving
                ? "Salvando…"
                : mode === "novo"
                  ? "Criar workflow"
                  : "Salvar nova versão"}
            </Button>
          </>
        }
      />

      {mode === "editar" && (
        <p className="rounded border border-info/30 bg-info-soft p-2 text-xs text-info-soft-foreground">
          Editar gera <strong>nova versão</strong> deste workflow (instâncias ativas
          continuam na versão antiga).
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <FormField
          label="Nome"
          required
          hint="Como o fluxo aparece nas listas."
          error={erroDoCampo("nome")}
        >
          <Input
            id="wf-nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            onBlur={() => setTocados((t) => ({ ...t, nome: true }))}
            placeholder="Ex.: Recurso administrativo"
          />
        </FormField>
        <FormField
          label="Identificador"
          required={mode === "novo"}
          hint={
            mode === "novo"
              ? "Minúsculas, números, _ e -. Não muda depois de criado."
              : "Não muda depois de criado."
          }
          error={erroDoCampo("slug")}
        >
          <Input
            id="wf-slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            onBlur={() => setTocados((t) => ({ ...t, slug: true }))}
            disabled={mode === "editar"}
            placeholder="Ex.: recurso_administrativo"
            className="font-mono"
          />
        </FormField>
        <FormField label="Descrição" opcional>
          <Textarea
            id="wf-desc"
            rows={1}
            value={descricao ?? ""}
            onChange={(e) => setDescricao(e.target.value || null)}
            placeholder="Ex.: Recursos contra decisões da Secretaria."
          />
        </FormField>
      </div>

      {(errosDoFluxo.length > 0 || warnings.length > 0) && (
        <div className="space-y-1">
          {errosDoFluxo.map((i, idx) => (
            <p
              key={`e-${idx}`}
              className="flex items-start gap-1.5 rounded border border-danger/40 bg-danger-soft px-2 py-1 text-xs text-danger-soft-foreground"
            >
              <AlertCircle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {i.msg}
            </p>
          ))}
          {warnings.map((i, idx) => (
            <p
              key={`w-${idx}`}
              className="flex items-start gap-1.5 rounded border border-warning/40 bg-warning-soft px-2 py-1 text-xs text-warning-soft-foreground"
            >
              <AlertTriangle className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              {i.msg}
            </p>
          ))}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="overflow-hidden rounded-md border border-border">
          <WorkflowEditor
            dsl={dsl}
            onChange={setDsl}
            onSelectionChange={setSelection}
            height={560}
          />
        </div>
        <div>
          <WorkflowEditPanel dsl={dsl} selection={selection} onChange={setDsl} />
        </div>
      </div>
    </div>
  );
}

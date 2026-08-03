"use client";

import { useRouter } from "next/navigation";
import { Save, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
        msg: "Slug do workflow deve começar com letra e usar só [a-z0-9_-].",
      });
    }
  }
  if (!nome.trim()) issues.push({ level: "error", msg: "Nome é obrigatório." });

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
  const warnings = issues.filter((i) => i.level === "warning");

  const handleSave = useCallback(async () => {
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold text-primary">
          {mode === "novo" ? "Novo workflow" : `Editar workflow${versao ? ` · v${versao}` : ""}`}
        </h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={handleCancel} disabled={saving}>
            <X className="mr-1 h-4 w-4" aria-hidden="true" />
            Cancelar
          </Button>
          <Button onClick={handleSave} disabled={saving || errors.length > 0}>
            <Save className="mr-1 h-4 w-4" aria-hidden="true" />
            {saving
              ? "Salvando…"
              : mode === "novo"
                ? "Criar"
                : "Salvar nova versão"}
          </Button>
        </div>
      </div>

      {mode === "editar" && (
        <p className="rounded border border-blue-200 bg-blue-50 p-2 text-xs text-blue-900">
          Editar gera <strong>nova versão</strong> deste workflow (instances ativas
          continuam na versão antiga).
        </p>
      )}

      <div className="grid gap-3 md:grid-cols-3">
        <div className="space-y-1">
          <Label htmlFor="wf-slug">Slug</Label>
          <Input
            id="wf-slug"
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            disabled={mode === "editar"}
            placeholder="ex: fluxo_recurso"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="wf-nome">Nome</Label>
          <Input
            id="wf-nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            placeholder="Nome humano"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="wf-desc">Descrição</Label>
          <Textarea
            id="wf-desc"
            rows={1}
            value={descricao ?? ""}
            onChange={(e) => setDescricao(e.target.value || null)}
          />
        </div>
      </div>

      {(errors.length > 0 || warnings.length > 0) && (
        <div className="space-y-1">
          {errors.map((i, idx) => (
            <p
              key={`e-${idx}`}
              className="rounded border border-danger/40 bg-danger/10 px-2 py-1 text-xs text-danger-soft-foreground"
            >
              ❌ {i.msg}
            </p>
          ))}
          {warnings.map((i, idx) => (
            <p
              key={`w-${idx}`}
              className="rounded border border-warning/40 bg-warning/10 px-2 py-1 text-xs text-warning-soft-foreground"
            >
              ⚠ {i.msg}
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

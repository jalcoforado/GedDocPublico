"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { UnidadePicker } from "@/components/UnidadePicker";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  workflowApi,
  type WorkflowDSL,
  type WorkflowEstado,
  type WorkflowTransicao,
} from "@/lib/api";

import type { WorkflowEditorSelection } from "./WorkflowEditor";

interface Props {
  dsl: WorkflowDSL;
  selection: WorkflowEditorSelection;
  onChange: (dsl: WorkflowDSL) => void;
}

const EVENTOS = ["manual", "abertura", "encaminhamento", "recebimento"] as const;

export function WorkflowEditPanel({ dsl, selection, onChange }: Props) {
  if (selection.type === "estado" && selection.id) {
    return <EstadoEditor dsl={dsl} slug={selection.id} onChange={onChange} />;
  }
  if (selection.type === "transicao" && selection.transicaoIndex !== null) {
    return (
      <TransicaoEditor
        dsl={dsl}
        index={selection.transicaoIndex}
        onChange={onChange}
      />
    );
  }
  return (
    <div className="rounded-md border border-border bg-card p-4 text-sm text-muted-foreground">
      Clique num estado ou transição pra editar. Use o botão{" "}
      <strong>+ Estado</strong> pra adicionar; arraste de um nodo a outro pra criar
      transição. Backspace exclui o item selecionado.
    </div>
  );
}

function EstadoEditor({
  dsl,
  slug,
  onChange,
}: {
  dsl: WorkflowDSL;
  slug: string;
  onChange: (dsl: WorkflowDSL) => void;
}) {
  const est = dsl.estados.find((e) => e.slug === slug);
  if (!est) return null;

  function patch(p: Partial<WorkflowEstado>) {
    const novosEstados = dsl.estados.map((e) => (e.slug === slug ? { ...e, ...p } : e));
    // Se o slug mudou, propaga em transições e estado_inicial
    if (p.slug && p.slug !== slug) {
      const novasTransicoes = dsl.transicoes.map((t) => ({
        ...t,
        de: t.de === slug ? p.slug! : t.de,
        para: t.para === slug ? p.slug! : t.para,
      }));
      const estadoInicial = dsl.estado_inicial === slug ? p.slug! : dsl.estado_inicial;
      onChange({
        ...dsl,
        estado_inicial: estadoInicial,
        estados: novosEstados,
        transicoes: novasTransicoes,
      });
    } else {
      onChange({ ...dsl, estados: novosEstados });
    }
  }

  function definirComoInicial() {
    onChange({ ...dsl, estado_inicial: slug });
  }

  const slugInvalido = !/^[a-z][a-z0-9_]*$/.test(est.slug);
  const slugDuplicado =
    dsl.estados.filter((e) => e.slug === est.slug).length > 1;

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Estado</h3>
        {dsl.estado_inicial === slug ? (
          <span className="text-xs font-medium text-blue-700">● inicial</span>
        ) : (
          <Button size="sm" variant="ghost" onClick={definirComoInicial}>
            Definir como inicial
          </Button>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="est-slug">Slug</Label>
        <Input
          id="est-slug"
          value={est.slug}
          onChange={(e) => patch({ slug: e.target.value })}
          aria-invalid={slugInvalido || slugDuplicado}
        />
        {(slugInvalido || slugDuplicado) && (
          <p className="text-xs text-danger-soft-foreground">
            {slugInvalido
              ? "Use só [a-z0-9_], começando com letra."
              : "Slug duplicado."}
          </p>
        )}
      </div>

      <div className="space-y-1">
        <Label htmlFor="est-nome">Nome</Label>
        <Input
          id="est-nome"
          value={est.nome}
          onChange={(e) => patch({ nome: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="est-desc">Descrição</Label>
        <Textarea
          id="est-desc"
          rows={2}
          value={est.descricao ?? ""}
          onChange={(e) => patch({ descricao: e.target.value || null })}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="est-sla">SLA (dias)</Label>
        <Input
          id="est-sla"
          type="number"
          min={1}
          max={365}
          value={est.sla_dias ?? ""}
          onChange={(e) =>
            patch({
              sla_dias: e.target.value === "" ? null : Number(e.target.value),
            })
          }
          placeholder="Sem SLA"
        />
        <p className="text-xs text-muted-foreground">
          Se preenchido, dispara alerta quando processo ficar mais de N dias neste
          estado.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={est.final}
          onChange={(e) => patch({ final: e.target.checked })}
        />
        Estado final (encerra a instance)
      </label>

      <UnidadeResponsavelField
        value={est.id_unidade_responsavel ?? null}
        onChange={(v) => patch({ id_unidade_responsavel: v })}
      />
    </div>
  );
}

function UnidadeResponsavelField({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <div className="space-y-1 border-t border-border pt-3">
      <Label>Unidade responsável</Label>
      <UnidadePicker
        value={value}
        onChange={onChange}
        placeholder="Nenhuma — qualquer usuário pode avançar"
      />
      <p className="text-xs text-muted-foreground">
        Quando o processo entra neste estado, é{" "}
        <strong>auto-encaminhado</strong> pra esta unidade. A transição também
        passa a aparecer só pros usuários lotados nela.
      </p>
    </div>
  );
}

function TransicaoEditor({
  dsl,
  index,
  onChange,
}: {
  dsl: WorkflowDSL;
  index: number;
  onChange: (dsl: WorkflowDSL) => void;
}) {
  const t = dsl.transicoes[index];
  if (!t) return null;

  function patch(p: Partial<WorkflowTransicao>) {
    const novas = dsl.transicoes.map((tt, i) => (i === index ? { ...tt, ...p } : tt));
    onChange({ ...dsl, transicoes: novas });
  }

  return (
    <div className="space-y-3 rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Transição</h3>
        <span className="font-mono text-xs text-muted-foreground">
          {t.de} → {t.para}
        </span>
      </div>

      <div className="space-y-1">
        <Label htmlFor="tr-label">Label</Label>
        <Input
          id="tr-label"
          value={t.label}
          onChange={(e) => patch({ label: e.target.value })}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="tr-evento">Evento gatilho</Label>
        <select
          id="tr-evento"
          value={t.evento}
          onChange={(e) =>
            patch({ evento: e.target.value as WorkflowTransicao["evento"] })
          }
          className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm"
        >
          {EVENTOS.map((ev) => (
            <option key={ev} value={ev}>
              {ev}
            </option>
          ))}
        </select>
        <p className="text-xs text-muted-foreground">
          <code>manual</code>: só via API. <code>abertura</code>: dispara ao criar
          processo. <code>encaminhamento</code>/<code>recebimento</code>: hooks de
          movimentação.
        </p>
      </div>

      <CondicaoEditor
        condicao={t.condicao}
        onChange={(c) => patch({ condicao: c })}
      />

      <div className="space-y-1">
        <Label htmlFor="tr-grupos">Grupos permitidos (slugs separados por vírgula)</Label>
        <Input
          id="tr-grupos"
          value={t.grupos_permitidos.join(", ")}
          onChange={(e) =>
            patch({
              grupos_permitidos: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
          placeholder="Vazio = qualquer um"
        />
      </div>
    </div>
  );
}

const CONTEXTO_TESTE_DEFAULT = JSON.stringify(
  {
    dias_aberto: 5,
    estado_atual: "exemplo",
    externo: false,
    publico: true,
  },
  null,
  2,
);

function CondicaoEditor({
  condicao,
  onChange,
}: {
  condicao: string | null;
  onChange: (c: string | null) => void;
}) {
  const [contextoStr, setContextoStr] = useState(CONTEXTO_TESTE_DEFAULT);
  const [parseError, setParseError] = useState<string | null>(null);
  const test = useMutation({
    mutationFn: (args: { expressao: string; contexto: Record<string, unknown> }) =>
      workflowApi.testExpr(args.expressao, args.contexto),
  });

  const testRef = useRef(test);
  testRef.current = test;

  // Reset resultado se condicao mudou
  useEffect(() => {
    test.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [condicao]);

  function runTest() {
    if (!condicao || !condicao.trim()) return;
    setParseError(null);
    try {
      const ctx = JSON.parse(contextoStr || "{}");
      test.mutate({ expressao: condicao, contexto: ctx });
    } catch (e) {
      setParseError((e as Error).message);
    }
  }

  return (
    <div className="space-y-1">
      <Label htmlFor="tr-cond">Condição (expressão SAFE)</Label>
      <Textarea
        id="tr-cond"
        rows={2}
        value={condicao ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        placeholder="ex: dias_aberto < 30"
        className="font-mono text-xs"
      />
      <p className="text-xs text-muted-foreground">
        Vazio = sempre permite. Vars disponíveis: <code>dias_aberto</code>,{" "}
        <code>estado_atual</code>, <code>estado_anterior</code>,{" "}
        <code>numero_processo</code>, <code>externo</code>, <code>publico</code>, +
        funções: <code>len</code>, <code>min</code>, <code>max</code>,{" "}
        <code>dias_entre</code>.
      </p>

      {condicao && condicao.trim() && (
        <details className="text-xs">
          <summary className="cursor-pointer text-primary">Testar condição</summary>
          <div className="mt-2 space-y-2 rounded border border-border bg-muted/30 p-2">
            <Label htmlFor="ctx-test">Contexto JSON</Label>
            <Textarea
              id="ctx-test"
              rows={5}
              value={contextoStr}
              onChange={(e) => setContextoStr(e.target.value)}
              className="font-mono text-xs"
            />
            {parseError && (
              <p className="text-danger-soft-foreground">JSON inválido: {parseError}</p>
            )}
            <Button size="sm" variant="secondary" onClick={runTest} disabled={test.isPending}>
              <FlaskConical className="mr-1 h-3.5 w-3.5" aria-hidden="true" />
              {test.isPending ? "Testando…" : "Avaliar"}
            </Button>
            {test.data && (
              <div className="rounded border border-border bg-card p-2 text-xs">
                {test.data.erro ? (
                  <div className="flex items-center gap-1 text-danger-soft-foreground">
                    <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    {test.data.erro}
                  </div>
                ) : (
                  <div
                    className={
                      test.data.truthy
                        ? "flex items-center gap-1 text-success-soft-foreground"
                        : "flex items-center gap-1 text-muted-foreground"
                    }
                  >
                    {test.data.truthy ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    Resultado: <code>{JSON.stringify(test.data.resultado)}</code>
                    {" — "}
                    {test.data.truthy ? "permite" : "bloqueia"} transição.
                  </div>
                )}
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

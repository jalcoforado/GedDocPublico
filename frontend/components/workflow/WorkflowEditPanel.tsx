"use client";

import { useMutation } from "@tanstack/react-query";
import { CheckCircle2, FlaskConical, XCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { UnidadePicker } from "@/components/UnidadePicker";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { FormField } from "@/components/ui/form-field";
import { Select } from "@/components/ui/select";
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
      Clique num estado ou numa transição para editar os detalhes aqui. Use{" "}
      <strong>+ Estado</strong> para adicionar; arraste de um estado a outro para criar
      uma transição. Backspace exclui o item selecionado.
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
    <div className="space-y-4 rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Estado</h3>
        {dsl.estado_inicial === slug ? (
          <span className="text-xs font-medium text-info-soft-foreground">● inicial</span>
        ) : (
          <Button size="sm" variant="ghost" onClick={definirComoInicial}>
            Definir como inicial
          </Button>
        )}
      </div>

      <FormField label="Nome" required hint="Como o estado aparece no processo.">
        <Input
          id="est-nome"
          value={est.nome}
          onChange={(e) => patch({ nome: e.target.value })}
          placeholder="Ex.: Em análise"
        />
      </FormField>

      <FormField
        label="Identificador"
        required
        hint="Minúsculas, números e _, começando com letra."
        error={
          slugInvalido
            ? "Use só minúsculas, números e _, começando com letra (ex.: em_analise)."
            : slugDuplicado
              ? "Outro estado já usa este identificador. Escolha outro."
              : undefined
        }
      >
        <Input
          id="est-slug"
          value={est.slug}
          onChange={(e) => patch({ slug: e.target.value })}
          className="font-mono"
        />
      </FormField>

      <FormField label="Descrição" opcional>
        <Textarea
          id="est-desc"
          rows={2}
          value={est.descricao ?? ""}
          onChange={(e) => patch({ descricao: e.target.value || null })}
          placeholder="Ex.: O técnico confere os documentos."
        />
      </FormField>

      <FormField
        label="Prazo no estado"
        opcional
        hint="Passou disso, o processo gera alerta. Em branco, sem prazo."
      >
        <CampoComUnidade
          id="est-sla"
          type="number"
          min={1}
          max={365}
          sufixo="dias"
          value={est.sla_dias ?? ""}
          onChange={(e) =>
            patch({
              sla_dias: e.target.value === "" ? null : Number(e.target.value),
            })
          }
          placeholder="Ex.: 15"
        />
      </FormField>

      <label className="flex cursor-pointer items-start gap-2.5 rounded-md border border-border bg-surface-1 px-3 py-2.5 transition-colors duration-fast hover:bg-surface-2">
        <Checkbox
          checked={est.final}
          onChange={(e) => patch({ final: e.target.checked })}
          className="mt-0.5 h-4 w-4"
        />
        <span className="text-sm">
          <span className="block font-medium text-foreground">Estado final</span>
          <span className="block text-xs text-foreground-muted">
            Chegar aqui encerra o fluxo do processo.
          </span>
        </span>
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
    <div className="border-t border-border pt-4">
      <FormField
        label="Unidade responsável"
        opcional
        hint={
          <>
            Ao entrar neste estado, o processo é <strong>encaminhado sozinho</strong> para
            esta unidade, e a transição só aparece para quem é lotado nela.
          </>
        }
      >
        <UnidadePicker
          id="est-unidade"
          value={value}
          onChange={onChange}
          placeholder="Nenhuma: qualquer usuário pode avançar"
        />
      </FormField>
    </div>
  );
}

/** Rótulo e efeito de cada evento — o `<select>` mostrava o valor cru ("encaminhamento"). */
const EVENTO_INFO: Record<(typeof EVENTOS)[number], { rotulo: string; descricao: string }> = {
  manual: { rotulo: "Manual", descricao: "Alguém aciona a transição (pela tela ou pela API)." },
  abertura: { rotulo: "Ao abrir o processo", descricao: "Dispara sozinha quando o processo é criado." },
  encaminhamento: {
    rotulo: "Ao encaminhar",
    descricao: "Dispara sozinha quando o processo é encaminhado.",
  },
  recebimento: { rotulo: "Ao receber", descricao: "Dispara sozinha quando o processo é recebido." },
};

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
    <div className="space-y-4 rounded-md border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">Transição</h3>
        <span className="truncate font-mono text-xs text-foreground-muted">
          {t.de} → {t.para}
        </span>
      </div>

      <FormField
        label="Rótulo"
        required
        hint="O nome da ação, como aparece para quem avança o processo."
      >
        <Input
          id="tr-label"
          value={t.label}
          onChange={(e) => patch({ label: e.target.value })}
          placeholder="Ex.: Aprovar"
        />
      </FormField>

      <FormField
        label="Quando acontece"
        hint={EVENTO_INFO[t.evento as (typeof EVENTOS)[number]]?.descricao}
      >
        <Select
          id="tr-evento"
          value={t.evento}
          onChange={(e) =>
            patch({ evento: e.target.value as WorkflowTransicao["evento"] })
          }
        >
          {EVENTOS.map((ev) => (
            <option key={ev} value={ev}>
              {EVENTO_INFO[ev].rotulo}
            </option>
          ))}
        </Select>
      </FormField>

      <CondicaoEditor
        condicao={t.condicao}
        onChange={(c) => patch({ condicao: c })}
      />

      <FormField
        label="Grupos permitidos"
        opcional
        hint="Identificadores separados por vírgula. Em branco, qualquer um pode acionar."
      >
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
          placeholder="Ex.: juridico, gabinete"
          className="font-mono"
        />
      </FormField>
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
    <div className="space-y-2">
      <FormField
        label="Condição"
        opcional
        hint={
          <>
            Em branco, sempre permite. Variáveis: <code>dias_aberto</code>,{" "}
            <code>estado_atual</code>, <code>estado_anterior</code>,{" "}
            <code>numero_processo</code>, <code>externo</code>, <code>publico</code>; funções:{" "}
            <code>len</code>, <code>min</code>, <code>max</code>, <code>dias_entre</code>.
          </>
        }
      >
        <Textarea
          id="tr-cond"
          rows={2}
          value={condicao ?? ""}
          onChange={(e) => onChange(e.target.value || null)}
          placeholder="Ex.: dias_aberto < 30"
          className="font-mono text-xs"
        />
      </FormField>

      {condicao && condicao.trim() && (
        <details className="text-xs">
          <summary className="cursor-pointer font-medium text-primary">Testar condição</summary>
          <div className="mt-2 space-y-2 rounded border border-border bg-surface-1 p-2">
            <FormField
              label="Dados de teste (JSON)"
              hint="Valores das variáveis para simular um processo."
              error={parseError ? `JSON inválido: ${parseError}` : undefined}
            >
              <Textarea
                id="ctx-test"
                rows={5}
                value={contextoStr}
                onChange={(e) => setContextoStr(e.target.value)}
                className="font-mono text-xs"
              />
            </FormField>
            <Button size="sm" variant="secondary" onClick={runTest} loading={test.isPending}>
              {!test.isPending && <FlaskConical className="h-3.5 w-3.5" aria-hidden="true" />}
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
                        : "flex items-center gap-1 text-foreground-muted"
                    }
                  >
                    {test.data.truthy ? (
                      <CheckCircle2 className="h-3.5 w-3.5" aria-hidden="true" />
                    ) : (
                      <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    )}
                    Resultado: <code>{JSON.stringify(test.data.resultado)}</code>
                    {" — "}
                    {test.data.truthy ? "permite" : "bloqueia"} a transição.
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

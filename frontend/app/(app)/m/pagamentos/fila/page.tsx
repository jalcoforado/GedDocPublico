"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Flag, ListOrdered } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { fmtData, fmtDataHora, fmtMoeda } from "@/components/pagamentos/format";
import { FILA_ROTULO } from "@/components/pagamentos/situacoes";
import {
  CATEGORIA_CONTRATO_LABEL,
  api,
  type CategoriaContrato,
  type FilaCronologicaGrupo,
} from "@/lib/api";

const CATEGORIAS: CategoriaContrato[] = ["BENS", "LOCACOES", "SERVICOS", "OBRAS"];

function chaveGrupo(g: FilaCronologicaGrupo): string {
  return `${g.id_unidade}-${g.id_fonte_recursos}-${g.categoria}-${g.exercicio}`;
}

function tituloGrupo(g: FilaCronologicaGrupo): string {
  const unidade = g.unidade_nome ?? `Unidade #${g.id_unidade}`;
  const categoria =
    CATEGORIA_CONTRATO_LABEL[g.categoria as CategoriaContrato] ?? g.categoria;
  return `${unidade} · ${g.fonte_nome} · ${categoria} · ${g.exercicio}`;
}

export default function FilaCronologicaPage() {
  const [idFonte, setIdFonte] = useState<string>("");
  const [idUnidade, setIdUnidade] = useState<string>("");
  const [categoria, setCategoria] = useState<string>("");
  const [exercicio, setExercicio] = useState<string>("");
  const [incluirConcluidas, setIncluirConcluidas] = useState(false);

  const fontesQ = useQuery({
    queryKey: ["pag-fontes-select"],
    queryFn: () => api.pagamentos.cadastros.fontes.list(),
  });
  const unidadesQ = useQuery({
    queryKey: ["pag-unidades-select"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });

  const filaQ = useQuery({
    queryKey: [
      "pag-fila-cronologica",
      idFonte, idUnidade, categoria, exercicio, incluirConcluidas,
    ],
    queryFn: () =>
      api.pagamentos.filaCronologica({
        id_fonte: idFonte ? Number(idFonte) : undefined,
        id_unidade: idUnidade ? Number(idUnidade) : undefined,
        categoria: categoria || undefined,
        exercicio: exercicio ? Number(exercicio) : undefined,
        incluir_concluidas: incluirConcluidas,
      }),
  });

  const grupos = filaQ.data ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ListOrdered}
        title="Ordem cronológica"
        description="Fila de pagamento de cada despesa, na ordem em que a LRF e a lei de licitações exigem — agrupada por unidade, fonte, categoria e exercício."
      />

      <div className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-surface-1 p-4 sm:grid-cols-2 lg:grid-cols-5">
        <FormField label="Fonte de recursos">
          <Select value={idFonte} onChange={(e) => setIdFonte(e.target.value)}>
            <option value="">Todas</option>
            {(fontesQ.data ?? []).map((f) => (
              <option key={f.id} value={f.id}>
                {f.codigo} — {f.descricao}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Unidade">
          <Select value={idUnidade} onChange={(e) => setIdUnidade(e.target.value)}>
            <option value="">Todas</option>
            {(unidadesQ.data?.items ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.unidade_trabalho}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Categoria">
          <Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>
            <option value="">Todas</option>
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>
                {CATEGORIA_CONTRATO_LABEL[c]}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Exercício">
          <Select value={exercicio} onChange={(e) => setExercicio(e.target.value)}>
            <option value="">Todos</option>
            {anosRecentes().map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
        </FormField>
        <div className="flex items-end">
          <label className="flex items-center gap-2 text-sm text-foreground">
            <input
              type="checkbox"
              checked={incluirConcluidas}
              onChange={(e) => setIncluirConcluidas(e.target.checked)}
              className="h-4 w-4 rounded border-input text-primary focus:ring-2 focus:ring-ring"
            />
            Incluir concluídas
          </label>
        </div>
      </div>

      {filaQ.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : grupos.length === 0 ? (
        <EmptyState
          icon={ListOrdered}
          title="Nenhum débito na fila"
          description="Ajuste os filtros ou aguarde uma solicitação chegar à fase de liquidação — é aí que ela entra na ordem cronológica."
        />
      ) : (
        <div className="space-y-4">
          {grupos.map((g) => (
            <GrupoFila key={chaveGrupo(g)} grupo={g} />
          ))}
        </div>
      )}
    </div>
  );
}

function anosRecentes(): number[] {
  const atual = new Date().getFullYear();
  return [atual + 1, atual, atual - 1, atual - 2];
}

function GrupoFila({ grupo }: { grupo: FilaCronologicaGrupo }) {
  return (
    <section className="overflow-hidden rounded-lg border border-border bg-surface-1">
      <header className="border-b border-border bg-surface-2 px-4 py-2.5">
        <h2 className="text-sm font-semibold text-foreground">{tituloGrupo(grupo)}</h2>
        <p className="text-xs text-foreground-muted">
          {grupo.itens.length} débito(s) na fila
        </p>
      </header>
      <div className="overflow-x-auto">
        <Table variant="flat">
          <THead>
            <TR>
              <TH className="text-right">Posição</TH>
              <TH>Marco</TH>
              <TH>Fornecedor</TH>
              <TH>Descrição</TH>
              <TH className="text-right">Valor</TH>
              <TH>Situação</TH>
            </TR>
          </THead>
          <TBody>
            {grupo.itens.map((item) => (
              <LinhaFila key={item.id_debito} item={item} />
            ))}
          </TBody>
        </Table>
      </div>
    </section>
  );
}

function LinhaFila({ item }: { item: FilaCronologicaGrupo["itens"][number] }) {
  const [expandido, setExpandido] = useState(false);
  const rotulo = FILA_ROTULO[item.situacao as keyof typeof FILA_ROTULO] ?? {
    label: item.situacao,
    intent: "neutral" as const,
    icon: ListOrdered,
  };

  return (
    <>
      <TR>
        <TD className="text-right tabular-nums font-medium">{item.posicao}</TD>
        <TD className="whitespace-nowrap">{fmtDataHora(item.marco_em)}</TD>
        <TD className="max-w-[16rem] truncate" title={item.fornecedor_nome}>
          {item.fornecedor_nome}
        </TD>
        <TD className="max-w-[20rem] truncate" title={item.descricao}>
          {item.descricao}
        </TD>
        <TD className="whitespace-nowrap text-right tabular-nums">
          {fmtMoeda(item.valor_total)}
        </TD>
        <TD>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge intent={rotulo.intent} icon={rotulo.icon}>
              {rotulo.label}
            </Badge>
            {item.motivo_bloqueio && (
              <span className="text-xs text-foreground-muted">{item.motivo_bloqueio}</span>
            )}
            {item.tem_excecao && (
              <button
                type="button"
                onClick={() => setExpandido((v) => !v)}
                className="inline-flex items-center gap-1 rounded-badge bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning-soft-foreground hover:brightness-95"
                aria-expanded={expandido}
              >
                <Flag className="h-3 w-3" aria-hidden="true" />
                Exceção autorizada
                <ChevronDown
                  className={`h-3 w-3 transition-transform ${expandido ? "rotate-180" : ""}`}
                  aria-hidden="true"
                />
              </button>
            )}
          </div>
        </TD>
      </TR>
      {item.tem_excecao && expandido && (
        <TR>
          <TD colSpan={6} className="bg-warning-soft/30 text-sm">
            <ExcecaoDoDebito idDebito={item.id_debito} />
          </TD>
        </TR>
      )}
    </>
  );
}

function ExcecaoDoDebito({ idDebito }: { idDebito: number }) {
  const excecoesQ = useQuery({
    queryKey: ["pag-excecoes-cronologicas", idDebito],
    queryFn: () => api.pagamentos.debitos.listarExcecoes(idDebito),
  });

  const excecoes = excecoesQ.data ?? [];

  if (excecoesQ.isLoading) return <Skeleton className="h-6 w-full" />;
  if (excecoes.length === 0) {
    return <p className="text-foreground-muted">Sem detalhes de exceção registrados.</p>;
  }

  return (
    <div className="space-y-2 py-1">
      {excecoes.map((e) => (
        <div key={e.id}>
          <p className="font-medium text-foreground">
            {e.fundamento} — autorizada em {fmtData(e.data_autorizacao)}
          </p>
          <p className="text-foreground-muted">{e.justificativa}</p>
        </div>
      ))}
    </div>
  );
}

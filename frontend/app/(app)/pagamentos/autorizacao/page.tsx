"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ExternalLink, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { GrupoContaCard } from "@/components/pagamentos/GrupoContaCard";
import { fmtData, fmtDataCurta, fmtMoeda } from "@/components/pagamentos/format";
import { RitoPagamento } from "@/components/pagamentos/RitoPagamento";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import {
  api,
  type DebitoFilaItem,
  type FilaAutorizacaoFonteGrupo,
  type FilaLiberacaoGrupo,
  type OrdemPagamento,
  type ParcelaFilaLibItem,
} from "@/lib/api";

type Tab = "despesa" | "pagamento";

const INVALIDATE_KEYS = [
  ["pag-fila-autorizacao"],
  ["pag-fila-liberacao"],
  ["pag-fila-tesouraria"],
  ["pag-fila"],
  ["pag-debitos"],
  ["pag-caixa-painel"],
] as const;

export default function AutorizacaoPagamentosPage() {
  const searchParams = useSearchParams();
  const [tab, setTab] = useState<Tab>(searchParams.get("tab") === "pagamento" ? "pagamento" : "despesa");

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ShieldCheck}
        title="Autorizações"
        description="Autorize a despesa (gera a Ordem de Pagamento) e depois libere o pagamento para a tesouraria — os dois atos do rito da Lei 4.320/64."
        tabs={
          <div role="tablist" aria-label="Etapa da autorização" className="flex gap-1 py-2">
            <TabButton active={tab === "despesa"} onClick={() => setTab("despesa")}>
              Despesa
            </TabButton>
            <TabButton active={tab === "pagamento"} onClick={() => setTab("pagamento")}>
              Pagamento
            </TabButton>
          </div>
        }
      />

      <RitoPagamento atual={tab === "despesa" ? "autorizar" : "liberar"} />

      {tab === "despesa" ? <TabDespesa /> : <TabPagamento />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
        active
          ? "bg-brand/12 text-brand dark:bg-brand/25 dark:text-brand-light"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
      )}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Tab Despesa — fila APROVADO agrupada por FONTE (v2.0). Por fonte, o autorizador
// escolhe a CONTA PAGADORA entre as contas ativas da fonte e autoriza (gera OP,
// reserva o valor na conta escolhida).
// ---------------------------------------------------------------------------

function TabDespesa() {
  const qc = useQueryClient();
  const toast = useToast();
  const [selecionados, setSelecionados] = useState<number[]>([]);
  // conta pagadora escolhida por fonte (id_fonte -> id_conta)
  const [contaPorFonte, setContaPorFonte] = useState<Record<number, number>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);

  const filaQ = useQuery({
    queryKey: ["pag-fila-autorizacao"],
    queryFn: () => api.pagamentos.filas.autorizacao(),
  });

  const grupos = filaQ.data ?? [];
  const selecionadosSet = useMemo(() => new Set(selecionados), [selecionados]);

  // Pré-seleciona a conta quando a fonte tem exatamente uma conta elegível (RF-AUT-10).
  useEffect(() => {
    setContaPorFonte((cur) => {
      const next = { ...cur };
      let mudou = false;
      for (const g of grupos) {
        if (next[g.id_fonte] === undefined && g.contas_elegiveis.length === 1) {
          next[g.id_fonte] = g.contas_elegiveis[0].id_conta;
          mudou = true;
        }
      }
      return mudou ? next : cur;
    });
  }, [grupos]);

  const somaSelecionados = useMemo(
    () =>
      grupos
        .flatMap((g) => g.debitos)
        .filter((d) => selecionadosSet.has(d.id))
        .reduce((acc, d) => acc + (Number(d.valor_total) || 0), 0),
    [grupos, selecionadosSet],
  );

  function toggle(id: number) {
    setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function toggleGrupo(grupo: FilaAutorizacaoFonteGrupo) {
    const ids = grupo.debitos.map((d) => d.id);
    const todosNoGrupo = ids.every((id) => selecionadosSet.has(id));
    setSelecionados((cur) =>
      todosNoGrupo ? cur.filter((id) => !ids.includes(id)) : Array.from(new Set([...cur, ...ids])),
    );
  }

  // Grupos com débitos selecionados, com a conta escolhida e a soma.
  const gruposSelecionados = useMemo(
    () =>
      grupos
        .map((g) => {
          const debs = g.debitos.filter((d) => selecionadosSet.has(d.id));
          const soma = debs.reduce((acc, d) => acc + (Number(d.valor_total) || 0), 0);
          const contaId = contaPorFonte[g.id_fonte];
          const conta = g.contas_elegiveis.find((c) => c.id_conta === contaId);
          return { grupo: g, debs, soma, contaId, conta };
        })
        .filter((x) => x.debs.length > 0),
    [grupos, selecionadosSet, contaPorFonte],
  );

  const faltaConta = gruposSelecionados.some((x) => x.contaId === undefined);
  const algumExcede = gruposSelecionados.some(
    (x) => x.conta && x.soma > (Number(x.conta.disponivel) || 0),
  );

  const autorizarM = useMutation({
    mutationFn: () =>
      api.pagamentos.autorizar(
        gruposSelecionados.map((x) => ({
          id_fonte: x.grupo.id_fonte,
          id_conta_pagadora: x.contaId as number,
          debito_ids: x.debs.map((d) => d.id),
        })),
      ),
    onSuccess: (ops: OrdemPagamento[]) => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      const total = ops.reduce((acc, o) => acc + (Number(o.valor_total) || 0), 0);
      toast.success(
        `${ops.length} Ordem(ns) de Pagamento gerada(s) — ${fmtMoeda(total)}`,
        ops.length === 1
          ? {
              action: {
                label: "Abrir PDF",
                onClick: () => window.open(api.pagamentos.ordens.pdfUrl(ops[0].id), "_blank", "noopener"),
              },
            }
          : undefined,
      );
      setSelecionados([]);
      setConfirmOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!filaQ.isLoading && grupos.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Nada aguardando autorização"
        description="Os débitos aprovados pela chefia aparecem aqui, agrupados por fonte de recursos, para você escolher a conta pagadora e emitir a Ordem de Pagamento."
      />
    );
  }

  return (
    <div className="space-y-4 pb-24">
      {grupos.map((grupo) => {
        const ids = grupo.debitos.map((d) => d.id);
        const groupChecked = ids.length > 0 && ids.every((id) => selecionadosSet.has(id));
        const semConta = grupo.contas_elegiveis.length === 0;
        const contaId = contaPorFonte[grupo.id_fonte];
        const contaSel = grupo.contas_elegiveis.find((c) => c.id_conta === contaId);
        const somaGrupo = grupo.debitos
          .filter((d) => selecionadosSet.has(d.id))
          .reduce((acc, d) => acc + (Number(d.valor_total) || 0), 0);
        const excede = !!contaSel && somaGrupo > (Number(contaSel.disponivel) || 0);
        return (
          <div key={grupo.id_fonte} className="overflow-hidden rounded-lg border border-border bg-surface-1">
            {/* Cabeçalho da fonte + seletor de conta pagadora */}
            <div className="space-y-3 border-b border-border bg-surface-2 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <input
                    type="checkbox"
                    checked={groupChecked}
                    disabled={ids.length === 0 || semConta}
                    onChange={() => toggleGrupo(grupo)}
                    aria-label={`Selecionar todos da fonte ${grupo.codigo_fonte}`}
                    className="h-5 w-5 cursor-pointer rounded border-input text-primary focus:ring-2 focus:ring-ring disabled:opacity-50"
                  />
                  <span>
                    Fonte {grupo.codigo_fonte}
                    <span className="ml-1 font-normal text-muted-foreground" title={grupo.descricao_fonte}>
                      · {grupo.descricao_fonte}
                    </span>
                  </span>
                </label>
                {somaGrupo > 0 && (
                  <span className="text-sm tabular-nums text-muted-foreground">
                    Σ selecionado <span className="font-semibold text-foreground">{fmtMoeda(somaGrupo)}</span>
                  </span>
                )}
              </div>

              {semConta ? (
                <div className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning-soft px-3 py-2 text-xs text-warning-soft-foreground">
                  <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                  Nenhuma conta ativa nesta fonte — cadastre/ative uma conta para autorizar (RF-AUT-11).
                </div>
              ) : (
                <div className="flex flex-wrap items-end gap-2">
                  <div className="min-w-[16rem] flex-1">
                    <Label htmlFor={`conta-fonte-${grupo.id_fonte}`} className="text-xs">
                      Conta pagadora
                    </Label>
                    <select
                      id={`conta-fonte-${grupo.id_fonte}`}
                      value={contaId ?? ""}
                      onChange={(e) =>
                        setContaPorFonte((cur) => ({ ...cur, [grupo.id_fonte]: Number(e.target.value) }))
                      }
                      className="mt-1 h-9 w-full rounded-md border border-input bg-surface-1 px-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                    >
                      <option value="" disabled>
                        Selecione a conta pagadora…
                      </option>
                      {grupo.contas_elegiveis.map((c) => (
                        <option key={c.id_conta} value={c.id_conta}>
                          {c.nome} · {c.banco} ag.{c.agencia} c/{c.conta_mascarada} — disp.{" "}
                          {fmtMoeda(c.disponivel)}
                        </option>
                      ))}
                    </select>
                  </div>
                  {contaSel && (
                    <p
                      className={cn(
                        "pb-1.5 text-xs tabular-nums",
                        excede ? "text-warning-soft-foreground" : "text-muted-foreground",
                      )}
                    >
                      Disponível {fmtMoeda(contaSel.disponivel)}
                      {excede && " — insuficiente para o selecionado"}
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Débitos da fonte */}
            <div className="divide-y divide-border">
              {grupo.debitos.map((d: DebitoFilaItem) => (
                <div key={d.id} className="flex items-center gap-3 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selecionadosSet.has(d.id)}
                    disabled={semConta}
                    onChange={() => toggle(d.id)}
                    aria-label={`Selecionar ${d.nome_fornecedor}`}
                    className="h-5 w-5 shrink-0 cursor-pointer rounded border-input text-primary focus:ring-2 focus:ring-ring disabled:opacity-50"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate font-semibold text-foreground" title={d.nome_fornecedor}>
                        {d.nome_fornecedor}
                      </span>
                      <Link
                        href={`/pagamentos/contas-a-pagar/${d.id}`}
                        aria-label={`Ver detalhe de ${d.nome_fornecedor}`}
                        className="shrink-0 text-muted-foreground hover:text-foreground"
                      >
                        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      </Link>
                      {d.urgente && <Badge intent="danger">URGENTE</Badge>}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      <span title={d.natureza_descricao}>{d.natureza_codigo}</span> · comp. {d.competencia}
                      {d.aprovado_por && (
                        <> · aprovado por {d.aprovado_por} em {fmtDataCurta(d.aprovado_em)}</>
                      )}
                    </p>
                  </div>
                  <p className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
                    {fmtMoeda(d.valor_total)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        );
      })}

      {selecionados.length > 0 && (
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-1 px-4 py-3 shadow-md sm:mx-0 sm:rounded-lg sm:border">
          <p className="text-sm text-foreground">
            <span className="font-semibold">{selecionados.length}</span> débito(s) — Σ{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>
          </p>
          <Button onClick={() => setConfirmOpen(true)} disabled={faltaConta}>
            {faltaConta ? "Escolha a conta pagadora de cada fonte" : "Autorizar despesas (gerar OP)"}
          </Button>
        </div>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirmar autorização de despesa"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => autorizarM.mutate()}
              disabled={gruposSelecionados.length === 0 || faltaConta || autorizarM.isPending}
            >
              {autorizarM.isPending ? "Autorizando..." : "Confirmar e gerar OP"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Você está autorizando <span className="font-semibold">{selecionados.length}</span> débito(s),
            totalizando{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>. Cada fonte
            gera uma Ordem de Pagamento reservando o valor na conta escolhida — ação não reversível.
          </p>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Por fonte → conta pagadora
            </p>
            {gruposSelecionados.map(({ grupo, soma, conta }) => {
              const disponivel = Number(conta?.disponivel) || 0;
              const excede = !!conta && soma > disponivel;
              return (
                <div
                  key={grupo.id_fonte}
                  className={cn(
                    "flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm",
                    excede
                      ? "border-warning/40 bg-warning-soft text-warning-soft-foreground"
                      : "border-border bg-surface-1 text-foreground",
                  )}
                >
                  <span className="min-w-0 truncate" title={grupo.descricao_fonte}>
                    Fonte {grupo.codigo_fonte} → {conta ? conta.nome : "—"}
                  </span>
                  <span className="shrink-0 whitespace-nowrap tabular-nums">
                    {fmtMoeda(soma)} de {fmtMoeda(disponivel)} disp.
                  </span>
                </div>
              );
            })}
            {algumExcede && (
              <p className="text-xs text-warning-soft-foreground">
                Atenção: alguma conta escolhida não tem saldo disponível suficiente — o backend
                recusará a autorização por saldo insuficiente.
              </p>
            )}
          </div>
        </div>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab Pagamento — fila de liberação (A_PAGAR de débitos AUTORIZADO/PAGO_PARCIAL).
// ---------------------------------------------------------------------------

function TabPagamento() {
  const qc = useQueryClient();
  const toast = useToast();
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dataPrevista, setDataPrevista] = useState("");

  const filaQ = useQuery({
    queryKey: ["pag-fila-liberacao"],
    queryFn: () => api.pagamentos.filas.liberacao(),
  });

  const grupos = filaQ.data ?? [];
  const selecionadosSet = useMemo(() => new Set(selecionados), [selecionados]);

  const todasParcelas = useMemo(() => grupos.flatMap((g) => g.parcelas), [grupos]);
  const parcelasSelecionadas = useMemo(
    () => todasParcelas.filter((p) => selecionadosSet.has(p.id)),
    [todasParcelas, selecionadosSet],
  );
  const somaSelecionados = useMemo(
    () => parcelasSelecionadas.reduce((acc, p) => acc + (Number(p.valor) || 0), 0),
    [parcelasSelecionadas],
  );

  function toggle(id: number) {
    setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function toggleGrupo(grupo: FilaLiberacaoGrupo) {
    const ids = grupo.parcelas.map((p) => p.id);
    const todosNoGrupo = ids.every((id) => selecionadosSet.has(id));
    setSelecionados((cur) =>
      todosNoGrupo ? cur.filter((id) => !ids.includes(id)) : Array.from(new Set([...cur, ...ids])),
    );
  }

  const resumoPorConta = useMemo(
    () =>
      grupos
        .map((g) => {
          const soma = g.parcelas
            .filter((p) => selecionadosSet.has(p.id))
            .reduce((acc, p) => acc + (Number(p.valor) || 0), 0);
          return { grupo: g, soma };
        })
        .filter((r) => r.soma > 0),
    [grupos, selecionadosSet],
  );

  const liberarM = useMutation({
    mutationFn: () => api.pagamentos.parcelas.liberar(selecionados, dataPrevista || null),
    onSuccess: () => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      toast.success(`${selecionados.length} parcela(s) liberada(s) para a tesouraria.`);
      setSelecionados([]);
      setDataPrevista("");
      setConfirmOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!filaQ.isLoading && grupos.length === 0) {
    return (
      <EmptyState
        icon={ShieldCheck}
        title="Nada aguardando liberação"
        description="Autorize despesas na aba Despesa — as parcelas dos débitos autorizados aparecem aqui para liberação à tesouraria."
      />
    );
  }

  return (
    <div className="space-y-4 pb-24">
      {grupos.map((grupo) => {
        const ids = grupo.parcelas.map((p) => p.id);
        const groupChecked = ids.length > 0 && ids.every((id) => selecionadosSet.has(id));
        const somaGrupo = grupo.parcelas
          .filter((p) => selecionadosSet.has(p.id))
          .reduce((acc, p) => acc + (Number(p.valor) || 0), 0);
        return (
          <GrupoContaCard
            key={grupo.id_conta}
            nomeConta={grupo.nome_conta}
            disponivel={grupo.disponivel}
            abaixoMinimo={grupo.abaixo_minimo}
            somaSelecionada={somaGrupo}
            groupChecked={groupChecked}
            onToggleGroup={() => toggleGrupo(grupo)}
            toggleGroupDisabled={ids.length === 0}
          >
            {grupo.parcelas.map((p: ParcelaFilaLibItem) => (
              <div key={p.id} className="flex items-center gap-3 px-4 py-3">
                <input
                  type="checkbox"
                  checked={selecionadosSet.has(p.id)}
                  onChange={() => toggle(p.id)}
                  aria-label={`Selecionar parcela de ${p.nome_fornecedor}`}
                  className="h-5 w-5 shrink-0 cursor-pointer rounded border-input text-primary focus:ring-2 focus:ring-ring"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="truncate font-semibold text-foreground" title={p.nome_fornecedor}>
                      {p.nome_fornecedor}
                    </span>
                    <Link
                      href={`/pagamentos/contas-a-pagar/${p.id_debito}`}
                      aria-label={`Ver detalhe de ${p.nome_fornecedor}`}
                      className="shrink-0 text-muted-foreground hover:text-foreground"
                    >
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </Link>
                    {p.vencida && <Badge intent="danger">vencida há {p.dias_atraso}d</Badge>}
                  </div>
                  <p className="truncate text-xs text-muted-foreground">
                    parcela {p.numero}/{p.qtd_parcelas} · vence {fmtData(p.vencimento)}
                    {p.op_numero && (
                      <>
                        {" "}
                        · OP{" "}
                        {p.op_id ? (
                          <a
                            href={api.pagamentos.ordens.pdfUrl(p.op_id)}
                            target="_blank"
                            rel="noopener"
                            className="inline-flex items-center gap-0.5 text-muted-foreground hover:text-foreground hover:underline"
                          >
                            {p.op_numero}
                            <FileText className="h-3 w-3" aria-hidden="true" />
                          </a>
                        ) : (
                          p.op_numero
                        )}
                      </>
                    )}
                  </p>
                </div>
                <p className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
                  {fmtMoeda(p.valor)}
                </p>
              </div>
            ))}
          </GrupoContaCard>
        );
      })}

      {selecionados.length > 0 && (
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-1 px-4 py-3 shadow-md sm:mx-0 sm:rounded-lg sm:border">
          <p className="text-sm text-foreground">
            <span className="font-semibold">{selecionados.length}</span> parcela(s) — Σ{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Label htmlFor="lib-data-prevista" className="sr-only">
              Data prevista (opcional)
            </Label>
            <Input
              id="lib-data-prevista"
              type="date"
              value={dataPrevista}
              onChange={(e) => setDataPrevista(e.target.value)}
              className="h-9 w-40"
              aria-label="Data prevista (opcional)"
            />
            <Button onClick={() => setConfirmOpen(true)}>Liberar pagamentos</Button>
          </div>
        </div>
      )}

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirmar liberação de pagamento"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => liberarM.mutate()} disabled={liberarM.isPending}>
              {liberarM.isPending ? "Liberando..." : "Confirmar liberação"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Você está liberando <span className="font-semibold">{selecionados.length}</span> parcela(s),
            totalizando{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span> para a
            tesouraria executar o pagamento.
            {dataPrevista && (
              <>
                {" "}
                Data prevista: <span className="font-semibold">{fmtData(dataPrevista)}</span>.
              </>
            )}
          </p>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Por conta</p>
            {resumoPorConta.map(({ grupo, soma }) => (
              <div
                key={grupo.id_conta}
                className="flex items-center justify-between rounded-md border border-border bg-surface-1 px-3 py-2 text-sm text-foreground"
              >
                <span className="min-w-0 truncate" title={grupo.nome_conta}>
                  {grupo.nome_conta}
                </span>
                <span className="shrink-0 whitespace-nowrap tabular-nums">{fmtMoeda(soma)}</span>
              </div>
            ))}
          </div>
        </div>
      </Dialog>
    </div>
  );
}

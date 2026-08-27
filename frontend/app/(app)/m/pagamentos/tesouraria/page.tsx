"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Banknote, FileText, Undo2 } from "lucide-react";
import { useMemo, useState } from "react";

import { fmtData, fmtDataCurta, fmtDataHora, fmtMoeda, hojeSemHora, parseDataLocal } from "@/components/pagamentos/format";
import { RitoPagamento } from "@/components/pagamentos/RitoPagamento";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePrompt } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { api, type ParcelaTesourariaItem } from "@/lib/api";
import { BotoesExportar } from "@/components/pagamentos/BotoesExportar";

type TabId = "pagar" | "ops" | "pagas";

const MAX_ORDENS = 15;

const INVALIDATE_KEYS = [
  ["pag-fila-autorizacao"],
  ["pag-fila-liberacao"],
  ["pag-fila-tesouraria"],
  ["pag-fila"],
  ["pag-debitos"],
  ["pag-caixa-painel"],
] as const;

type Urgencia = "atrasadas" | "hoje" | "semana" | "depois";

function bucketDe(item: ParcelaTesourariaItem): Urgencia {
  const ref = parseDataLocal(item.data_prevista_pagamento ?? item.vencimento);
  const hoje = hojeSemHora();
  const diffDias = Math.round((ref.getTime() - hoje.getTime()) / 86_400_000);
  if (diffDias < 0) return "atrasadas";
  if (diffDias === 0) return "hoje";
  if (diffDias <= 7) return "semana";
  return "depois";
}

const BUCKET_LABEL: Record<Urgencia, string> = {
  atrasadas: "Atrasadas",
  hoje: "Hoje",
  semana: "Esta semana",
  depois: "Depois",
};

export default function TesourariaPage() {
  const [tab, setTab] = useState<TabId>("pagar");

  return (
    // `Tabs` envolve o header E os painéis: a `TabList` viaja como prop até o
    // `PageHeader`, mas continua DENTRO desta subárvore no React, então o
    // contexto (ids, aria-controls) alcança os dois lados.
    <Tabs value={tab} onChange={(v) => setTab(v as TabId)} className="space-y-4">
      <PageHeader
        icon={Banknote}
        title="Tesouraria"
        description="Execute os pagamentos das parcelas liberadas pelo ordenador — o último ato do rito da Lei 4.320/64."
        tabs={
          <TabList
            aria-label="Seção da tesouraria"
            variant="pill"
            tabs={[
              { value: "pagar", label: "A pagar" },
              { value: "ops", label: "OPs emitidas" },
              { value: "pagas", label: "Pagas recentemente" },
            ]}
          />
        }
      />

      <RitoPagamento atual="pagar" />

      <TabPanel value="pagar">
        <TabAPagar />
      </TabPanel>
      <TabPanel value="ops">
        <TabOps />
      </TabPanel>
      <TabPanel value="pagas">
        <TabPagas />
      </TabPanel>
    </Tabs>
  );
}


// ---------------------------------------------------------------------------
// Tab "A pagar" — parcelas LIBERADAS, agrupadas por urgência temporal.
// ---------------------------------------------------------------------------

function TabAPagar() {
  const qc = useQueryClient();
  const toast = useToast();
  const prompt = usePrompt();
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [pagarOpen, setPagarOpen] = useState(false);
  const [pagarIds, setPagarIds] = useState<number[]>([]);
  const [formaPagamento, setFormaPagamento] = useState("PIX");
  const [dataPagamento, setDataPagamento] = useState("");

  const filaQ = useQuery({
    queryKey: ["pag-fila-tesouraria"],
    queryFn: () => api.pagamentos.filas.tesouraria(),
  });

  const liberadas = filaQ.data?.liberadas ?? [];
  const selecionadosSet = useMemo(() => new Set(selecionados), [selecionados]);

  const grupos = useMemo(() => {
    const m: Record<Urgencia, ParcelaTesourariaItem[]> = {
      atrasadas: [], hoje: [], semana: [], depois: [],
    };
    liberadas.forEach((p) => m[bucketDe(p)].push(p));
    return m;
  }, [liberadas]);

  const somaSelecionados = useMemo(
    () =>
      liberadas
        .filter((p) => selecionadosSet.has(p.id))
        .reduce((acc, p) => acc + (Number(p.valor) || 0), 0),
    [liberadas, selecionadosSet],
  );

  function toggle(id: number) {
    setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  function abrirPagar(ids: number[]) {
    setPagarIds(ids);
    setFormaPagamento("PIX");
    setDataPagamento("");
    setPagarOpen(true);
  }

  const pagarM = useMutation({
    mutationFn: async () => {
      let ok = 0;
      const erros: string[] = [];
      for (const id of pagarIds) {
        try {
          // eslint-disable-next-line no-await-in-loop -- lote intencionalmente sequencial (evita corrida no caixa)
          await api.pagamentos.parcelas.pagar(id, {
            forma_pagamento: formaPagamento,
            data_pagamento: dataPagamento || null,
          });
          ok += 1;
        } catch (e) {
          erros.push((e as Error).message);
        }
      }
      return { ok, total: pagarIds.length, erros };
    },
    onSuccess: (res) => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      if (res.erros.length === 0) {
        toast.success(`${res.ok} parcela(s) paga(s).`);
      } else {
        toast.error(`${res.ok}/${res.total} pagas — ${res.erros.length} falharam: ${res.erros[0]}`);
      }
      setSelecionados((cur) => cur.filter((id) => !pagarIds.includes(id)));
      setPagarOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const revogarM = useMutation({
    mutationFn: (vars: { id: number; justificativa: string }) =>
      api.pagamentos.parcelas.revogarLiberacao(vars.id, vars.justificativa),
    onSuccess: () => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      toast.success("Liberação revogada — parcela volta para a fila de liberação.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function revogar(p: ParcelaTesourariaItem) {
    const j = await prompt({
      title: "Revogar liberação",
      message: `A parcela ${p.numero}/${p.qtd_parcelas} de ${p.nome_fornecedor} volta para a fila de liberação.`,
      label: "Justificativa",
      required: true,
      confirmLabel: "Revogar",
    });
    if (j) revogarM.mutate({ id: p.id, justificativa: j });
  }

  if (!filaQ.isLoading && liberadas.length === 0) {
    return (
      <EmptyState
        icon={Banknote}
        title="Nada aguardando liberação"
        description="Autorize despesas na aba Despesa e libere pagamentos na aba Pagamento das Autorizações — as parcelas liberadas aparecem aqui."
      />
    );
  }

  const ordemBuckets: Urgencia[] = ["atrasadas", "hoje", "semana", "depois"];

  return (
    <div className="space-y-4 pb-24">
      {ordemBuckets.map((bucket) => {
        const itens = grupos[bucket];
        if (itens.length === 0) return null;
        return (
          <section key={bucket} className="space-y-2">
            <h2
              className={cn(
                "text-sm font-semibold uppercase tracking-wide",
                bucket === "atrasadas" ? "text-danger-soft-foreground" : "text-muted-foreground",
              )}
            >
              {BUCKET_LABEL[bucket]} <span className="tabular-nums">({itens.length})</span>
            </h2>
            <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
              {itens.map((p) => (
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
                      <span className="truncate text-xs text-muted-foreground" title={p.descricao_debito}>
                        {p.descricao_debito}
                      </span>
                      {p.vencida && <Badge intent="danger">vencida há {p.dias_atraso}d</Badge>}
                    </div>
                    <p className="truncate text-xs text-muted-foreground">
                      {p.op_numero && (
                        <>
                          {p.op_id ? (
                            <a
                              href={api.pagamentos.ordens.pdfUrl(p.op_id)}
                              target="_blank"
                              rel="noopener"
                              className="inline-flex items-center gap-0.5 hover:text-foreground hover:underline"
                            >
                              {p.op_numero}
                              <FileText className="h-3 w-3" aria-hidden="true" />
                            </a>
                          ) : (
                            p.op_numero
                          )}
                          {" · "}
                        </>
                      )}
                      {p.liberado_por
                        ? `liberado por ${p.liberado_por} em ${fmtDataCurta(p.data_liberacao)}`
                        : "liberação sem registro de usuário"}
                      {p.data_prevista_pagamento && <> · previsto {fmtData(p.data_prevista_pagamento)}</>}
                    </p>
                  </div>
                  <p className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
                    {fmtMoeda(p.valor)}
                  </p>
                  <div className="flex shrink-0 items-center gap-1">
                    <Button size="sm" onClick={() => abrirPagar([p.id])}>
                      Pagar
                    </Button>
                    <button
                      type="button"
                      onClick={() => revogar(p)}
                      disabled={revogarM.isPending}
                      aria-label={`Revogar liberação de ${p.nome_fornecedor}`}
                      title="Revogar liberação"
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                    >
                      <Undo2 className="h-4 w-4" aria-hidden="true" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>
        );
      })}

      {selecionados.length > 0 && (
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-1 px-4 py-3 shadow-md sm:mx-0 sm:rounded-lg sm:border">
          <p className="text-sm text-foreground">
            <span className="font-semibold">{selecionados.length}</span> selecionada(s) — Σ{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>
          </p>
          <Button onClick={() => abrirPagar(selecionados)}>Pagar selecionadas</Button>
        </div>
      )}

      <Dialog
        open={pagarOpen}
        onClose={() => setPagarOpen(false)}
        title={pagarIds.length > 1 ? `Pagar ${pagarIds.length} parcelas` : "Pagar parcela"}
        size="sm"
        footer={
          <>
            <Button variant="secondary" onClick={() => setPagarOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => pagarM.mutate()} disabled={pagarM.isPending}>
              {pagarM.isPending ? "Salvando..." : "Confirmar pagamento"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <Label htmlFor="tes-forma" required>
              Forma de pagamento
            </Label>
            <Select
              id="tes-forma"
              value={formaPagamento}
              onChange={(e) => setFormaPagamento(e.target.value)}
              required
            >
              <option value="PIX">PIX</option>
              <option value="TED">TED</option>
              <option value="BOLETO">Boleto</option>
              <option value="DINHEIRO">Dinheiro</option>
              <option value="OUTRO">Outro</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="tes-data">Data do pagamento (opcional)</Label>
            <Input
              id="tes-data"
              type="date"
              value={dataPagamento}
              onChange={(e) => setDataPagamento(e.target.value)}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab "OPs emitidas" — movida da tela de Autorizações.
// ---------------------------------------------------------------------------

function TabOps() {
  const ordensQ = useQuery({
    queryKey: ["pag-ops"],
    queryFn: () => api.pagamentos.ordens.list(),
  });

  const ordens = ordensQ.data ?? [];
  const ordensExibidas = ordens.slice(0, MAX_ORDENS);

  if (!ordensQ.isLoading && ordens.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="Nenhuma ordem de pagamento emitida"
        description="Autorize despesas na aba Despesa das Autorizações para gerar a primeira OP."
      />
    );
  }

  return (
    <div className="space-y-3">
      {/* Export da LISTA (C1.3). Não confundir com o `pdfUrl` de cada linha:
          aquele é a OP individual, este é o relatório de todas. */}
      <div className="flex justify-end">
        <BotoesExportar
          csvUrl={api.pagamentos.ordens.listaCsvUrl()}
          pdfUrl={api.pagamentos.ordens.listaPdfUrl()}
          rotulo="ordens de pagamento"
        />
      </div>
      <div className="overflow-hidden rounded-lg border border-border bg-surface-1">
      <Table variant="flat">
        <THead>
          <TR>
            <TH>Número</TH>
            <TH>Data</TH>
            <TH>Autorizador</TH>
            <TH className="text-right">Qtd. débitos</TH>
            <TH className="text-right">Valor total</TH>
            <TH>PDF</TH>
          </TR>
        </THead>
        <TBody>
          {ordensExibidas.map((op) => (
            <TR key={op.id}>
              <TD className="font-medium">{op.numero}</TD>
              <TD className="whitespace-nowrap">{fmtDataHora(op.criado_em)}</TD>
              <TD>{op.nome_autorizador ?? "—"}</TD>
              <TD className="text-right tabular-nums">{op.qtd_debitos}</TD>
              <TD className="whitespace-nowrap text-right tabular-nums">{fmtMoeda(op.valor_total)}</TD>
              <TD>
                <a
                  href={api.pagamentos.ordens.pdfUrl(op.id)}
                  target="_blank"
                  rel="noopener"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  <FileText className="h-3.5 w-3.5" aria-hidden="true" />
                  PDF
                </a>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
      {ordens.length > MAX_ORDENS && (
        <p className="px-4 py-2 text-xs text-muted-foreground">
          + {ordens.length - MAX_ORDENS} anteriores
        </p>
      )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tab "Pagas recentemente" — últimas 15, com Estornar.
// ---------------------------------------------------------------------------

function TabPagas() {
  const qc = useQueryClient();
  const toast = useToast();
  const prompt = usePrompt();

  const filaQ = useQuery({
    queryKey: ["pag-fila-tesouraria"],
    queryFn: () => api.pagamentos.filas.tesouraria(),
  });

  const pagas = filaQ.data?.pagas_recentes ?? [];

  const estornarM = useMutation({
    mutationFn: (vars: { id: number; justificativa: string }) =>
      api.pagamentos.parcelas.estornar(vars.id, vars.justificativa),
    onSuccess: () => {
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      toast.success("Parcela estornada — volta para a fila de liberação.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function estornar(p: ParcelaTesourariaItem) {
    const j = await prompt({
      title: "Estornar parcela",
      message: `A parcela ${p.numero}/${p.qtd_parcelas} de ${p.nome_fornecedor} volta para A pagar (será preciso liberar novamente).`,
      label: "Justificativa",
      required: true,
      confirmLabel: "Estornar",
    });
    if (j) estornarM.mutate({ id: p.id, justificativa: j });
  }

  if (!filaQ.isLoading && pagas.length === 0) {
    return (
      <EmptyState
        icon={Banknote}
        title="Nenhum pagamento recente"
        description="As últimas parcelas pagas pela tesouraria aparecem aqui."
      />
    );
  }

  return (
    <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
      {pagas.map((p) => (
        <div key={p.id} className="flex items-center gap-3 px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="truncate font-semibold text-foreground" title={p.nome_fornecedor}>
                {p.nome_fornecedor}
              </span>
              <span className="truncate text-xs text-muted-foreground" title={p.descricao_debito}>
                {p.descricao_debito}
              </span>
            </div>
            <p className="truncate text-xs text-muted-foreground">
              parcela {p.numero}/{p.qtd_parcelas} · pago em {fmtData(p.data_pagamento)}
            </p>
          </div>
          <p className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
            {fmtMoeda(p.valor)}
          </p>
          <Button
            size="sm"
            variant="danger"
            onClick={() => estornar(p)}
            disabled={estornarM.isPending}
          >
            Estornar
          </Button>
        </div>
      ))}
    </div>
  );
}

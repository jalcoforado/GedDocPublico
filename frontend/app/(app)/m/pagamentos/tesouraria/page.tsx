"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Banknote, ChevronDown, ChevronRight, FileText, Paperclip, Send, Upload, XCircle,
} from "lucide-react";
import { useMemo, useState } from "react";

import { fmtData, fmtDataHora, fmtMoeda } from "@/components/pagamentos/format";
import { RitoPagamento } from "@/components/pagamentos/RitoPagamento";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { TabList, TabPanel, Tabs } from "@/components/ui/tabs";
import {
  api,
  type ContaBancaria,
  type LoteDetalhe,
  type LotePagamento,
  type Parcela,
  type RetornoParcelaInput,
  type SituacaoLote,
} from "@/lib/api";
import { BotoesExportar } from "@/components/pagamentos/BotoesExportar";

type TabId = "selecionar" | "lotes" | "ops";

const MAX_ORDENS = 15;

const INVALIDATE_KEYS = [
  ["pag-lotes"],
  ["pag-lotes-elegiveis"],
  ["pag-caixa-painel"],
] as const;

const SITUACAO_LOTE_INTENT: Record<SituacaoLote, "neutral" | "info" | "warning" | "success" | "danger"> = {
  RASCUNHO: "neutral",
  PROGRAMADO: "info",
  ENVIADO: "warning",
  PROCESSADO: "success",
  CANCELADO: "danger",
};

const SITUACAO_LOTE_ROTULO: Record<SituacaoLote, string> = {
  RASCUNHO: "Rascunho",
  PROGRAMADO: "Programado",
  ENVIADO: "Enviado ao banco",
  PROCESSADO: "Processado",
  CANCELADO: "Cancelado",
};

export default function TesourariaPage() {
  const [tab, setTab] = useState<TabId>("selecionar");

  return (
    <Tabs value={tab} onChange={(v) => setTab(v as TabId)} className="space-y-4">
      <PageHeader
        icon={Banknote}
        title="Tesouraria"
        description="Central da execução: selecione parcelas liberadas, monte o lote e acompanhe até o retorno do banco."
        tabs={
          <TabList
            aria-label="Seção da tesouraria"
            variant="pill"
            tabs={[
              { value: "selecionar", label: "Selecionar e criar lote" },
              { value: "lotes", label: "Lotes" },
              { value: "ops", label: "OPs emitidas" },
            ]}
          />
        }
      />

      <RitoPagamento atual="pagar" />

      <TabPanel value="selecionar">
        <TabSelecionar onLoteCriado={() => setTab("lotes")} />
      </TabPanel>
      <TabPanel value="lotes">
        <TabLotes />
      </TabPanel>
      <TabPanel value="ops">
        <TabOps />
      </TabPanel>
    </Tabs>
  );
}

// ---------------------------------------------------------------------------
// "Selecionar e criar lote" — 1º e 2º passos da Central (spec §7.6).
// ---------------------------------------------------------------------------

function TabSelecionar({ onLoteCriado }: { onLoteCriado: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [contaId, setContaId] = useState<number | "">("");
  const [selecionadas, setSelecionadas] = useState<number[]>([]);

  const contasQ = useQuery({
    queryKey: ["pag-contas-tesouraria"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const contas = (contasQ.data ?? []).filter((c: ContaBancaria) => c.ativa);

  const elegiveisQ = useQuery({
    queryKey: ["pag-lotes-elegiveis", contaId],
    queryFn: () => api.pagamentos.lotes.elegiveis(contaId === "" ? undefined : contaId),
  });
  const elegiveis = elegiveisQ.data ?? [];
  const selecionadasSet = useMemo(() => new Set(selecionadas), [selecionadas]);

  const somaSelecionadas = useMemo(
    () =>
      elegiveis
        .filter((p) => selecionadasSet.has(p.id))
        .reduce((acc, p) => acc + (Number(p.valor) || 0), 0),
    [elegiveis, selecionadasSet],
  );

  function toggle(id: number) {
    setSelecionadas((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  const criarLoteM = useMutation({
    mutationFn: () => {
      if (contaId === "") throw new Error("Selecione a conta pagadora");
      return api.pagamentos.lotes.criar({ id_conta_pagadora: contaId, parcela_ids: selecionadas });
    },
    onSuccess: (lote: LotePagamento) => {
      toast.success(`Lote ${lote.numero} criado com ${selecionadas.length} parcela(s).`);
      setSelecionadas([]);
      INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
      onLoteCriado();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="space-y-4 pb-24">
      <div className="max-w-sm">
        <FormField label="Conta pagadora" required>
          <Select
            value={contaId === "" ? "" : String(contaId)}
            onChange={(e) => {
              setContaId(e.target.value ? Number(e.target.value) : "");
              setSelecionadas([]);
            }}
          >
            <option value="">Selecione…</option>
            {contas.map((c: ContaBancaria) => (
              <option key={c.id} value={c.id}>
                {c.nome} — {c.banco}/{c.agencia}
              </option>
            ))}
          </Select>
        </FormField>
      </div>

      {contaId === "" ? (
        <EmptyState
          icon={Banknote}
          title="Escolha uma conta pagadora"
          description="As parcelas liberadas e disponíveis para lote aparecem depois de escolher a conta."
        />
      ) : elegiveisQ.isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : elegiveis.length === 0 ? (
        <EmptyState
          icon={Banknote}
          title="Nada elegível nesta conta"
          description="Libere pagamentos na fila de liberação das Autorizações para que apareçam aqui."
        />
      ) : (
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface-1">
          {elegiveis.map((p: Parcela) => (
            <div key={p.id} className="flex items-center gap-3 px-4 py-3">
              <input
                type="checkbox"
                checked={selecionadasSet.has(p.id)}
                onChange={() => toggle(p.id)}
                aria-label={`Selecionar parcela ${p.numero} do débito #${p.id_debito}`}
                className="h-5 w-5 shrink-0 cursor-pointer rounded border-input text-primary focus:ring-2 focus:ring-ring"
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  Débito #{p.id_debito} · parcela {p.numero}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  vencimento {fmtData(p.vencimento)}
                  {p.data_prevista_pagamento && <> · previsto {fmtData(p.data_prevista_pagamento)}</>}
                </p>
              </div>
              <p className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
                {fmtMoeda(p.valor)}
              </p>
            </div>
          ))}
        </div>
      )}

      {selecionadas.length > 0 && (
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-between gap-3 border-t border-border bg-surface-1 px-4 py-3 shadow-md sm:mx-0 sm:rounded-lg sm:border">
          <p className="text-sm text-foreground">
            <span className="font-semibold">{selecionadas.length}</span> selecionada(s) — Σ{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(String(somaSelecionadas))}</span>
          </p>
          <Button onClick={() => criarLoteM.mutate()} disabled={criarLoteM.isPending}>
            {criarLoteM.isPending ? "Criando…" : "Criar lote"}
          </Button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// "Lotes" — lista + detalhe inline com as ações de cada estágio.
// ---------------------------------------------------------------------------

function TabLotes() {
  const [expandido, setExpandido] = useState<number | null>(null);

  const lotesQ = useQuery({
    queryKey: ["pag-lotes"],
    queryFn: () => api.pagamentos.lotes.listar(),
  });
  const lotes = lotesQ.data ?? [];

  if (!lotesQ.isLoading && lotes.length === 0) {
    return (
      <EmptyState
        icon={Banknote}
        title="Nenhum lote criado ainda"
        description="Monte o primeiro lote na aba Selecionar e criar lote."
      />
    );
  }

  return (
    <div className="space-y-2 pb-12">
      {lotes.map((lote: LotePagamento) => (
        <div key={lote.id} className="overflow-hidden rounded-lg border border-border bg-surface-1">
          <button
            type="button"
            onClick={() => setExpandido((cur) => (cur === lote.id ? null : lote.id))}
            className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted/40"
            aria-expanded={expandido === lote.id}
          >
            {expandido === lote.id ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            )}
            <span className="min-w-0 flex-1">
              <span className="font-semibold text-foreground">{lote.numero}</span>{" "}
              <span className="text-xs text-muted-foreground">criado em {fmtDataHora(lote.criado_em)}</span>
            </span>
            <Badge intent={SITUACAO_LOTE_INTENT[lote.situacao]}>{SITUACAO_LOTE_ROTULO[lote.situacao]}</Badge>
            <span className="shrink-0 whitespace-nowrap text-sm font-semibold tabular-nums text-foreground">
              {fmtMoeda(lote.valor_total)}
            </span>
          </button>
          {expandido === lote.id && <LoteDetalheInline loteId={lote.id} />}
        </div>
      ))}
    </div>
  );
}

function LoteDetalheInline({ loteId }: { loteId: number }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [dataProgramada, setDataProgramada] = useState("");
  const [retornos, setRetornos] = useState<Record<number, { resultado: "PAGA" | "FALHOU"; motivo: string }>>({});
  const [comprovanteArquivo, setComprovanteArquivo] = useState<File | null>(null);

  const loteQ = useQuery({
    queryKey: ["pag-lote", loteId],
    queryFn: () => api.pagamentos.lotes.obter(loteId),
  });
  const lote = loteQ.data as LoteDetalhe | undefined;

  function invalidar() {
    INVALIDATE_KEYS.forEach((key) => qc.invalidateQueries({ queryKey: key }));
    qc.invalidateQueries({ queryKey: ["pag-lote", loteId] });
  }

  const removerParcelaM = useMutation({
    mutationFn: (parcelaId: number) => api.pagamentos.lotes.removerParcela(loteId, parcelaId),
    onSuccess: () => { toast.success("Parcela removida do lote"); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const cancelarM = useMutation({
    mutationFn: () => api.pagamentos.lotes.cancelar(loteId),
    onSuccess: () => { toast.success("Lote cancelado — parcelas liberadas para um novo lote."); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const programarM = useMutation({
    mutationFn: () => api.pagamentos.lotes.programar(loteId, dataProgramada),
    onSuccess: () => { toast.success("Lote programado"); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const enviarM = useMutation({
    mutationFn: () => api.pagamentos.lotes.enviar(loteId),
    onSuccess: () => { toast.success("Lote enviado ao banco"); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const retornoM = useMutation({
    mutationFn: () => {
      const pendentes = (lote?.parcelas ?? []).filter((p) => p.situacao === "PENDENTE");
      const payload: RetornoParcelaInput[] = pendentes.map((p) => {
        const decisao = retornos[p.id_parcela] ?? { resultado: "PAGA" as const, motivo: "" };
        return {
          parcela_id: p.id_parcela,
          resultado: decisao.resultado,
          motivo_falha: decisao.resultado === "FALHOU" ? decisao.motivo : undefined,
        };
      });
      return api.pagamentos.lotes.processarRetorno(loteId, payload);
    },
    onSuccess: () => { toast.success("Retorno registrado"); setRetornos({}); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  const comprovanteM = useMutation({
    mutationFn: () => {
      if (!comprovanteArquivo) throw new Error("Selecione um arquivo");
      return api.pagamentos.lotes.anexarComprovante(loteId, comprovanteArquivo);
    },
    onSuccess: () => { toast.success("Comprovante anexado"); setComprovanteArquivo(null); invalidar(); },
    onError: (e: Error) => toast.error(e.message),
  });

  if (loteQ.isLoading || !lote) {
    return <div className="border-t border-border p-4"><Skeleton className="h-24 w-full" /></div>;
  }

  return (
    <div className="space-y-4 border-t border-border p-4">
      <div className="overflow-x-auto">
        <Table variant="flat">
          <THead>
            <TR>
              <TH>Parcela</TH>
              <TH>Situação</TH>
              {lote.situacao === "ENVIADO" && <TH>Retorno</TH>}
              {lote.situacao === "RASCUNHO" && <TH className="text-right">Ações</TH>}
            </TR>
          </THead>
          <TBody>
            {lote.parcelas.map((p) => (
              <TR key={p.id}>
                <TD>Parcela #{p.id_parcela}</TD>
                <TD>
                  <Badge
                    intent={p.situacao === "PAGA" ? "success" : p.situacao === "FALHOU" ? "danger" : "neutral"}
                  >
                    {p.situacao}
                  </Badge>
                  {p.motivo_falha && <p className="text-xs text-muted-foreground">{p.motivo_falha}</p>}
                </TD>
                {lote.situacao === "ENVIADO" && (
                  <TD>
                    {p.situacao === "PENDENTE" ? (
                      <div className="flex items-center gap-2">
                        <Select
                          value={retornos[p.id_parcela]?.resultado ?? "PAGA"}
                          onChange={(e) =>
                            setRetornos((cur) => ({
                              ...cur,
                              [p.id_parcela]: {
                                resultado: e.target.value as "PAGA" | "FALHOU",
                                motivo: cur[p.id_parcela]?.motivo ?? "",
                              },
                            }))
                          }
                        >
                          <option value="PAGA">Pago</option>
                          <option value="FALHOU">Falhou</option>
                        </Select>
                        {retornos[p.id_parcela]?.resultado === "FALHOU" && (
                          <Input
                            placeholder="Motivo da falha"
                            value={retornos[p.id_parcela]?.motivo ?? ""}
                            onChange={(e) =>
                              setRetornos((cur) => ({
                                ...cur,
                                [p.id_parcela]: { resultado: "FALHOU", motivo: e.target.value },
                              }))
                            }
                          />
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">já resolvida</span>
                    )}
                  </TD>
                )}
                {lote.situacao === "RASCUNHO" && (
                  <TD className="text-right">
                    <Button
                      variant="ghost" size="sm"
                      onClick={() => removerParcelaM.mutate(p.id_parcela)}
                      disabled={removerParcelaM.isPending}
                    >
                      Remover
                    </Button>
                  </TD>
                )}
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      {lote.situacao === "RASCUNHO" && (
        <div className="flex flex-wrap items-end gap-3">
          <FormField label="Data programada" required>
            <Input type="date" value={dataProgramada} onChange={(e) => setDataProgramada(e.target.value)} />
          </FormField>
          <Button onClick={() => programarM.mutate()} disabled={!dataProgramada || programarM.isPending}>
            Programar
          </Button>
          <Button variant="danger" onClick={() => cancelarM.mutate()} disabled={cancelarM.isPending}>
            <XCircle className="mr-1 h-4 w-4" aria-hidden="true" />
            Cancelar lote
          </Button>
        </div>
      )}

      {lote.situacao === "PROGRAMADO" && (
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => enviarM.mutate()} disabled={enviarM.isPending}>
            <Send className="mr-1 h-4 w-4" aria-hidden="true" />
            {enviarM.isPending ? "Enviando…" : "Enviar ao banco"}
          </Button>
          <Button variant="danger" onClick={() => cancelarM.mutate()} disabled={cancelarM.isPending}>
            <XCircle className="mr-1 h-4 w-4" aria-hidden="true" />
            Cancelar lote
          </Button>
        </div>
      )}

      {lote.situacao === "ENVIADO" && (
        <div className="space-y-3 border-t border-border pt-3">
          <Button onClick={() => retornoM.mutate()} disabled={retornoM.isPending}>
            {retornoM.isPending ? "Registrando…" : "Registrar retorno"}
          </Button>
          <div className="flex flex-wrap items-end gap-2">
            <FormField label="Comprovante da remessa" hint="PDF do protocolo bancário, opcional">
              <input
                type="file"
                onChange={(e) => setComprovanteArquivo(e.target.files?.[0] ?? null)}
                className="block text-sm text-foreground file:mr-3 file:rounded-md file:border-0 file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:file:bg-muted/80"
              />
            </FormField>
            <Button
              variant="secondary" size="sm"
              onClick={() => comprovanteM.mutate()}
              disabled={!comprovanteArquivo || comprovanteM.isPending}
            >
              <Upload className="mr-1 h-4 w-4" aria-hidden="true" />
              Anexar
            </Button>
          </div>
        </div>
      )}

      {(lote.situacao === "PROCESSADO" || lote.id_anexo_comprovante) && lote.id_anexo_comprovante && (
        <a
          href={api.pagamentos.lotes.comprovanteDownloadUrl(lote.id)}
          target="_blank"
          rel="noopener"
          className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <Paperclip className="h-4 w-4" aria-hidden="true" />
          Ver comprovante
        </a>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// "OPs emitidas" — inalterada da versão anterior.
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

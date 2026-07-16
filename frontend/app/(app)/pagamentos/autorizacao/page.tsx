"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { PageHeader } from "@/components/ui/page-header";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type Debito, type OrdemPagamento } from "@/lib/api";

function fmtMoeda(v: string | number): string {
  const n = typeof v === "string" ? Number(v) : v;
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtDataHora(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const data = d.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "2-digit" });
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${data} ${hora}`;
}

const MAX_ORDENS = 15;

export default function AutorizacaoPagamentosPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [selecionados, setSelecionados] = useState<number[]>([]);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const filaQ = useQuery({
    queryKey: ["pag-aut-fila"],
    queryFn: () => api.pagamentos.debitos.list({ status: "APROVADO" }),
  });
  const naturezasQ = useQuery({
    queryKey: ["pag-naturezas"],
    queryFn: () => api.pagamentos.cadastros.naturezas.list(),
  });
  const contasQ = useQuery({
    queryKey: ["pag-contas-select"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const painelQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });
  const ordensQ = useQuery({
    queryKey: ["pag-ops"],
    queryFn: () => api.pagamentos.ordens.list(),
  });

  const debitos = filaQ.data ?? [];
  const painel = painelQ.data ?? [];
  const ordens = ordensQ.data ?? [];

  const naturezaMap = useMemo(() => {
    const m = new Map<number, string>();
    (naturezasQ.data ?? []).forEach((n) => m.set(n.id, n.codigo));
    return m;
  }, [naturezasQ.data]);

  const contaMap = useMemo(() => {
    const m = new Map<number, string>();
    (contasQ.data ?? []).forEach((c) => m.set(c.id, c.nome));
    return m;
  }, [contasQ.data]);

  const disponivelPorConta = useMemo(() => {
    const m = new Map<number, string>();
    painel.forEach((c) => m.set(c.id_conta, c.disponivel));
    return m;
  }, [painel]);

  const selecionadosSet = useMemo(() => new Set(selecionados), [selecionados]);
  const debitosSelecionados = useMemo(
    () => debitos.filter((d) => selecionadosSet.has(d.id)),
    [debitos, selecionadosSet],
  );

  const somaSelecionados = useMemo(
    () => debitosSelecionados.reduce((acc, d) => acc + (Number(d.valor_total) || 0), 0),
    [debitosSelecionados],
  );

  const somaPorConta = useMemo(() => {
    const m = new Map<number, number>();
    debitosSelecionados.forEach((d) => {
      m.set(d.id_conta, (m.get(d.id_conta) ?? 0) + (Number(d.valor_total) || 0));
    });
    return m;
  }, [debitosSelecionados]);

  const algumaContaExcedeSaldo = useMemo(
    () =>
      Array.from(somaPorConta.entries()).some(
        ([idConta, valor]) => valor > Number(disponivelPorConta.get(idConta) ?? "0"),
      ),
    [somaPorConta, disponivelPorConta],
  );

  const todosSelecionados = debitos.length > 0 && debitos.every((d) => selecionadosSet.has(d.id));

  function toggleTodos() {
    if (todosSelecionados) {
      setSelecionados([]);
    } else {
      setSelecionados(debitos.map((d) => d.id));
    }
  }

  function toggle(id: number) {
    setSelecionados((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }

  const autorizarM = useMutation({
    mutationFn: () => api.pagamentos.autorizar(selecionados),
    onSuccess: (op: OrdemPagamento) => {
      qc.invalidateQueries({ queryKey: ["pag-aut-fila"] });
      qc.invalidateQueries({ queryKey: ["pag-ops"] });
      qc.invalidateQueries({ queryKey: ["pag-fila"] });
      qc.invalidateQueries({ queryKey: ["pag-debitos"] });
      qc.invalidateQueries({ queryKey: ["pag-caixa-painel"] });
      toast.success(`OP ${op.numero} gerada — ${fmtMoeda(op.valor_total)}`, {
        action: {
          label: "Abrir PDF",
          onClick: () => window.open(api.pagamentos.ordens.pdfUrl(op.id), "_blank", "noopener"),
        },
      });
      setSelecionados([]);
      setConfirmOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const ordensExibidas = ordens.slice(0, MAX_ORDENS);

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ShieldCheck}
        title="Autorização de pagamentos"
        description="Revise os débitos aprovados e autorize em lote, gerando a Ordem de Pagamento (art. 64, Lei 4.320/64)."
      />

      {/* Disponível por conta */}
      <div className="flex flex-wrap gap-2">
        {painel.length === 0 && !painelQ.isLoading && (
          <p className="text-sm text-muted-foreground">Nenhuma conta cadastrada.</p>
        )}
        {painel.map((c) => (
          <div
            key={c.id_conta}
            className="min-w-0 max-w-[220px] rounded-md border border-border bg-surface-1 px-3 py-1.5"
          >
            <p className="truncate text-xs text-muted-foreground" title={c.nome}>
              {c.nome}
            </p>
            <p className="tabular-nums text-sm font-semibold text-foreground">
              {fmtMoeda(c.disponivel)}
            </p>
          </div>
        ))}
      </div>

      {/* Fila de aprovados */}
      <Card>
        <CardHeader>
          <CardTitle>Fila de aprovados</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table variant="flat">
            <THead>
              <TR>
                <TH className="w-8">
                  <input
                    type="checkbox"
                    checked={todosSelecionados}
                    onChange={toggleTodos}
                    aria-label="Selecionar todos"
                    disabled={debitos.length === 0}
                  />
                </TH>
                <TH>Fornecedor</TH>
                <TH>Descrição</TH>
                <TH>Natureza</TH>
                <TH>Conta</TH>
                <TH>Competência</TH>
                <TH className="text-right">Valor</TH>
              </TR>
            </THead>
            <TBody>
              {!filaQ.isLoading && debitos.length === 0 && (
                <TR>
                  <TD colSpan={7} className="py-6 text-center text-sm text-muted-foreground">
                    Nenhum débito aguardando autorização.
                  </TD>
                </TR>
              )}
              {debitos.map((d: Debito) => (
                <TR key={d.id}>
                  <TD>
                    <input
                      type="checkbox"
                      checked={selecionadosSet.has(d.id)}
                      onChange={() => toggle(d.id)}
                      aria-label={`Selecionar ${d.nome_fornecedor}`}
                    />
                  </TD>
                  <TD className="max-w-[160px]">
                    <Link
                      href={`/pagamentos/contas-a-pagar/${d.id}`}
                      className="block truncate whitespace-nowrap text-primary hover:underline"
                      title={d.nome_fornecedor}
                    >
                      {d.nome_fornecedor}
                    </Link>
                  </TD>
                  <TD className="max-w-[200px]">
                    <span className="block truncate whitespace-nowrap" title={d.descricao}>
                      {d.descricao}
                    </span>
                  </TD>
                  <TD>{naturezaMap.get(d.id_natureza) ?? "—"}</TD>
                  <TD className="max-w-[140px]">
                    <span className="block truncate whitespace-nowrap" title={contaMap.get(d.id_conta) ?? ""}>
                      {contaMap.get(d.id_conta) ?? "—"}
                    </span>
                  </TD>
                  <TD>{d.competencia}</TD>
                  <TD className="whitespace-nowrap text-right tabular-nums">
                    <div className="flex items-center justify-end gap-1">
                      {d.urgente && <Badge intent="danger">URGENTE</Badge>}
                      {fmtMoeda(d.valor_total)}
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </CardContent>
      </Card>

      {/* Barra de seleção */}
      {selecionados.length > 0 && (
        <div className="sticky bottom-4 z-10 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-surface-1 px-4 py-3 shadow-md">
          <p className="text-sm text-foreground">
            <span className="font-semibold">{selecionados.length}</span> selecionado(s) —{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>
          </p>
          <Button onClick={() => setConfirmOpen(true)}>Autorizar selecionados (gerar OP)</Button>
        </div>
      )}

      {/* Ordens de pagamento emitidas */}
      <Card>
        <CardHeader>
          <CardTitle>Ordens de pagamento emitidas</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
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
              {!ordensQ.isLoading && ordens.length === 0 && (
                <TR>
                  <TD colSpan={6} className="py-6 text-center text-sm text-muted-foreground">
                    Nenhuma ordem de pagamento emitida.
                  </TD>
                </TR>
              )}
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
                      className="text-primary hover:underline"
                    >
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
        </CardContent>
      </Card>

      {/* Dialog de confirmação */}
      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Confirmar autorização de pagamento"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirmOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => autorizarM.mutate()} disabled={autorizarM.isPending}>
              {autorizarM.isPending ? "Autorizando..." : "Confirmar e gerar OP"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Você está autorizando <span className="font-semibold">{selecionados.length}</span> débito(s),
            totalizando{" "}
            <span className="font-semibold tabular-nums">{fmtMoeda(somaSelecionados)}</span>. Esta ação
            gera uma Ordem de Pagamento e não pode ser desfeita.
          </p>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Por conta
            </p>
            {Array.from(somaPorConta.entries()).map(([idConta, valor]) => {
              const disponivel = Number(disponivelPorConta.get(idConta) ?? "0");
              const excede = valor > disponivel;
              return (
                <div
                  key={idConta}
                  className={
                    "flex items-center justify-between rounded-md border px-3 py-2 text-sm " +
                    (excede
                      ? "border-warning/40 bg-warning-soft text-warning-soft-foreground"
                      : "border-border bg-surface-1 text-foreground")
                  }
                >
                  <span className="min-w-0 truncate" title={contaMap.get(idConta) ?? ""}>
                    {contaMap.get(idConta) ?? `Conta #${idConta}`}
                  </span>
                  <span className="shrink-0 whitespace-nowrap tabular-nums">
                    {fmtMoeda(valor)} de {fmtMoeda(disponivel)} disponível
                  </span>
                </div>
              );
            })}
            {algumaContaExcedeSaldo && (
              <p className="text-xs text-warning-soft-foreground">
                Atenção: alguma conta selecionada não tem saldo disponível suficiente — o backend
                recusará a autorização por saldo insuficiente.
              </p>
            )}
          </div>
        </div>
      </Dialog>
    </div>
  );
}

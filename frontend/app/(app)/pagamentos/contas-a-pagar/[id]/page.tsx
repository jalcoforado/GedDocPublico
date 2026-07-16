"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { usePrompt } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { RitoPagamento, type PassoRito } from "@/components/pagamentos/RitoPagamento";
import { fmtDataCurta } from "@/components/pagamentos/format";
import { useAuth } from "@/lib/auth";
import { api, type Parcela, type StatusDebito } from "@/lib/api";

// Passos do rito já concluídos + próximo passo pendente, derivados do status do débito.
const RITO_POR_STATUS: Record<StatusDebito, { concluidos: PassoRito[]; atual?: PassoRito }> = {
  RASCUNHO: { concluidos: [], atual: "solicitar" },
  AGUARDANDO_APROVACAO: { concluidos: ["solicitar"], atual: "aprovar" },
  APROVADO: { concluidos: ["solicitar", "aprovar"], atual: "autorizar" },
  AUTORIZADO: { concluidos: ["solicitar", "aprovar", "autorizar"], atual: "liberar" },
  PAGO_PARCIAL: { concluidos: ["solicitar", "aprovar", "autorizar"], atual: "pagar" },
  PAGO: { concluidos: ["solicitar", "aprovar", "autorizar", "liberar", "pagar"] },
  REJEITADO: { concluidos: ["solicitar"] },
  CANCELADO: { concluidos: [] },
};

function fmtMoeda(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function fmtData(v: string | null): string {
  if (!v) return "—";
  const d = new Date(v.length <= 10 ? `${v}T00:00:00` : v);
  return d.toLocaleDateString("pt-BR");
}

function fmtDataHora(v: string): string {
  return new Date(v).toLocaleString("pt-BR");
}

const STATUS_BADGE: Record<StatusDebito, { intent: "neutral" | "warning" | "info" | "success" | "danger"; label: string }> = {
  RASCUNHO: { intent: "neutral", label: "Rascunho" },
  AGUARDANDO_APROVACAO: { intent: "warning", label: "Aguardando aprovação" },
  APROVADO: { intent: "info", label: "Aprovado" },
  AUTORIZADO: { intent: "info", label: "Autorizado" },
  PAGO_PARCIAL: { intent: "warning", label: "Pago parcial" },
  PAGO: { intent: "success", label: "Pago" },
  REJEITADO: { intent: "danger", label: "Rejeitado" },
  CANCELADO: { intent: "danger", label: "Cancelado" },
};

function StatusBadge({ status }: { status: StatusDebito }) {
  const cfg = STATUS_BADGE[status];
  return <Badge intent={cfg.intent}>{cfg.label}</Badge>;
}

const PARCELA_STATUS_BADGE: Record<Parcela["status"], { intent: "neutral" | "info" | "success" | "danger"; label: string }> = {
  A_PAGAR: { intent: "neutral", label: "A pagar" },
  LIBERADA: { intent: "info", label: "Liberada" },
  PAGA: { intent: "success", label: "Paga" },
  CANCELADA: { intent: "danger", label: "Cancelada" },
};

export default function DebitoDetalhePage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const qc = useQueryClient();
  const toast = useToast();
  const prompt = usePrompt();
  const { can } = useAuth();

  const [pagarOpen, setPagarOpen] = useState(false);
  const [pagarParcela, setPagarParcela] = useState<Parcela | null>(null);
  const [formaPagamento, setFormaPagamento] = useState("PIX");
  const [dataPagamento, setDataPagamento] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["pag-debito", id] });
    qc.invalidateQueries({ queryKey: ["pag-debitos"] });
  };

  const debitoQ = useQuery({
    queryKey: ["pag-debito", id],
    queryFn: () => api.pagamentos.debitos.get(id),
    enabled: Number.isFinite(id),
  });

  function abrirPagar(p: Parcela) {
    setPagarParcela(p);
    setFormaPagamento("PIX");
    setDataPagamento("");
    setErr(null);
    setPagarOpen(true);
  }

  const enviarM = useMutation({
    mutationFn: () => api.pagamentos.debitos.enviar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Débito enviado para aprovação.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const aprovarM = useMutation({
    mutationFn: () => api.pagamentos.debitos.aprovar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Débito aprovado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const devolverM = useMutation({
    mutationFn: (justificativa: string) => api.pagamentos.debitos.devolver(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Débito devolvido.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const rejeitarM = useMutation({
    mutationFn: (justificativa: string) => api.pagamentos.debitos.rejeitar(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Débito rejeitado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const cancelarM = useMutation({
    mutationFn: (justificativa: string) => api.pagamentos.debitos.cancelar(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Débito cancelado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const autorizarM = useMutation({
    mutationFn: () => api.pagamentos.autorizar([id]),
    onSuccess: (op) => {
      invalidate();
      toast.success(`Débito autorizado. OP ${op.numero} gerada.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const pagarM = useMutation({
    mutationFn: () => {
      if (!pagarParcela) throw new Error("Parcela inválida.");
      return api.pagamentos.parcelas.pagar(pagarParcela.id, {
        forma_pagamento: formaPagamento,
        data_pagamento: dataPagamento || null,
      });
    },
    onSuccess: () => {
      invalidate();
      toast.success("Parcela paga.");
      setPagarOpen(false);
    },
    onError: (e: Error) => {
      setErr(e.message);
      toast.error(e.message);
    },
  });

  const estornarM = useMutation({
    mutationFn: (vars: { parcelaId: number; justificativa: string }) =>
      api.pagamentos.parcelas.estornar(vars.parcelaId, vars.justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Parcela estornada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function devolver() {
    const j = await prompt({
      title: "Devolver débito",
      label: "Justificativa",
      required: true,
      confirmLabel: "Devolver",
    });
    if (j) devolverM.mutate(j);
  }

  async function rejeitar() {
    const j = await prompt({
      title: "Rejeitar débito",
      label: "Justificativa",
      required: true,
      confirmLabel: "Rejeitar",
    });
    if (j) rejeitarM.mutate(j);
  }

  async function cancelar() {
    const j = await prompt({
      title: "Cancelar débito",
      label: "Justificativa",
      required: true,
      confirmLabel: "Cancelar débito",
    });
    if (j) cancelarM.mutate(j);
  }

  async function estornar(p: Parcela) {
    const j = await prompt({
      title: "Estornar parcela",
      label: "Justificativa",
      required: true,
      confirmLabel: "Estornar",
    });
    if (j) estornarM.mutate({ parcelaId: p.id, justificativa: j });
  }

  if (debitoQ.isLoading) {
    return <div className="text-muted-foreground">Carregando…</div>;
  }
  if (debitoQ.error || !debitoQ.data) {
    return (
      <div className="text-danger-soft-foreground">
        Erro ao carregar débito: {(debitoQ.error as Error)?.message ?? "não encontrado"}
      </div>
    );
  }

  const d = debitoQ.data;
  const podePagar = can("pagamento_pagar");

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Link
          href="/pagamentos/contas-a-pagar"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label="Voltar"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-aprimora">{d.nome_fornecedor}</h1>
          <p className="text-sm text-muted-foreground">{d.descricao}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-surface-1 px-4 py-3">
        <RitoPagamento
          atual={RITO_POR_STATUS[d.status].atual}
          concluidos={RITO_POR_STATUS[d.status].concluidos}
        />
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-border bg-surface-1 p-4 sm:grid-cols-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Valor total</p>
          <p className="text-lg font-semibold tabular-nums">{fmtMoeda(d.valor_total)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Competência</p>
          <p className="text-lg font-semibold">{d.competencia}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Status</p>
          <StatusBadge status={d.status} />
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-muted-foreground">Criticidade</p>
          <div className="flex items-center gap-1">
            <span>{d.criticidade}</span>
            {d.urgente && <Badge intent="danger">URGENTE</Badge>}
          </div>
        </div>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Parcelas
        </h2>
        <Table>
          <THead>
            <TR>
              <TH>Nº</TH>
              <TH className="text-right">Valor</TH>
              <TH>Vencimento</TH>
              <TH>Status</TH>
              <TH>Forma</TH>
              <TH>Data pagamento</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {d.parcelas.length === 0 && (
              <TR>
                <TD colSpan={7} className="py-6 text-center text-sm text-muted-foreground">
                  Nenhuma parcela.
                </TD>
              </TR>
            )}
            {d.parcelas.map((p) => (
              <TR key={p.id}>
                <TD>{p.numero}</TD>
                <TD className="text-right tabular-nums">{fmtMoeda(p.valor)}</TD>
                <TD>{fmtData(p.vencimento)}</TD>
                <TD>
                  <Badge intent={PARCELA_STATUS_BADGE[p.status].intent}>
                    {PARCELA_STATUS_BADGE[p.status].label}
                  </Badge>
                  {p.status === "LIBERADA" && p.data_liberacao && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      liberada em {fmtDataCurta(p.data_liberacao)}
                    </p>
                  )}
                </TD>
                <TD>{p.forma_pagamento ?? "—"}</TD>
                <TD>{fmtData(p.data_pagamento)}</TD>
                <TD className="text-right">
                  {p.status === "LIBERADA" && podePagar && (
                    <Button size="sm" onClick={() => abrirPagar(p)}>
                      Pagar
                    </Button>
                  )}
                  {p.status === "A_PAGAR" && (
                    <span className="text-xs text-muted-foreground">
                      aguardando liberação
                    </span>
                  )}
                  {p.status === "PAGA" && podePagar && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => estornar(p)}
                      disabled={estornarM.isPending}
                    >
                      Estornar
                    </Button>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Ações do fluxo
        </h2>
        <div className="flex flex-wrap gap-2">
          {d.status === "RASCUNHO" && can("pagamento_solicitar") && (
            <>
              <Button onClick={() => enviarM.mutate()} disabled={enviarM.isPending}>
                Enviar para aprovação
              </Button>
              <Button variant="danger" onClick={cancelar} disabled={cancelarM.isPending}>
                Cancelar
              </Button>
            </>
          )}
          {d.status === "AGUARDANDO_APROVACAO" && can("pagamento_aprovar") && (
            <>
              <Button onClick={() => aprovarM.mutate()} disabled={aprovarM.isPending}>
                Aprovar
              </Button>
              <Button variant="secondary" onClick={devolver} disabled={devolverM.isPending}>
                Devolver
              </Button>
              <Button variant="danger" onClick={rejeitar} disabled={rejeitarM.isPending}>
                Rejeitar
              </Button>
            </>
          )}
          {d.status === "APROVADO" && can("pagamento_autorizar") && (
            <Button onClick={() => autorizarM.mutate()} disabled={autorizarM.isPending}>
              Autorizar
            </Button>
          )}
          {!(
            (d.status === "RASCUNHO" && can("pagamento_solicitar")) ||
            (d.status === "AGUARDANDO_APROVACAO" && can("pagamento_aprovar")) ||
            (d.status === "APROVADO" && can("pagamento_autorizar"))
          ) && <p className="text-sm text-muted-foreground">Nenhuma ação disponível.</p>}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Trilha
        </h2>
        {d.historico.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sem registros.</p>
        ) : (
          <ul className="space-y-2">
            {d.historico.map((h) => (
              <li
                key={h.id}
                className="rounded border border-border bg-card px-3 py-2 text-sm"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{h.acao}</span>
                  <span className="text-xs text-muted-foreground">
                    {fmtDataHora(h.criado_em)}
                  </span>
                </div>
                {h.status_anterior && (
                  <p className="text-xs text-muted-foreground">
                    {h.status_anterior} → {h.status_novo}
                  </p>
                )}
                {h.justificativa && <p className="mt-1 text-sm">{h.justificativa}</p>}
                {h.nome_usuario && (
                  <p className="mt-1 text-xs text-muted-foreground">{h.nome_usuario}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <Dialog
        open={pagarOpen}
        onClose={() => setPagarOpen(false)}
        title={`Pagar parcela ${pagarParcela?.numero ?? ""}`}
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
            <Label htmlFor="pg-forma" required>
              Forma de pagamento
            </Label>
            <Select
              id="pg-forma"
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
            <Label htmlFor="pg-data">Data do pagamento (opcional)</Label>
            <Input
              id="pg-data"
              type="date"
              value={dataPagamento}
              onChange={(e) => setDataPagamento(e.target.value)}
            />
          </div>
          {err && (
            <div
              role="alert"
              className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}

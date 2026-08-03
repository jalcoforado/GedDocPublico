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
import { DEBITO_STATUS_BADGE } from "@/components/pagamentos/statusDebito";

// Passos do rito já concluídos + próximo passo pendente, derivados do status do débito.
// Rito v2.0 (16 status) mapeado sobre os passos visuais existentes
// (solicitar → validar[aprovar] → autorizar → liberar → pagar).
const RITO_POR_STATUS: Record<StatusDebito, { concluidos: PassoRito[]; atual?: PassoRito }> = {
  RASCUNHO: { concluidos: [], atual: "solicitar" },
  DEVOLVIDO: { concluidos: [], atual: "solicitar" },
  EM_VALIDACAO: { concluidos: ["solicitar"], atual: "aprovar" },
  VALIDADO: { concluidos: ["solicitar", "aprovar"], atual: "autorizar" },
  ENVIADO_SECRETARIO: { concluidos: ["solicitar", "aprovar"], atual: "autorizar" },
  AGUARDANDO_AUTORIZACAO: { concluidos: ["solicitar", "aprovar"], atual: "autorizar" },
  AUTORIZADO: { concluidos: ["solicitar", "aprovar", "autorizar"], atual: "liberar" },
  ENVIADO_TESOURARIA: { concluidos: ["solicitar", "aprovar", "autorizar", "liberar"], atual: "pagar" },
  EM_PROCESSAMENTO: { concluidos: ["solicitar", "aprovar", "autorizar", "liberar"], atual: "pagar" },
  PAGO_PARCIAL: { concluidos: ["solicitar", "aprovar", "autorizar"], atual: "pagar" },
  PAGO: { concluidos: ["solicitar", "aprovar", "autorizar", "liberar", "pagar"] },
  CONCILIADO: { concluidos: ["solicitar", "aprovar", "autorizar", "liberar", "pagar"] },
  ESTORNADO: { concluidos: ["solicitar", "aprovar", "autorizar"], atual: "liberar" },
  REJEITADO: { concluidos: ["solicitar"] },
  CANCELADO: { concluidos: [] },
  SUSPENSO: { concluidos: ["solicitar"] },
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

const STATUS_BADGE = DEBITO_STATUS_BADGE;

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
  const [autorizarOpen, setAutorizarOpen] = useState(false);
  const [contaPagadora, setContaPagadora] = useState<number | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["pag-debito", id] });
    qc.invalidateQueries({ queryKey: ["pag-debitos"] });
    qc.invalidateQueries({ queryKey: ["pag-debito-checklist", id] });
  };

  const debitoQ = useQuery({
    queryKey: ["pag-debito", id],
    queryFn: () => api.pagamentos.debitos.get(id),
    enabled: Number.isFinite(id),
  });

  // RF-VAL-01/06: checklist documental do débito.
  const checklistQ = useQuery({
    queryKey: ["pag-debito-checklist", id],
    queryFn: () => api.pagamentos.debitos.checklist(id),
    enabled: Number.isFinite(id),
  });
  const marcarChecklistM = useMutation({
    mutationFn: (v: { id_checklist_item: number; marcado: boolean }) =>
      api.pagamentos.debitos.marcarChecklist(id, v),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-debito-checklist", id] });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Contas elegíveis para pagar este débito (contas ativas da fonte) — v2.0.
  const fonteDoDebito = debitoQ.data?.id_fonte_recursos;
  const contasElegiveisQ = useQuery({
    queryKey: ["pag-contas-elegiveis", fonteDoDebito],
    queryFn: () => api.pagamentos.contasElegiveis(fonteDoDebito as number),
    enabled: autorizarOpen && fonteDoDebito !== undefined,
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

  const validarM = useMutation({
    mutationFn: () => api.pagamentos.debitos.validar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Débito validado.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const encaminharM = useMutation({
    mutationFn: () => api.pagamentos.debitos.encaminhar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Débito encaminhado à autoridade.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const emProcessamentoM = useMutation({
    mutationFn: () => api.pagamentos.debitos.emProcessamento(id),
    onSuccess: () => {
      invalidate();
      toast.success("Pagamento marcado em processamento.");
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
    mutationFn: () => {
      if (fonteDoDebito === undefined) throw new Error("Fonte do débito indisponível.");
      if (contaPagadora === null) throw new Error("Escolha a conta pagadora.");
      return api.pagamentos.autorizar([
        { id_fonte: fonteDoDebito, id_conta_pagadora: contaPagadora, debito_ids: [id] },
      ]);
    },
    onSuccess: (ops) => {
      invalidate();
      setAutorizarOpen(false);
      setContaPagadora(null);
      const numero = ops[0]?.numero ?? "";
      toast.success(`Débito autorizado. OP ${numero} gerada.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const liquidacaoM = useMutation({
    mutationFn: () => api.pagamentos.debitos.confirmarLiquidacao(id),
    onSuccess: () => {
      invalidate();
      toast.success("Liquidação confirmada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const suspenderM = useMutation({
    mutationFn: (justificativa: string) => api.pagamentos.debitos.suspender(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Débito suspenso.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const reativarM = useMutation({
    mutationFn: (justificativa: string) => api.pagamentos.debitos.reativar(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Débito reativado.");
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

  async function suspender() {
    const j = await prompt({
      title: "Suspender débito",
      label: "Motivo da suspensão",
      required: true,
      confirmLabel: "Suspender",
    });
    if (j) suspenderM.mutate(j);
  }

  async function reativar() {
    const j = await prompt({
      title: "Reativar débito",
      label: "Justificativa",
      required: true,
      confirmLabel: "Reativar",
    });
    if (j) reativarM.mutate(j);
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
          href="/m/pagamentos/contas-a-pagar"
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

      {/* RF-VAL-01/06: checklist documental */}
      {(checklistQ.data?.length ?? 0) > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Checklist documental
          </h2>
          <ul className="space-y-1">
            {checklistQ.data!.map((item) => {
              const editavel = d.status === "EM_VALIDACAO" &&
                (can("pagamento_validar") || can("pagamento_aprovar"));
              return (
                <li key={item.id_checklist_item}
                  className="flex items-center gap-2 rounded border border-border bg-card px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={item.marcado}
                    disabled={!editavel || marcarChecklistM.isPending}
                    onChange={(e) => marcarChecklistM.mutate({
                      id_checklist_item: item.id_checklist_item, marcado: e.target.checked })}
                  />
                  <span className={item.marcado ? "line-through text-muted-foreground" : ""}>
                    {item.descricao}
                    {item.obrigatorio && <span className="ml-1 text-danger">*</span>}
                  </span>
                  {item.observacao && (
                    <span className="ml-auto text-xs text-muted-foreground">{item.observacao}</span>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="text-danger">*</span> obrigatório para validar (RF-VAL-01).
          </p>
        </section>
      )}

      <section>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Ações do fluxo
        </h2>
        <div className="flex flex-wrap gap-2">
          {/* v2.0: liquidação é pré-requisito para validar (RN-01). Validador ou
              autoridade podem confirmá-la nas etapas pré-validação. */}
          {!d.liquidacao_confirmada &&
            ["RASCUNHO", "DEVOLVIDO", "EM_VALIDACAO", "VALIDADO"].includes(d.status) &&
            (can("pagamento_validar") || can("pagamento_aprovar") || can("pagamento_autorizar")) && (
              <Button variant="secondary" onClick={() => liquidacaoM.mutate()}
                disabled={liquidacaoM.isPending}>
                Confirmar liquidação
              </Button>
            )}
          {["RASCUNHO", "DEVOLVIDO"].includes(d.status) && can("pagamento_solicitar") && (
            <>
              <Button onClick={() => enviarM.mutate()} disabled={enviarM.isPending}>
                Enviar para validação
              </Button>
              <Button variant="danger" onClick={cancelar} disabled={cancelarM.isPending}>
                Cancelar
              </Button>
            </>
          )}
          {d.status === "EM_VALIDACAO" && (can("pagamento_validar") || can("pagamento_aprovar")) && (
            <>
              {d.liquidacao_confirmada ? (
                <Button onClick={() => validarM.mutate()} disabled={validarM.isPending}>
                  Validar
                </Button>
              ) : (
                <p className="self-center text-sm text-muted-foreground">
                  Confirme a liquidação antes de validar.
                </p>
              )}
              <Button variant="secondary" onClick={devolver} disabled={devolverM.isPending}>
                Devolver
              </Button>
              <Button variant="danger" onClick={rejeitar} disabled={rejeitarM.isPending}>
                Rejeitar
              </Button>
            </>
          )}
          {d.status === "VALIDADO" && (can("pagamento_encaminhar") || can("pagamento_autorizar")) && (
            <Button onClick={() => encaminharM.mutate()} disabled={encaminharM.isPending}>
              Encaminhar à autoridade
            </Button>
          )}
          {["ENVIADO_SECRETARIO", "AGUARDANDO_AUTORIZACAO"].includes(d.status) &&
            can("pagamento_autorizar") && (
              <Button
                onClick={() => {
                  setContaPagadora(null);
                  setAutorizarOpen(true);
                }}
              >
                Autorizar
              </Button>
            )}
          {/* v2.0: tesouraria marca o pagamento em processamento (RF-TES) */}
          {d.status === "ENVIADO_TESOURARIA" && can("pagamento_pagar") && (
            <Button variant="secondary" onClick={() => emProcessamentoM.mutate()}
              disabled={emProcessamentoM.isPending}>
              Marcar em processamento
            </Button>
          )}
          {/* v2.0: suspende/reativa débito suspeito (RF-TES-06/RF-AUT-17) */}
          {["EM_VALIDACAO", "VALIDADO", "ENVIADO_SECRETARIO", "AGUARDANDO_AUTORIZACAO"].includes(d.status) &&
            can("pagamento_pagar") && (
              <Button variant="danger" onClick={suspender} disabled={suspenderM.isPending}>
                Suspender
              </Button>
            )}
          {d.status === "SUSPENSO" && can("pagamento_pagar") && (
            <Button onClick={reativar} disabled={reativarM.isPending}>
              Reativar
            </Button>
          )}
          {["PAGO", "CONCILIADO", "REJEITADO", "CANCELADO"].includes(d.status) && (
            <p className="text-sm text-muted-foreground">Nenhuma ação disponível.</p>
          )}
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

      <Dialog
        open={autorizarOpen}
        onClose={() => setAutorizarOpen(false)}
        title="Autorizar despesa"
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAutorizarOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => autorizarM.mutate()}
              disabled={contaPagadora === null || autorizarM.isPending}
            >
              {autorizarM.isPending ? "Autorizando..." : "Confirmar e gerar OP"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p className="text-sm text-foreground">
            Escolha a <span className="font-semibold">conta pagadora</span> — apenas contas ativas da
            fonte de recursos deste débito. O valor será reservado nessa conta ao gerar a Ordem de
            Pagamento.
          </p>
          <div>
            <Label htmlFor="autorizar-conta" required>
              Conta pagadora
            </Label>
            <Select
              id="autorizar-conta"
              value={contaPagadora ?? ""}
              onChange={(e) => setContaPagadora(e.target.value ? Number(e.target.value) : null)}
              disabled={contasElegiveisQ.isLoading}
            >
              <option value="" disabled>
                {contasElegiveisQ.isLoading ? "Carregando..." : "Selecione a conta pagadora..."}
              </option>
              {(contasElegiveisQ.data ?? []).map((c) => (
                <option key={c.id_conta} value={c.id_conta}>
                  {c.nome} · {c.banco} ag.{c.agencia} c/{c.conta_mascarada} — disp.{" "}
                  {fmtMoeda(c.disponivel)}
                </option>
              ))}
            </Select>
          </div>
          {!contasElegiveisQ.isLoading && (contasElegiveisQ.data ?? []).length === 0 && (
            <p className="text-xs text-warning-soft-foreground">
              Nenhuma conta ativa nesta fonte — cadastre/ative uma conta para autorizar.
            </p>
          )}
        </div>
      </Dialog>
    </div>
  );
}

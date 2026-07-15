"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";
import { api, type StatusDebito } from "@/lib/api";

function fmtMoeda(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const STATUS_TABS: { value: StatusDebito | ""; label: string }[] = [
  { value: "", label: "Todos" },
  { value: "RASCUNHO", label: "Rascunho" },
  { value: "AGUARDANDO_APROVACAO", label: "Aguardando aprovação" },
  { value: "APROVADO", label: "Aprovado" },
  { value: "AUTORIZADO", label: "Autorizado" },
  { value: "PAGO_PARCIAL", label: "Pago parcial" },
  { value: "PAGO", label: "Pago" },
  { value: "REJEITADO", label: "Rejeitado" },
  { value: "CANCELADO", label: "Cancelado" },
];

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

interface ParcelaForm {
  numero: number;
  valor: string;
  vencimento: string;
}

interface FormState {
  id_fornecedor: number | null;
  id_natureza: number | null;
  id_conta: number | null;
  id_contrato: number | null;
  valor_total: string;
  competencia: string;
  numero_ne: string;
  numero_nf: string;
  criticidade: string;
  urgente: boolean;
  justificativa_urgencia: string;
  descricao: string;
}

function emptyForm(): FormState {
  return {
    id_fornecedor: null,
    id_natureza: null,
    id_conta: null,
    id_contrato: null,
    valor_total: "",
    competencia: "",
    numero_ne: "",
    numero_nf: "",
    criticidade: "MEDIA",
    urgente: false,
    justificativa_urgencia: "",
    descricao: "",
  };
}

function emptyParcelas(): ParcelaForm[] {
  return [{ numero: 1, valor: "", vencimento: "" }];
}

export default function ContasAPagarPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const { can } = useAuth();

  const [status, setStatus] = useState<StatusDebito | "">("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [parcelas, setParcelas] = useState<ParcelaForm[]>(emptyParcelas());
  const [err, setErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["pag-debitos", status],
    queryFn: () => api.pagamentos.debitos.list({ status: status || undefined }),
  });

  const fornecedoresQ = useQuery({
    queryKey: ["pag-fornecedores"],
    queryFn: () => api.pagamentos.cadastros.fornecedores.list(),
    enabled: open,
  });
  const naturezasQ = useQuery({
    queryKey: ["pag-naturezas"],
    queryFn: () => api.pagamentos.cadastros.naturezas.list(),
    enabled: open,
  });
  const contasQ = useQuery({
    queryKey: ["pag-contas-select"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
    enabled: open,
  });
  const contratosQ = useQuery({
    queryKey: ["pag-contratos"],
    queryFn: () => api.pagamentos.cadastros.contratos.list(),
    enabled: open,
  });

  function abrirNovo() {
    setForm(emptyForm());
    setParcelas(emptyParcelas());
    setErr(null);
    setOpen(true);
  }

  function addParcela() {
    setParcelas((cur) => [...cur, { numero: cur.length + 1, valor: "", vencimento: "" }]);
  }

  function removeParcela(idx: number) {
    setParcelas((cur) =>
      cur.filter((_, i) => i !== idx).map((p, i) => ({ ...p, numero: i + 1 })),
    );
  }

  function updateParcela(idx: number, patch: Partial<ParcelaForm>) {
    setParcelas((cur) => cur.map((p, i) => (i === idx ? { ...p, ...patch } : p)));
  }

  const somaParcelas = useMemo(
    () => parcelas.reduce((acc, p) => acc + (Number(p.valor) || 0), 0),
    [parcelas],
  );
  const valorTotalNum = Number(form.valor_total) || 0;
  const somaDiverge = Math.abs(somaParcelas - valorTotalNum) > 0.01;

  const createM = useMutation({
    mutationFn: () => {
      if (form.id_fornecedor === null) throw new Error("Selecione um fornecedor.");
      if (form.id_natureza === null) throw new Error("Selecione uma natureza de despesa.");
      if (form.id_conta === null) throw new Error("Selecione uma conta.");
      return api.pagamentos.debitos.create({
        id_fornecedor: form.id_fornecedor,
        id_natureza: form.id_natureza,
        id_conta: form.id_conta,
        id_contrato: form.id_contrato,
        valor_total: Number(form.valor_total),
        competencia: form.competencia,
        numero_ne: form.numero_ne.trim() || null,
        numero_nf: form.numero_nf.trim() || null,
        criticidade: form.criticidade,
        urgente: form.urgente,
        justificativa_urgencia: form.urgente ? form.justificativa_urgencia.trim() || null : null,
        descricao: form.descricao.trim(),
        parcelas: parcelas.map((p) => ({
          numero: p.numero,
          valor: Number(p.valor),
          vencimento: p.vencimento,
        })),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-debitos"] });
      toast.success("Débito criado.");
      setOpen(false);
    },
    onError: (e: Error) => {
      setErr(e.message);
      toast.error(e.message);
    },
  });

  const debitos = listQ.data ?? [];
  const podeSalvar =
    form.id_fornecedor !== null &&
    form.id_natureza !== null &&
    form.id_conta !== null &&
    Number(form.valor_total) > 0 &&
    form.competencia.length > 0 &&
    form.descricao.trim().length > 0 &&
    parcelas.length > 0 &&
    parcelas.every((p) => Number(p.valor) > 0 && p.vencimento.length > 0) &&
    (!form.urgente || form.justificativa_urgencia.trim().length > 0);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-aprimora">Contas a pagar</h1>
          <p className="text-sm text-muted-foreground">
            Débitos, parcelas e fluxo de aprovação/autorização de pagamentos.
          </p>
        </div>
        {can("pagamento_solicitar", "inserir") && (
          <Button onClick={abrirNovo}>Novo débito</Button>
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((t) => (
          <button
            key={t.value || "todos"}
            type="button"
            onClick={() => setStatus(t.value)}
            className={
              "rounded-full border px-3 py-1 text-xs font-medium transition-colors " +
              (status === t.value
                ? "border-brand bg-brand text-primary-foreground"
                : "border-border-strong bg-surface-1 text-foreground hover:bg-muted")
            }
          >
            {t.label}
          </button>
        ))}
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Fornecedor</TH>
            <TH>Descrição</TH>
            <TH>Competência</TH>
            <TH className="text-right">Valor</TH>
            <TH>Criticidade</TH>
            <TH>Status</TH>
          </TR>
        </THead>
        <TBody>
          {!listQ.isLoading && debitos.length === 0 && (
            <TR>
              <TD colSpan={6} className="py-6 text-center text-sm text-muted-foreground">
                Nenhum débito encontrado.
              </TD>
            </TR>
          )}
          {debitos.map((d) => (
            <TR key={d.id}>
              <TD>
                <Link
                  href={`/pagamentos/contas-a-pagar/${d.id}`}
                  className="text-primary hover:underline"
                >
                  {d.nome_fornecedor}
                </Link>
              </TD>
              <TD>{d.descricao}</TD>
              <TD>{d.competencia}</TD>
              <TD className="text-right tabular-nums">{fmtMoeda(d.valor_total)}</TD>
              <TD>
                <div className="flex items-center gap-1">
                  {d.criticidade}
                  {d.urgente && <Badge intent="danger">URGENTE</Badge>}
                </div>
              </TD>
              <TD>
                <StatusBadge status={d.status} />
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Novo débito"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => createM.mutate()} disabled={!podeSalvar || createM.isPending}>
              {createM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label htmlFor="db-fornecedor" required>
              Fornecedor
            </Label>
            <Select
              id="db-fornecedor"
              value={form.id_fornecedor ?? ""}
              onChange={(e) => setForm({ ...form, id_fornecedor: Number(e.target.value) })}
              required
            >
              <option value="" disabled>
                Selecione...
              </option>
              {(fornecedoresQ.data ?? []).map((f) => (
                <option key={f.id} value={f.id}>
                  {f.nome}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="db-natureza" required>
              Natureza de despesa
            </Label>
            <Select
              id="db-natureza"
              value={form.id_natureza ?? ""}
              onChange={(e) => setForm({ ...form, id_natureza: Number(e.target.value) })}
              required
            >
              <option value="" disabled>
                Selecione...
              </option>
              {(naturezasQ.data ?? []).map((n) => (
                <option key={n.id} value={n.id}>
                  {n.codigo} — {n.descricao}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="db-conta" required>
              Conta
            </Label>
            <Select
              id="db-conta"
              value={form.id_conta ?? ""}
              onChange={(e) => setForm({ ...form, id_conta: Number(e.target.value) })}
              required
            >
              <option value="" disabled>
                Selecione...
              </option>
              {(contasQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nome} ({c.banco})
                </option>
              ))}
            </Select>
          </div>
          <div className="col-span-2">
            <Label htmlFor="db-contrato">Contrato (opcional)</Label>
            <Select
              id="db-contrato"
              value={form.id_contrato ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_contrato: e.target.value ? Number(e.target.value) : null,
                })
              }
            >
              <option value="">Nenhum</option>
              {(contratosQ.data ?? []).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.numero} — {c.objeto}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="db-valor" required>
              Valor total
            </Label>
            <Input
              id="db-valor"
              type="number"
              min="0.01"
              step="0.01"
              value={form.valor_total}
              onChange={(e) => setForm({ ...form, valor_total: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="db-competencia" required>
              Competência
            </Label>
            <Input
              id="db-competencia"
              type="month"
              value={form.competencia}
              onChange={(e) => setForm({ ...form, competencia: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="db-ne">Número NE</Label>
            <Input
              id="db-ne"
              value={form.numero_ne}
              onChange={(e) => setForm({ ...form, numero_ne: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="db-nf">Número NF</Label>
            <Input
              id="db-nf"
              value={form.numero_nf}
              onChange={(e) => setForm({ ...form, numero_nf: e.target.value })}
            />
          </div>
          <div>
            <Label htmlFor="db-criticidade" required>
              Criticidade
            </Label>
            <Select
              id="db-criticidade"
              value={form.criticidade}
              onChange={(e) => setForm({ ...form, criticidade: e.target.value })}
              required
            >
              <option value="URGENTE">Urgente</option>
              <option value="ALTA">Alta</option>
              <option value="MEDIA">Média</option>
              <option value="BAIXA">Baixa</option>
            </Select>
          </div>
          <div className="flex items-end gap-2">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input
                type="checkbox"
                checked={form.urgente}
                onChange={(e) => setForm({ ...form, urgente: e.target.checked })}
              />
              Urgente
            </label>
          </div>
          {form.urgente && (
            <div className="col-span-2">
              <Label htmlFor="db-just-urgencia" required>
                Justificativa da urgência
              </Label>
              <Input
                id="db-just-urgencia"
                value={form.justificativa_urgencia}
                onChange={(e) => setForm({ ...form, justificativa_urgencia: e.target.value })}
                required
              />
            </div>
          )}
          <div className="col-span-2">
            <Label htmlFor="db-descricao" required>
              Descrição
            </Label>
            <Input
              id="db-descricao"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
              required
            />
          </div>

          <div className="col-span-2 mt-2 border-t border-border pt-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Parcelas</p>
              <Button type="button" variant="secondary" size="sm" onClick={addParcela}>
                Adicionar parcela
              </Button>
            </div>
            <div className="space-y-2">
              {parcelas.map((p, idx) => (
                <div key={idx} className="grid grid-cols-[1fr_2fr_2fr_auto] items-end gap-2">
                  <div>
                    <Label htmlFor={`db-parc-num-${idx}`}>Nº</Label>
                    <Input id={`db-parc-num-${idx}`} value={p.numero} disabled />
                  </div>
                  <div>
                    <Label htmlFor={`db-parc-valor-${idx}`} required>
                      Valor
                    </Label>
                    <Input
                      id={`db-parc-valor-${idx}`}
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={p.valor}
                      onChange={(e) => updateParcela(idx, { valor: e.target.value })}
                      required
                    />
                  </div>
                  <div>
                    <Label htmlFor={`db-parc-venc-${idx}`} required>
                      Vencimento
                    </Label>
                    <Input
                      id={`db-parc-venc-${idx}`}
                      type="date"
                      value={p.vencimento}
                      onChange={(e) => updateParcela(idx, { vencimento: e.target.value })}
                      required
                    />
                  </div>
                  <Button
                    type="button"
                    variant="danger"
                    size="sm"
                    onClick={() => removeParcela(idx)}
                    disabled={parcelas.length === 1}
                  >
                    Remover
                  </Button>
                </div>
              ))}
            </div>
            <p
              className={
                "mt-2 text-sm " +
                (somaDiverge ? "font-semibold text-danger-soft-foreground" : "text-muted-foreground")
              }
            >
              Σ parcelas: {fmtMoeda(String(somaParcelas))}
              {form.valor_total && ` de ${fmtMoeda(form.valor_total)}`}
              {somaDiverge && " — diverge do valor total!"}
            </p>
          </div>

          {err && (
            <div
              role="alert"
              className="col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground"
            >
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}

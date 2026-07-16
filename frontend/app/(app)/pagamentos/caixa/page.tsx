"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import {
  api,
  type ContaSaldoPainel,
  type OrigemMovimentacao,
  type TipoMovimentacao,
} from "@/lib/api";

function fmtMoeda(v: string): string {
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function hojeISO(): string {
  return new Date().toISOString().slice(0, 10);
}

interface FormState {
  id_conta: number | null;
  tipo: TipoMovimentacao;
  origem: OrigemMovimentacao;
  valor: string;
  data: string;
  descricao: string;
}

function emptyForm(idConta: number | null): FormState {
  return {
    id_conta: idConta,
    tipo: "ENTRADA",
    origem: "APORTE",
    valor: "",
    data: hojeISO(),
    descricao: "",
  };
}

export default function CaixaPage() {
  const qc = useQueryClient();
  const toast = useToast();

  const [selecionada, setSelecionada] = useState<ContaSaldoPainel | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(emptyForm(null));
  const [err, setErr] = useState<string | null>(null);

  const painelQ = useQuery({
    queryKey: ["pag-caixa-painel"],
    queryFn: () => api.pagamentos.caixa.painel(),
  });
  const contasQ = useQuery({
    queryKey: ["pag-contas-select"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const extratoQ = useQuery({
    queryKey: ["pag-caixa-extrato", selecionada?.id_conta],
    queryFn: () => api.pagamentos.caixa.extrato(selecionada!.id_conta),
    enabled: selecionada !== null,
  });

  function abrirLancar() {
    setForm(emptyForm(selecionada?.id_conta ?? contasQ.data?.[0]?.id ?? null));
    setErr(null);
    setOpen(true);
  }

  const lancarM = useMutation({
    mutationFn: () => {
      if (form.id_conta === null) throw new Error("Selecione uma conta.");
      return api.pagamentos.caixa.lancar({
        id_conta: form.id_conta,
        tipo: form.tipo,
        origem: form.origem,
        valor: Number(form.valor),
        data: form.data,
        descricao: form.descricao.trim() || null,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-caixa-painel"] });
      qc.invalidateQueries({ queryKey: ["pag-caixa-extrato"] });
      toast.success("Lançamento registrado.");
      setOpen(false);
    },
    onError: (e: Error) => {
      setErr(e.message);
      toast.error(e.message);
    },
  });

  const painel = painelQ.data ?? [];
  const extrato = extratoQ.data ?? [];
  const podeSalvar = form.id_conta !== null && Number(form.valor) > 0 && form.data.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-aprimora">Caixa</h1>
          <p className="text-sm text-muted-foreground">
            Painel de saldo por conta e lançamentos de entrada/saída.
          </p>
        </div>
        <Button onClick={abrirLancar}>Lançar entrada/saída</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Conta</TH>
            <TH>Banco</TH>
            <TH className="text-right">Saldo inicial</TH>
            <TH className="text-right">Entradas</TH>
            <TH className="text-right">Saídas</TH>
            <TH className="text-right">Comprometido</TH>
            <TH className="text-right">Disponível</TH>
            <TH className="text-right">Saldo atual</TH>
            <TH></TH>
          </TR>
        </THead>
        <TBody>
          {!painelQ.isLoading && painel.length === 0 && (
            <TR>
              <TD colSpan={9} className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma conta cadastrada.
              </TD>
            </TR>
          )}
          {painel.map((c) => (
            <TR
              key={c.id_conta}
              highlighted={selecionada?.id_conta === c.id_conta}
              onClickRow={() => setSelecionada(c)}
            >
              <TD>{c.nome}</TD>
              <TD>{c.banco}</TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.saldo_inicial)}</TD>
              <TD className="text-right tabular-nums text-success-soft-foreground">
                {fmtMoeda(c.total_entradas)}
              </TD>
              <TD className="text-right tabular-nums text-danger-soft-foreground">
                {fmtMoeda(c.total_saidas)}
              </TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.comprometido)}</TD>
              <TD className="text-right tabular-nums">{fmtMoeda(c.disponivel)}</TD>
              <TD className="text-right text-base font-semibold tabular-nums">
                {fmtMoeda(c.saldo_atual)}
              </TD>
              <TD>
                {c.abaixo_minimo && <Badge intent="danger">Abaixo do mínimo</Badge>}
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <div className="space-y-2">
        <h2 className="text-lg font-semibold text-foreground">
          Extrato{selecionada ? ` — ${selecionada.nome}` : ""}
        </h2>
        {selecionada === null ? (
          <p className="text-sm text-muted-foreground">
            Selecione uma conta no painel acima para ver o extrato.
          </p>
        ) : (
          <Table>
            <THead>
              <TR>
                <TH>Data</TH>
                <TH>Tipo</TH>
                <TH>Origem</TH>
                <TH className="text-right">Valor</TH>
                <TH>Descrição</TH>
              </TR>
            </THead>
            <TBody>
              {!extratoQ.isLoading && extrato.length === 0 && (
                <TR>
                  <TD colSpan={5} className="py-6 text-center text-sm text-muted-foreground">
                    Nenhuma movimentação nesta conta.
                  </TD>
                </TR>
              )}
              {extrato.map((m) => (
                <TR key={m.id}>
                  <TD>{m.data}</TD>
                  <TD>
                    <Badge intent={m.tipo === "ENTRADA" ? "success" : "danger"}>
                      {m.tipo === "ENTRADA" ? "Entrada" : "Saída"}
                    </Badge>
                  </TD>
                  <TD>{m.origem}</TD>
                  <TD
                    className={
                      "text-right tabular-nums " +
                      (m.tipo === "ENTRADA"
                        ? "text-success-soft-foreground"
                        : "text-danger-soft-foreground")
                    }
                  >
                    {m.tipo === "ENTRADA" ? "+" : "-"}
                    {fmtMoeda(m.valor)}
                  </TD>
                  <TD>{m.descricao ?? "—"}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </div>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title="Lançar entrada/saída"
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => lancarM.mutate()} disabled={!podeSalvar || lancarM.isPending}>
              {lancarM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label htmlFor="cx-conta" required>
              Conta
            </Label>
            <Select
              id="cx-conta"
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
          <div>
            <Label htmlFor="cx-tipo" required>
              Tipo
            </Label>
            <Select
              id="cx-tipo"
              value={form.tipo}
              onChange={(e) => setForm({ ...form, tipo: e.target.value as TipoMovimentacao })}
              required
            >
              <option value="ENTRADA">Entrada</option>
              <option value="SAIDA">Saída</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="cx-origem" required>
              Origem
            </Label>
            <Select
              id="cx-origem"
              value={form.origem}
              onChange={(e) =>
                setForm({ ...form, origem: e.target.value as OrigemMovimentacao })
              }
              required
            >
              <option value="APORTE">Aporte</option>
              <option value="RECEITA">Receita</option>
              <option value="AJUSTE">Ajuste</option>
            </Select>
          </div>
          <div>
            <Label htmlFor="cx-valor" required>
              Valor
            </Label>
            <Input
              id="cx-valor"
              type="number"
              min="0.01"
              step="0.01"
              value={form.valor}
              onChange={(e) => setForm({ ...form, valor: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="cx-data" required>
              Data
            </Label>
            <Input
              id="cx-data"
              type="date"
              value={form.data}
              onChange={(e) => setForm({ ...form, data: e.target.value })}
              required
            />
          </div>
          <div className="col-span-2">
            <Label htmlFor="cx-descricao">Descrição</Label>
            <Input
              id="cx-descricao"
              value={form.descricao}
              onChange={(e) => setForm({ ...form, descricao: e.target.value })}
            />
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

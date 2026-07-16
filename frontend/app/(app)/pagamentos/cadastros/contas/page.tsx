"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, type ContaBancaria } from "@/lib/api";

const GRUPO_LABELS: Record<string, string> = {
  PESSOAL: "Pessoal",
  CUSTEIO: "Custeio",
  INVESTIMENTO: "Investimento",
  DIVIDA: "Dívida",
  OUTRAS: "Outras",
};

interface FormState {
  nome: string;
  banco: string;
  agencia: string;
  conta: string;
  id_fonte_recursos: number | null;
  grupo_despesa: string;
  saldo_minimo_alerta: number;
  ativa: boolean;
}

const EMPTY: FormState = {
  nome: "",
  banco: "",
  agencia: "",
  conta: "",
  id_fonte_recursos: null,
  grupo_despesa: "CUSTEIO",
  saldo_minimo_alerta: 0,
  ativa: true,
};

export default function ContasPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [open, setOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY);

  const listQ = useQuery({
    queryKey: ["pag-contas"],
    queryFn: () => api.pagamentos.cadastros.contas.list(),
  });
  const fontesQ = useQuery({
    queryKey: ["pag-fontes-select"],
    queryFn: () => api.pagamentos.cadastros.fontes.list(),
  });
  const enumsQ = useQuery({
    queryKey: ["pag-enums"],
    queryFn: () => api.pagamentos.cadastros.enums(),
  });

  function openNew() {
    setEditId(null);
    setForm({ ...EMPTY, id_fonte_recursos: fontesQ.data?.[0]?.id ?? null });
    setOpen(true);
  }

  function openEdit(c: ContaBancaria) {
    setEditId(c.id);
    setForm({
      nome: c.nome,
      banco: c.banco,
      agencia: c.agencia,
      conta: c.conta,
      id_fonte_recursos: c.id_fonte_recursos,
      grupo_despesa: c.grupo_despesa,
      saldo_minimo_alerta: Number(c.saldo_minimo_alerta),
      ativa: c.ativa,
    });
    setOpen(true);
  }

  const saveM = useMutation({
    mutationFn: () => {
      const payload = {
        nome: form.nome.trim(),
        banco: form.banco.trim(),
        agencia: form.agencia.trim(),
        conta: form.conta.trim(),
        id_fonte_recursos: form.id_fonte_recursos,
        grupo_despesa: form.grupo_despesa,
        saldo_minimo_alerta: form.saldo_minimo_alerta ?? 0,
        ativa: form.ativa,
      };
      return editId === null
        ? api.pagamentos.cadastros.contas.create(payload)
        : api.pagamentos.cadastros.contas.update(editId, payload);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-contas"] });
      toast.success(editId === null ? "Conta criada." : "Conta atualizada.");
      setOpen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const removeM = useMutation({
    mutationFn: (id: number) => api.pagamentos.cadastros.contas.remove(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pag-contas"] });
      toast.success("Conta excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  async function excluir(c: ContaBancaria) {
    const ok = await confirm({
      title: "Excluir conta bancária",
      message: "Esta ação não pode ser desfeita. Deseja realmente excluir esta conta?",
      confirmLabel: "Excluir",
      intent: "danger",
    });
    if (ok) removeM.mutate(c.id);
  }

  const contas = listQ.data ?? [];
  const grupoOptions = enumsQ.data?.grupo_despesa ?? Object.keys(GRUPO_LABELS);
  const podeSalvar =
    form.nome.trim().length > 0 &&
    form.banco.trim().length > 0 &&
    form.agencia.trim().length > 0 &&
    form.conta.trim().length > 0 &&
    form.id_fonte_recursos !== null;

  function fonteNome(id: number) {
    return fontesQ.data?.find((f) => f.id === id)?.descricao ?? String(id);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-aprimora">Contas bancárias</h1>
        <Button onClick={openNew}>Novo</Button>
      </div>

      <Table>
        <THead>
          <TR>
            <TH>Nome</TH>
            <TH>Banco / Agência / Conta</TH>
            <TH>Fonte</TH>
            <TH>Grupo</TH>
            <TH>Ativa</TH>
            <TH className="text-right">Ações</TH>
          </TR>
        </THead>
        <TBody>
          {!listQ.isLoading && contas.length === 0 && (
            <TR>
              <TD colSpan={6} className="py-6 text-center text-sm text-muted-foreground">
                Nenhuma conta cadastrada.
              </TD>
            </TR>
          )}
          {contas.map((c) => (
            <TR key={c.id}>
              <TD>{c.nome}</TD>
              <TD>
                {c.banco} / {c.agencia} / {c.conta}
              </TD>
              <TD>{fonteNome(c.id_fonte_recursos)}</TD>
              <TD>{GRUPO_LABELS[c.grupo_despesa] ?? c.grupo_despesa}</TD>
              <TD>{c.ativa ? "Sim" : "Não"}</TD>
              <TD className="text-right">
                <div className="inline-flex gap-2">
                  <Button variant="secondary" size="sm" onClick={() => openEdit(c)}>
                    Editar
                  </Button>
                  <Button variant="danger" size="sm" onClick={() => excluir(c)}>
                    Excluir
                  </Button>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>

      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        title={editId === null ? "Nova conta bancária" : "Editar conta bancária"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={() => saveM.mutate()} disabled={!podeSalvar || saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <Label htmlFor="conta-nome" required>
              Nome
            </Label>
            <Input
              id="conta-nome"
              value={form.nome}
              onChange={(e) => setForm({ ...form, nome: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="conta-banco" required>
              Banco
            </Label>
            <Input
              id="conta-banco"
              value={form.banco}
              onChange={(e) => setForm({ ...form, banco: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="conta-agencia" required>
              Agência
            </Label>
            <Input
              id="conta-agencia"
              value={form.agencia}
              onChange={(e) => setForm({ ...form, agencia: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="conta-conta" required>
              Conta
            </Label>
            <Input
              id="conta-conta"
              value={form.conta}
              onChange={(e) => setForm({ ...form, conta: e.target.value })}
              required
            />
          </div>
          <div>
            <Label htmlFor="conta-saldo">Saldo mínimo de alerta</Label>
            <Input
              id="conta-saldo"
              type="number"
              value={form.saldo_minimo_alerta}
              onChange={(e) =>
                setForm({
                  ...form,
                  saldo_minimo_alerta: e.target.value === "" ? 0 : Number(e.target.value),
                })
              }
            />
          </div>
          <div>
            <Label htmlFor="conta-fonte" required>
              Fonte de recursos
            </Label>
            <Select
              id="conta-fonte"
              value={form.id_fonte_recursos ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  id_fonte_recursos: e.target.value === "" ? null : Number(e.target.value),
                })
              }
              required
            >
              <option value="">—</option>
              {fontesQ.data?.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.codigo} — {f.descricao}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="conta-grupo" required>
              Grupo de despesa
            </Label>
            <Select
              id="conta-grupo"
              value={form.grupo_despesa}
              onChange={(e) => setForm({ ...form, grupo_despesa: e.target.value })}
              required
            >
              {grupoOptions.map((g) => (
                <option key={g} value={g}>
                  {GRUPO_LABELS[g] ?? g}
                </option>
              ))}
            </Select>
          </div>
          <div className="col-span-2 flex items-center gap-2">
            <Checkbox
              id="conta-ativa"
              checked={form.ativa}
              onChange={(e) => setForm({ ...form, ativa: e.target.checked })}
            />
            <Label htmlFor="conta-ativa" className="mb-0">
              Ativa
            </Label>
          </div>
        </div>
      </Dialog>
    </div>
  );
}

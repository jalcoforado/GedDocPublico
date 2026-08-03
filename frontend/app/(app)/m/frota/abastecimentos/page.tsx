"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fuel, Gauge, Inbox, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type VeiculoAbastecimento } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const COMBUSTIVEIS = ["gasolina", "etanol", "flex", "diesel", "gnv", "eletrico", "hibrido"];

interface AbastForm {
  id_veiculo: number | null;
  id_motorista: number | null;
  data_abastecimento: string;
  km_atual: number | null;
  tipo_combustivel: string;
  litros: number | null;
  valor_total: number | null;
  posto: string;
  observacoes: string;
}

const EMPTY: AbastForm = {
  id_veiculo: null,
  id_motorista: null,
  data_abastecimento: "",
  km_atual: null,
  tipo_combustivel: "",
  litros: null,
  valor_total: null,
  posto: "",
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}
function fmtData(d: string | null): string {
  if (!d) return "—";
  return new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR");
}
function fmtMoeda(v: number | null): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <p className="text-sm text-foreground-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums text-foreground">{value}</p>
    </div>
  );
}

export default function AbastecimentosPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoAbastecimento | null>(null);
  const [form, setForm] = useState<AbastForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const motoristasQ = useQuery({ queryKey: ["frota-motoristas"], queryFn: () => api.motoristas.listAll() });
  const abastQ = useQuery({ queryKey: ["frota-abastecimentos"], queryFn: () => api.abastecimentos.list() });
  const resumoQ = useQuery({ queryKey: ["frota-abast-resumo"], queryFn: () => api.abastecimentos.resumo() });

  const placaDe = useMemo(() => {
    const map = new Map<number, string>();
    (veiculosQ.data ?? []).forEach((v) => map.set(v.id, v.placa));
    return map;
  }, [veiculosQ.data]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["frota-abastecimentos"] });
    qc.invalidateQueries({ queryKey: ["frota-abast-resumo"] });
    qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
    qc.invalidateQueries({ queryKey: ["frota-relatorio-resumo"] });
  };

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.abastecimentos.update(editing.id, data) : api.abastecimentos.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Abastecimento atualizado." : "Abastecimento registrado.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.abastecimentos.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Abastecimento excluído.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof AbastForm>(key: K, value: AbastForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }
  function openEdit(a: VeiculoAbastecimento) {
    setEditing(a);
    setForm({
      id_veiculo: a.id_veiculo,
      id_motorista: a.id_motorista,
      data_abastecimento: a.data_abastecimento,
      km_atual: a.km_atual,
      tipo_combustivel: a.tipo_combustivel ?? "",
      litros: a.litros,
      valor_total: a.valor_total,
      posto: a.posto ?? "",
      observacoes: a.observacoes ?? "",
    });
    setErr(null);
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!editing && form.id_veiculo == null) {
      setErr("Selecione o veículo.");
      return;
    }
    if (form.km_atual == null || form.litros == null || form.valor_total == null) {
      setErr("Km, litros e valor total são obrigatórios.");
      return;
    }
    if (form.litros <= 0) {
      setErr("Litros deve ser maior que zero.");
      return;
    }
    const comum = {
      id_motorista: form.id_motorista ?? null,
      data_abastecimento: nullify(form.data_abastecimento),
      km_atual: form.km_atual,
      tipo_combustivel: nullify(form.tipo_combustivel),
      litros: form.litros,
      valor_total: form.valor_total,
      posto: nullify(form.posto),
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(editing ? comum : { id_veiculo: form.id_veiculo, ...comum });
  }

  const r = resumoQ.data;
  return (
    <div className="space-y-4">
      <PageHeader
        icon={Fuel}
        title="Abastecimentos"
        description="Registro de abastecimentos da frota."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Abastecimentos" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Novo abastecimento
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="Abastecimentos" value={String(r?.total_abastecimentos ?? 0)} />
        <StatCard label="Litros (total)" value={(r?.total_litros ?? 0).toLocaleString("pt-BR")} />
        <StatCard label="Custo total" value={fmtMoeda(r?.total_valor ?? 0)} />
        <StatCard
          label="Média R$/litro"
          value={r?.media_valor_litro != null ? fmtMoeda(r.media_valor_litro) : "—"}
        />
      </div>
      {r?.ultimo_abastecimento && (
        <p className="text-sm text-foreground-muted">
          <Gauge className="mr-1 inline h-4 w-4" />
          Último abastecimento: {fmtData(r.ultimo_abastecimento)}
        </p>
      )}

      {!abastQ.isLoading && (abastQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhum abastecimento"
          description="Registre o primeiro abastecimento de um veículo da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Novo abastecimento
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Data</TH>
              <TH>Veículo</TH>
              <TH className="text-right">Km</TH>
              <TH className="text-right">Litros</TH>
              <TH className="text-right">Valor</TH>
              <TH>Posto</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {abastQ.isLoading && (
              <TR>
                <TD colSpan={7} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {abastQ.data?.map((a) => (
              <TR key={a.id}>
                <TD className="tabular-nums">{fmtData(a.data_abastecimento)}</TD>
                <TD className="font-mono">{placaDe.get(a.id_veiculo) ?? `#${a.id_veiculo}`}</TD>
                <TD className="text-right tabular-nums">{a.km_atual.toLocaleString("pt-BR")}</TD>
                <TD className="text-right tabular-nums">{a.litros.toLocaleString("pt-BR")}</TD>
                <TD className="text-right tabular-nums">{fmtMoeda(a.valor_total)}</TD>
                <TD className="text-muted-foreground">{a.posto ?? "—"}</TD>
                <TD className="text-right">
                  <div className="inline-flex gap-2">
                    {canEdit && (
                      <Button variant="secondary" size="sm" onClick={() => openEdit(a)}>
                        Editar
                      </Button>
                    )}
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        disabled={deleteM.isPending}
                        onClick={async () => {
                          const ok = await confirm({
                            title: "Excluir abastecimento",
                            message: "Excluir este abastecimento? Esta ação não pode ser desfeita.",
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(a.id);
                        }}
                      >
                        Excluir
                      </Button>
                    )}
                  </div>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar abastecimento" : "Novo abastecimento"}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button onClick={salvar} disabled={saveM.isPending}>
              {saveM.isPending ? "Salvando..." : "Salvar"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {!editing && (
            <div className="sm:col-span-2">
              <Label htmlFor="veiculo" required>
                Veículo
              </Label>
              <Select
                id="veiculo"
                value={form.id_veiculo ?? ""}
                onChange={(e) => set("id_veiculo", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Selecione...</option>
                {(veiculosQ.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.placa} {v.marca ? `— ${v.marca}` : ""}
                  </option>
                ))}
              </Select>
            </div>
          )}
          <div>
            <Label htmlFor="motorista">Motorista</Label>
            <Select
              id="motorista"
              value={form.id_motorista ?? ""}
              onChange={(e) => set("id_motorista", e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">—</option>
              {(motoristasQ.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="data">Data</Label>
            <Input
              id="data"
              type="date"
              value={form.data_abastecimento}
              onChange={(e) => set("data_abastecimento", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="km" required>
              Km atual
            </Label>
            <Input
              id="km"
              type="number"
              min={0}
              value={form.km_atual ?? ""}
              onChange={(e) => set("km_atual", e.target.value ? Number(e.target.value) : null)}
            />
          </div>
          <div>
            <Label htmlFor="combustivel">Combustível</Label>
            <Select
              id="combustivel"
              value={form.tipo_combustivel}
              onChange={(e) => set("tipo_combustivel", e.target.value)}
            >
              <option value="">—</option>
              {COMBUSTIVEIS.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="litros" required>
              Litros
            </Label>
            <Input
              id="litros"
              type="number"
              min={0}
              step="0.001"
              value={form.litros ?? ""}
              onChange={(e) => set("litros", e.target.value ? Number(e.target.value) : null)}
            />
          </div>
          <div>
            <Label htmlFor="valor" required>
              Valor total (R$)
            </Label>
            <Input
              id="valor"
              type="number"
              min={0}
              step="0.01"
              value={form.valor_total ?? ""}
              onChange={(e) => set("valor_total", e.target.value ? Number(e.target.value) : null)}
            />
          </div>
          <div>
            <Label htmlFor="posto">Posto</Label>
            <Input id="posto" value={form.posto} onChange={(e) => set("posto", e.target.value)} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="obs">Observações</Label>
            <Textarea id="obs" rows={2} value={form.observacoes} onChange={(e) => set("observacoes", e.target.value)} />
          </div>
          {err && (
            <div role="alert" className="sm:col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}

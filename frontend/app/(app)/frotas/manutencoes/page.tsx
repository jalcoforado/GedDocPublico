"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Plus, Wrench } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
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
import {
  api,
  type ManutencaoStatus,
  type ManutencaoTipo,
  type VeiculoManutencao,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: ManutencaoTipo; label: string }[] = [
  { value: "preventiva", label: "Preventiva" },
  { value: "corretiva", label: "Corretiva" },
];
const STATUS: { value: ManutencaoStatus; label: string }[] = [
  { value: "aberta", label: "Aberta" },
  { value: "em_andamento", label: "Em andamento" },
  { value: "concluida", label: "Concluída" },
  { value: "cancelada", label: "Cancelada" },
];
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS.map((s) => [s.value, s.label]));
const STATUS_INTENT: Record<string, "neutral" | "info" | "success" | "danger"> = {
  aberta: "info",
  em_andamento: "neutral",
  concluida: "success",
  cancelada: "danger",
};

interface ManutForm {
  id_veiculo: number | null;
  tipo: ManutencaoTipo;
  descricao: string;
  data_prevista: string;
  km_atual: number | null;
  fornecedor: string;
  custo_estimado: number | null;
  observacoes: string;
}

const EMPTY: ManutForm = {
  id_veiculo: null,
  tipo: "preventiva",
  descricao: "",
  data_prevista: "",
  km_atual: null,
  fornecedor: "",
  custo_estimado: null,
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

export default function ManutencoesPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [statusFiltro, setStatusFiltro] = useState<string>("");
  const [tipoFiltro, setTipoFiltro] = useState<string>("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoManutencao | null>(null);
  const [form, setForm] = useState<ManutForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [concluindo, setConcluindo] = useState<VeiculoManutencao | null>(null);
  const [concForm, setConcForm] = useState({ data_conclusao: "", custo_final: "", km_atual: "" });

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const placaDe = useMemo(() => {
    const map = new Map<number, string>();
    (veiculosQ.data ?? []).forEach((v) => map.set(v.id, v.placa));
    return map;
  }, [veiculosQ.data]);

  const manutQ = useQuery({
    queryKey: ["frota-manutencoes", statusFiltro],
    queryFn: () => api.manutencoes.list(statusFiltro ? { status_filtro: statusFiltro } : undefined),
  });
  const linhas = useMemo(
    () => (manutQ.data ?? []).filter((m) => (tipoFiltro ? m.tipo === tipoFiltro : true)),
    [manutQ.data, tipoFiltro],
  );

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["frota-manutencoes"] });
    qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
    qc.invalidateQueries({ queryKey: ["frota-relatorio-resumo"] });
  };

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.manutencoes.update(editing.id, data) : api.manutencoes.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Manutenção atualizada." : "Manutenção aberta.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "iniciar" | "cancelar" }) =>
      acao === "iniciar" ? api.manutencoes.iniciar(id) : api.manutencoes.cancelar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Manutenção atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const concluirM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: ({ id, data }: { id: number; data: any }) => api.manutencoes.concluir(id, data),
    onSuccess: () => {
      invalidate();
      toast.success("Manutenção concluída.");
      setConcluindo(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.manutencoes.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Manutenção excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof ManutForm>(key: K, value: ManutForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }
  function openEdit(m: VeiculoManutencao) {
    setEditing(m);
    setForm({
      id_veiculo: m.id_veiculo,
      tipo: m.tipo,
      descricao: m.descricao,
      data_prevista: m.data_prevista ?? "",
      km_atual: m.km_atual,
      fornecedor: m.fornecedor ?? "",
      custo_estimado: m.custo_estimado,
      observacoes: m.observacoes ?? "",
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
    if (form.descricao.trim() === "") {
      setErr("Descrição é obrigatória.");
      return;
    }
    const comum = {
      tipo: form.tipo,
      descricao: form.descricao.trim(),
      data_prevista: nullify(form.data_prevista),
      km_atual: form.km_atual ?? null,
      fornecedor: nullify(form.fornecedor),
      custo_estimado: form.custo_estimado ?? null,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(editing ? comum : { id_veiculo: form.id_veiculo, ...comum });
  }
  function concluir() {
    concluirM.mutate({
      id: concluindo!.id,
      data: {
        data_conclusao: nullify(concForm.data_conclusao),
        custo_final: concForm.custo_final === "" ? null : Number(concForm.custo_final),
        km_atual: concForm.km_atual === "" ? null : Number(concForm.km_atual),
      },
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Wrench}
        title="Manutenções"
        description="Manutenções preventivas e corretivas da frota."
        breadcrumbs={[{ label: "Frota Pública", href: "/frotas" }, { label: "Manutenções" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova manutenção
            </Button>
          ) : undefined
        }
      />

      <div className="flex flex-wrap gap-3">
        <div>
          <Label htmlFor="f_status">Status</Label>
          <Select id="f_status" value={statusFiltro} onChange={(e) => setStatusFiltro(e.target.value)}>
            <option value="">Todos</option>
            {STATUS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </div>
        <div>
          <Label htmlFor="f_tipo">Tipo</Label>
          <Select id="f_tipo" value={tipoFiltro} onChange={(e) => setTipoFiltro(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {!manutQ.isLoading && linhas.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma manutenção"
          description="Abra a primeira manutenção para um veículo da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Nova manutenção
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Veículo</TH>
              <TH>Tipo</TH>
              <TH>Descrição</TH>
              <TH>Abertura</TH>
              <TH>Status</TH>
              <TH className="text-right">Custo final</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {manutQ.isLoading && (
              <TR>
                <TD colSpan={7} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {linhas.map((m) => {
              const aberta = m.status === "aberta";
              const encerravel = m.status === "aberta" || m.status === "em_andamento";
              return (
                <TR key={m.id}>
                  <TD className="font-mono">{placaDe.get(m.id_veiculo) ?? `#${m.id_veiculo}`}</TD>
                  <TD>{m.tipo === "preventiva" ? "Preventiva" : "Corretiva"}</TD>
                  <TD className="max-w-[20rem] truncate">{m.descricao}</TD>
                  <TD className="tabular-nums">{fmtData(m.data_abertura)}</TD>
                  <TD>
                    <Badge intent={STATUS_INTENT[m.status] ?? "neutral"}>
                      {STATUS_LABEL[m.status] ?? m.status}
                    </Badge>
                  </TD>
                  <TD className="text-right tabular-nums">{fmtMoeda(m.custo_final)}</TD>
                  <TD className="text-right">
                    <div className="inline-flex flex-wrap justify-end gap-2">
                      {canEdit && aberta && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => actionM.mutate({ id: m.id, acao: "iniciar" })}
                        >
                          Iniciar
                        </Button>
                      )}
                      {canEdit && encerravel && (
                        <Button
                          size="sm"
                          onClick={() => {
                            setConcluindo(m);
                            setConcForm({ data_conclusao: "", custo_final: "", km_atual: "" });
                          }}
                        >
                          Concluir
                        </Button>
                      )}
                      {canEdit && encerravel && (
                        <Button variant="secondary" size="sm" onClick={() => openEdit(m)}>
                          Editar
                        </Button>
                      )}
                      {canEdit && encerravel && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Cancelar manutenção",
                              message: "Cancelar esta manutenção?",
                              confirmLabel: "Cancelar manutenção",
                            });
                            if (ok) actionM.mutate({ id: m.id, acao: "cancelar" });
                          }}
                        >
                          Cancelar
                        </Button>
                      )}
                      {canDelete && (
                        <Button
                          variant="danger"
                          size="sm"
                          disabled={deleteM.isPending}
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Excluir manutenção",
                              message: "Excluir este registro de manutenção? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(m.id);
                          }}
                        >
                          Excluir
                        </Button>
                      )}
                    </div>
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      )}

      <Dialog
        open={dialogOpen}
        onClose={closeDialog}
        title={editing ? "Editar manutenção" : "Nova manutenção"}
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
            <Label htmlFor="tipo" required>
              Tipo
            </Label>
            <Select id="tipo" value={form.tipo} onChange={(e) => set("tipo", e.target.value as ManutencaoTipo)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="data_prevista">Data prevista</Label>
            <Input
              id="data_prevista"
              type="date"
              value={form.data_prevista}
              onChange={(e) => set("data_prevista", e.target.value)}
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="descricao" required>
              Descrição
            </Label>
            <Textarea
              id="descricao"
              rows={2}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="km_atual">Km atual</Label>
            <Input
              id="km_atual"
              type="number"
              min={0}
              value={form.km_atual ?? ""}
              onChange={(e) => set("km_atual", e.target.value ? Number(e.target.value) : null)}
            />
          </div>
          <div>
            <Label htmlFor="fornecedor">Fornecedor</Label>
            <Input id="fornecedor" value={form.fornecedor} onChange={(e) => set("fornecedor", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="custo_estimado">Custo estimado (R$)</Label>
            <Input
              id="custo_estimado"
              type="number"
              min={0}
              step="0.01"
              value={form.custo_estimado ?? ""}
              onChange={(e) => set("custo_estimado", e.target.value ? Number(e.target.value) : null)}
            />
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

      <Dialog
        open={concluindo != null}
        onClose={() => setConcluindo(null)}
        title="Concluir manutenção"
        footer={
          <>
            <Button variant="secondary" onClick={() => setConcluindo(null)}>
              Cancelar
            </Button>
            <Button onClick={concluir} disabled={concluirM.isPending}>
              {concluirM.isPending ? "Concluindo..." : "Concluir"}
            </Button>
          </>
        }
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="c_data">Data de conclusão</Label>
            <Input
              id="c_data"
              type="date"
              value={concForm.data_conclusao}
              onChange={(e) => setConcForm((f) => ({ ...f, data_conclusao: e.target.value }))}
            />
          </div>
          <div>
            <Label htmlFor="c_km">Km atual</Label>
            <Input
              id="c_km"
              type="number"
              min={0}
              value={concForm.km_atual}
              onChange={(e) => setConcForm((f) => ({ ...f, km_atual: e.target.value }))}
            />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="c_custo">Custo final (R$)</Label>
            <Input
              id="c_custo"
              type="number"
              min={0}
              step="0.01"
              value={concForm.custo_final}
              onChange={(e) => setConcForm((f) => ({ ...f, custo_final: e.target.value }))}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertOctagon, Inbox, Plus } from "lucide-react";
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
  type OcorrenciaGravidade,
  type OcorrenciaTipo,
  type VeiculoOcorrencia,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TIPOS: { value: OcorrenciaTipo; label: string }[] = [
  { value: "avaria", label: "Avaria" },
  { value: "multa", label: "Multa" },
  { value: "sinistro", label: "Sinistro" },
  { value: "documentacao", label: "Documentação" },
  { value: "uso_indevido", label: "Uso indevido" },
  { value: "outro", label: "Outro" },
];
const GRAVIDADES: { value: OcorrenciaGravidade; label: string }[] = [
  { value: "baixa", label: "Baixa" },
  { value: "media", label: "Média" },
  { value: "alta", label: "Alta" },
  { value: "critica", label: "Crítica" },
];
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));
const GRAV_LABEL: Record<string, string> = Object.fromEntries(GRAVIDADES.map((g) => [g.value, g.label]));
const GRAV_INTENT: Record<string, "neutral" | "info" | "warning" | "danger"> = {
  baixa: "neutral",
  media: "info",
  alta: "warning",
  critica: "danger",
};
const STATUS: { value: string; label: string }[] = [
  { value: "aberta", label: "Aberta" },
  { value: "em_tratamento", label: "Em tratamento" },
  { value: "resolvida", label: "Resolvida" },
  { value: "cancelada", label: "Cancelada" },
];
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS.map((s) => [s.value, s.label]));
const STATUS_INTENT: Record<string, "info" | "neutral" | "success" | "danger"> = {
  aberta: "info",
  em_tratamento: "neutral",
  resolvida: "success",
  cancelada: "danger",
};

interface OcorrForm {
  id_veiculo: number | null;
  id_motorista: number | null;
  tipo: OcorrenciaTipo;
  data_ocorrencia: string;
  descricao: string;
  gravidade: OcorrenciaGravidade;
  providencias: string;
}

const EMPTY: OcorrForm = {
  id_veiculo: null,
  id_motorista: null,
  tipo: "avaria",
  data_ocorrencia: "",
  descricao: "",
  gravidade: "media",
  providencias: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}
function fmtData(d: string | null): string {
  if (!d) return "—";
  return new Date(`${d}T00:00:00`).toLocaleDateString("pt-BR");
}

function StatCard({ label, value, intent }: { label: string; value: number; intent?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface-1 p-4">
      <p className="text-sm text-foreground-muted">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold tabular-nums ${
          intent === "danger" && value > 0 ? "text-danger-soft-foreground" : "text-foreground"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export default function OcorrenciasPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [statusFiltro, setStatusFiltro] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<VeiculoOcorrencia | null>(null);
  const [form, setForm] = useState<OcorrForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);
  const [resolvendo, setResolvendo] = useState<VeiculoOcorrencia | null>(null);
  const [resForm, setResForm] = useState({ data_resolucao: "", providencias: "" });

  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const motoristasQ = useQuery({ queryKey: ["frota-motoristas"], queryFn: () => api.motoristas.listAll() });
  const todasQ = useQuery({ queryKey: ["frota-ocorrencias-all"], queryFn: () => api.ocorrencias.list() });
  const listaQ = useQuery({
    queryKey: ["frota-ocorrencias", statusFiltro],
    queryFn: () => api.ocorrencias.list(statusFiltro ? { status_filtro: statusFiltro } : undefined),
  });

  const placaDe = useMemo(() => {
    const map = new Map<number, string>();
    (veiculosQ.data ?? []).forEach((v) => map.set(v.id, v.placa));
    return map;
  }, [veiculosQ.data]);

  const cards = useMemo(() => {
    const all = todasQ.data ?? [];
    const abertas = all.filter((o) => o.status === "aberta" || o.status === "em_tratamento").length;
    const criticas = all.filter(
      (o) => o.gravidade === "critica" && (o.status === "aberta" || o.status === "em_tratamento"),
    ).length;
    const resolvidas = all.filter((o) => o.status === "resolvida").length;
    return { abertas, criticas, resolvidas };
  }, [todasQ.data]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["frota-ocorrencias"] });
    qc.invalidateQueries({ queryKey: ["frota-ocorrencias-all"] });
  };

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.ocorrencias.update(editing.id, data) : api.ocorrencias.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Ocorrência atualizada." : "Ocorrência registrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const actionM = useMutation({
    mutationFn: ({ id, acao }: { id: number; acao: "iniciar" | "cancelar" }) =>
      acao === "iniciar" ? api.ocorrencias.iniciarTratamento(id) : api.ocorrencias.cancelar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Ocorrência atualizada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const resolverM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: ({ id, data }: { id: number; data: any }) => api.ocorrencias.resolver(id, data),
    onSuccess: () => {
      invalidate();
      toast.success("Ocorrência resolvida.");
      setResolvendo(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.ocorrencias.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Ocorrência excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof OcorrForm>(key: K, value: OcorrForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }
  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }
  function openEdit(o: VeiculoOcorrencia) {
    setEditing(o);
    setForm({
      id_veiculo: o.id_veiculo,
      id_motorista: o.id_motorista,
      tipo: o.tipo,
      data_ocorrencia: o.data_ocorrencia,
      descricao: o.descricao,
      gravidade: o.gravidade,
      providencias: o.providencias ?? "",
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
      id_motorista: form.id_motorista ?? null,
      tipo: form.tipo,
      data_ocorrencia: nullify(form.data_ocorrencia),
      descricao: form.descricao.trim(),
      gravidade: form.gravidade,
      providencias: nullify(form.providencias),
    };
    saveM.mutate(editing ? comum : { id_veiculo: form.id_veiculo, ...comum });
  }
  function resolver() {
    resolverM.mutate({
      id: resolvendo!.id,
      data: {
        data_resolucao: nullify(resForm.data_resolucao),
        providencias: nullify(resForm.providencias),
      },
    });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={AlertOctagon}
        title="Ocorrências"
        description="Ocorrências internas da frota: avaria, multa, sinistro e outras."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Ocorrências" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova ocorrência
            </Button>
          ) : undefined
        }
      />

      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Abertas" value={cards.abertas} />
        <StatCard label="Críticas (abertas)" value={cards.criticas} intent="danger" />
        <StatCard label="Resolvidas" value={cards.resolvidas} />
      </div>

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

      {!listaQ.isLoading && (listaQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma ocorrência"
          description="Registre a primeira ocorrência de um veículo da frota."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Nova ocorrência
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
              <TH>Tipo</TH>
              <TH>Gravidade</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listaQ.isLoading && (
              <TR>
                <TD colSpan={6} className="text-center text-muted-foreground">
                  Carregando...
                </TD>
              </TR>
            )}
            {listaQ.data?.map((o) => {
              const tratavel = o.status === "aberta" || o.status === "em_tratamento";
              return (
                <TR key={o.id}>
                  <TD className="tabular-nums">{fmtData(o.data_ocorrencia)}</TD>
                  <TD className="font-mono">{placaDe.get(o.id_veiculo) ?? `#${o.id_veiculo}`}</TD>
                  <TD>{TIPO_LABEL[o.tipo] ?? o.tipo}</TD>
                  <TD>
                    <Badge intent={GRAV_INTENT[o.gravidade] ?? "neutral"}>
                      {GRAV_LABEL[o.gravidade] ?? o.gravidade}
                    </Badge>
                  </TD>
                  <TD>
                    <Badge intent={STATUS_INTENT[o.status] ?? "neutral"}>
                      {STATUS_LABEL[o.status] ?? o.status}
                    </Badge>
                  </TD>
                  <TD className="text-right">
                    <div className="inline-flex flex-wrap justify-end gap-2">
                      {canEdit && o.status === "aberta" && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => actionM.mutate({ id: o.id, acao: "iniciar" })}
                        >
                          Tratar
                        </Button>
                      )}
                      {canEdit && tratavel && (
                        <Button
                          size="sm"
                          onClick={() => {
                            setResolvendo(o);
                            setResForm({ data_resolucao: "", providencias: o.providencias ?? "" });
                          }}
                        >
                          Resolver
                        </Button>
                      )}
                      {canEdit && tratavel && (
                        <Button variant="secondary" size="sm" onClick={() => openEdit(o)}>
                          Editar
                        </Button>
                      )}
                      {canEdit && tratavel && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Cancelar ocorrência",
                              message: "Cancelar esta ocorrência?",
                              confirmLabel: "Cancelar ocorrência",
                            });
                            if (ok) actionM.mutate({ id: o.id, acao: "cancelar" });
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
                              title: "Excluir ocorrência",
                              message: "Excluir esta ocorrência? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(o.id);
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
        title={editing ? "Editar ocorrência" : "Nova ocorrência"}
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
              value={form.data_ocorrencia}
              onChange={(e) => set("data_ocorrencia", e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="tipo" required>
              Tipo
            </Label>
            <Select id="tipo" value={form.tipo} onChange={(e) => set("tipo", e.target.value as OcorrenciaTipo)}>
              {TIPOS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="gravidade">Gravidade</Label>
            <Select
              id="gravidade"
              value={form.gravidade}
              onChange={(e) => set("gravidade", e.target.value as OcorrenciaGravidade)}
            >
              {GRAVIDADES.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </Select>
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
          <div className="sm:col-span-2">
            <Label htmlFor="prov">Providências</Label>
            <Textarea
              id="prov"
              rows={2}
              value={form.providencias}
              onChange={(e) => set("providencias", e.target.value)}
            />
          </div>
          {err && (
            <div role="alert" className="sm:col-span-2 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>

      <Dialog
        open={resolvendo != null}
        onClose={() => setResolvendo(null)}
        title="Resolver ocorrência"
        footer={
          <>
            <Button variant="secondary" onClick={() => setResolvendo(null)}>
              Cancelar
            </Button>
            <Button onClick={resolver} disabled={resolverM.isPending}>
              {resolverM.isPending ? "Resolvendo..." : "Resolver"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <Label htmlFor="r_data">Data de resolução</Label>
            <Input
              id="r_data"
              type="date"
              value={resForm.data_resolucao}
              onChange={(e) => setResForm((f) => ({ ...f, data_resolucao: e.target.value }))}
            />
          </div>
          <div>
            <Label htmlFor="r_prov">Providências</Label>
            <Textarea
              id="r_prov"
              rows={3}
              value={resForm.providencias}
              onChange={(e) => setResForm((f) => ({ ...f, providencias: e.target.value }))}
            />
          </div>
        </div>
      </Dialog>
    </div>
  );
}

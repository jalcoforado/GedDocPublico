"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardList, FileText, Inbox, MapPin, Plus } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type SolicitacaoStatus, type SolicitacaoVeiculo } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATUS_LABEL: Record<SolicitacaoStatus, string> = {
  solicitada: "Solicitada",
  aprovada: "Aprovada",
  rejeitada: "Rejeitada",
  cancelada: "Cancelada",
};
const STATUS_INTENT: Record<SolicitacaoStatus, "neutral" | "success" | "danger" | "warning"> = {
  solicitada: "warning",
  aprovada: "success",
  rejeitada: "danger",
  cancelada: "neutral",
};

interface SolicitacaoForm {
  id_unidade_solicitante: number | null;
  finalidade: string;
  destino: string;
  data_saida_prevista: string;
  data_retorno_prevista: string;
  quantidade_passageiros: number;
  necessita_motorista: boolean;
  observacoes: string;
}

const EMPTY: SolicitacaoForm = {
  id_unidade_solicitante: null,
  finalidade: "",
  destino: "",
  data_saida_prevista: "",
  data_retorno_prevista: "",
  quantidade_passageiros: 1,
  necessita_motorista: false,
  observacoes: "",
};

function nullify(v: string): string | null {
  const t = v.trim();
  return t === "" ? null : t;
}

function fmt(dt: string): string {
  if (!dt) return "—";
  const d = new Date(dt);
  return isNaN(d.getTime()) ? dt : d.toLocaleString("pt-BR");
}

export default function SolicitacoesPage() {
  const { can } = useAuth();
  const canCreate = can("frota", "inserir");
  const canEdit = can("frota", "atualizar");
  const canDelete = can("frota", "excluir");
  const qc = useQueryClient();
  const toast = useToast();
  const confirm = useConfirm();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<SolicitacaoVeiculo | null>(null);
  const [form, setForm] = useState<SolicitacaoForm>(EMPTY);
  const [err, setErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["frota-solicitacoes"],
    queryFn: () => api.solicitacoes.listAll(),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";

  const invalidate = () => qc.invalidateQueries({ queryKey: ["frota-solicitacoes"] });

  const saveM = useMutation({
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    mutationFn: (data: any) =>
      editing ? api.solicitacoes.update(editing.id, data) : api.solicitacoes.create(data),
    onSuccess: () => {
      invalidate();
      toast.success(editing ? "Solicitação atualizada." : "Solicitação registrada.");
      closeDialog();
    },
    onError: (e: Error) => setErr(e.message),
  });
  const aprovarM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.aprovar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação aprovada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const cancelarM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.cancelar(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação cancelada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const rejeitarM = useMutation({
    mutationFn: ({ id, justificativa }: { id: number; justificativa: string }) =>
      api.solicitacoes.rejeitar(id, justificativa),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação rejeitada.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const deleteM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.remove(id),
    onSuccess: () => {
      invalidate();
      toast.success("Solicitação excluída.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function set<K extends keyof SolicitacaoForm>(key: K, value: SolicitacaoForm[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function openNew() {
    setEditing(null);
    setForm(EMPTY);
    setErr(null);
    setDialogOpen(true);
  }

  function openEdit(s: SolicitacaoVeiculo) {
    setEditing(s);
    setForm({
      id_unidade_solicitante: s.id_unidade_solicitante,
      finalidade: s.finalidade,
      destino: s.destino,
      data_saida_prevista: s.data_saida_prevista?.slice(0, 16) ?? "",
      data_retorno_prevista: s.data_retorno_prevista?.slice(0, 16) ?? "",
      quantidade_passageiros: s.quantidade_passageiros,
      necessita_motorista: s.necessita_motorista,
      observacoes: s.observacoes ?? "",
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
    const payload = {
      id_unidade_solicitante: form.id_unidade_solicitante ?? null,
      finalidade: form.finalidade.trim(),
      destino: form.destino.trim(),
      data_saida_prevista: form.data_saida_prevista,
      data_retorno_prevista: form.data_retorno_prevista,
      quantidade_passageiros: form.quantidade_passageiros,
      necessita_motorista: form.necessita_motorista,
      observacoes: nullify(form.observacoes),
    };
    saveM.mutate(payload);
  }

  async function onRejeitar(s: SolicitacaoVeiculo) {
    const justificativa = window.prompt("Justificativa da rejeição (obrigatória):", "");
    if (justificativa === null) return;
    if (justificativa.trim() === "") {
      toast.error("A justificativa é obrigatória para rejeitar.");
      return;
    }
    rejeitarM.mutate({ id: s.id, justificativa: justificativa.trim() });
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Solicitações de Veículo"
        description="Pedidos de uso de veículo da frota, com finalidade, destino e datas previstas."
        breadcrumbs={[{ label: "Frota Pública", href: "/frotas" }, { label: "Solicitações" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova solicitação
            </Button>
          ) : undefined
        }
      />

      {!listQ.isLoading && (listQ.data?.length ?? 0) === 0 ? (
        <EmptyState
          icon={Inbox}
          title="Nenhuma solicitação registrada"
          description="Registre a primeira solicitação de uso de veículo."
          action={
            canCreate ? (
              <Button onClick={openNew}>
                <Plus className="mr-1 h-4 w-4" />
                Nova solicitação
              </Button>
            ) : undefined
          }
        />
      ) : (
        <Table>
          <THead>
            <TR>
              <TH>Finalidade</TH>
              <TH>Destino</TH>
              <TH>Saída prevista</TH>
              <TH>Retorno previsto</TH>
              <TH className="text-right">Passag.</TH>
              <TH>Unidade</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listQ.isLoading && (
              <TR>
                <TD colSpan={8} className="text-center text-muted-foreground">
                  Carregando solicitações...
                </TD>
              </TR>
            )}
            {listQ.data?.map((s) => {
              const isSolicitada = s.status === "solicitada";
              const isAprovada = s.status === "aprovada";
              return (
                <TR key={s.id}>
                  <TD className="font-medium">{s.finalidade}</TD>
                  <TD className="text-muted-foreground">{s.destino}</TD>
                  <TD className="tabular-nums">{fmt(s.data_saida_prevista)}</TD>
                  <TD className="tabular-nums">{fmt(s.data_retorno_prevista)}</TD>
                  <TD className="text-right tabular-nums">{s.quantidade_passageiros}</TD>
                  <TD className="text-muted-foreground">{unidadeNome(s.id_unidade_solicitante)}</TD>
                  <TD>
                    <Badge intent={STATUS_INTENT[s.status]}>{STATUS_LABEL[s.status]}</Badge>
                  </TD>
                  <TD className="text-right">
                    <div className="inline-flex flex-wrap justify-end gap-2">
                      {canEdit && isSolicitada && (
                        <Button variant="secondary" size="sm" onClick={() => openEdit(s)}>
                          Editar
                        </Button>
                      )}
                      {canEdit && isSolicitada && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={aprovarM.isPending}
                          onClick={() => aprovarM.mutate(s.id)}
                        >
                          Aprovar
                        </Button>
                      )}
                      {canEdit && isSolicitada && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={rejeitarM.isPending}
                          onClick={() => onRejeitar(s)}
                        >
                          Rejeitar
                        </Button>
                      )}
                      {canEdit && (isSolicitada || isAprovada) && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={cancelarM.isPending}
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Cancelar solicitação",
                              message: `Cancelar a solicitação "${s.finalidade}"?`,
                              confirmLabel: "Cancelar solicitação",
                            });
                            if (ok) cancelarM.mutate(s.id);
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
                              title: "Excluir solicitação",
                              message: "Esta ação não pode ser desfeita. Excluir a solicitação?",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(s.id);
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
        title={editing ? `Editar — ${editing.finalidade}` : "Nova solicitação"}
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
        <div className="space-y-4">
          <SectionCard
            icon={FileText}
            title="Dados da solicitação"
            description="Finalidade, destino e quem é a unidade solicitante."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Label htmlFor="finalidade" required>
                  Finalidade
                </Label>
                <Input
                  id="finalidade"
                  value={form.finalidade}
                  onChange={(e) => set("finalidade", e.target.value)}
                />
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="destino" required>
                  Destino
                </Label>
                <Input id="destino" value={form.destino} onChange={(e) => set("destino", e.target.value)} />
              </div>
              <div>
                <Label htmlFor="unidade">Unidade solicitante</Label>
                <Select
                  id="unidade"
                  value={form.id_unidade_solicitante ?? ""}
                  onChange={(e) =>
                    set("id_unidade_solicitante", e.target.value ? Number(e.target.value) : null)
                  }
                >
                  <option value="">—</option>
                  {unidades.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.unidade_trabalho}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <Label htmlFor="passageiros" required>
                  Qtd. de passageiros
                </Label>
                <Input
                  id="passageiros"
                  type="number"
                  min={1}
                  value={form.quantidade_passageiros}
                  onChange={(e) =>
                    set("quantidade_passageiros", e.target.value ? Number(e.target.value) : 1)
                  }
                />
              </div>
            </div>
          </SectionCard>

          <SectionCard
            icon={MapPin}
            title="Previsão de uso"
            description="Datas/horas previstas de saída e retorno e necessidade de motorista."
          >
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="saida" required>
                  Saída prevista
                </Label>
                <Input
                  id="saida"
                  type="datetime-local"
                  value={form.data_saida_prevista}
                  onChange={(e) => set("data_saida_prevista", e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="retorno" required>
                  Retorno previsto
                </Label>
                <Input
                  id="retorno"
                  type="datetime-local"
                  value={form.data_retorno_prevista}
                  onChange={(e) => set("data_retorno_prevista", e.target.value)}
                />
              </div>
              <div className="flex items-center gap-2 sm:col-span-2">
                <input
                  id="necessita_motorista"
                  type="checkbox"
                  checked={form.necessita_motorista}
                  onChange={(e) => set("necessita_motorista", e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <Label htmlFor="necessita_motorista" className="!mb-0">
                  Necessita motorista
                </Label>
              </div>
              <div className="sm:col-span-2">
                <Label htmlFor="obs">Observações</Label>
                <Textarea
                  id="obs"
                  rows={3}
                  value={form.observacoes}
                  onChange={(e) => set("observacoes", e.target.value)}
                />
              </div>
            </div>
          </SectionCard>

          {err && (
            <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
              {err}
            </div>
          )}
        </div>
      </Dialog>
    </div>
  );
}

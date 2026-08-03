"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Car, ClipboardList, FileText, Gauge, Inbox, MapPin, Plus } from "lucide-react";
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
import {
  api,
  type DesignacaoInput,
  type RegistrarRetornoInput,
  type RegistrarSaidaInput,
  type SolicitacaoStatus,
  type SolicitacaoVeiculo,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATUS_LABEL: Record<SolicitacaoStatus, string> = {
  solicitada: "Solicitada",
  aprovada: "Aprovada",
  rejeitada: "Rejeitada",
  cancelada: "Cancelada",
  em_uso: "Em uso",
  concluida: "Concluída",
};
const STATUS_INTENT: Record<SolicitacaoStatus, "neutral" | "success" | "danger" | "warning"> = {
  solicitada: "warning",
  aprovada: "success",
  rejeitada: "danger",
  cancelada: "neutral",
  em_uso: "warning",
  concluida: "success",
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

interface DesignarForm {
  id_veiculo: number | null;
  id_motorista: number | null;
  observacoes_designacao: string;
}

const DESIGNAR_EMPTY: DesignarForm = {
  id_veiculo: null,
  id_motorista: null,
  observacoes_designacao: "",
};

interface SaidaForm {
  km_saida: string;
  observacoes_saida: string;
}
const SAIDA_EMPTY: SaidaForm = { km_saida: "", observacoes_saida: "" };

interface RetornoForm {
  km_retorno: string;
  observacoes_retorno: string;
}
const RETORNO_EMPTY: RetornoForm = { km_retorno: "", observacoes_retorno: "" };

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

  const [designarOpen, setDesignarOpen] = useState(false);
  const [designarSol, setDesignarSol] = useState<SolicitacaoVeiculo | null>(null);
  const [designarForm, setDesignarForm] = useState<DesignarForm>(DESIGNAR_EMPTY);
  const [designarErr, setDesignarErr] = useState<string | null>(null);

  const [saidaOpen, setSaidaOpen] = useState(false);
  const [saidaSol, setSaidaSol] = useState<SolicitacaoVeiculo | null>(null);
  const [saidaForm, setSaidaForm] = useState<SaidaForm>(SAIDA_EMPTY);
  const [saidaErr, setSaidaErr] = useState<string | null>(null);

  const [retornoOpen, setRetornoOpen] = useState(false);
  const [retornoSol, setRetornoSol] = useState<SolicitacaoVeiculo | null>(null);
  const [retornoForm, setRetornoForm] = useState<RetornoForm>(RETORNO_EMPTY);
  const [retornoErr, setRetornoErr] = useState<string | null>(null);

  const listQ = useQuery({
    queryKey: ["frota-solicitacoes"],
    queryFn: () => api.solicitacoes.listAll(),
  });
  const unidadesQ = useQuery({
    queryKey: ["unidades-all"],
    queryFn: () => api.unidades.list({ page_size: 200 }),
  });
  const veiculosQ = useQuery({ queryKey: ["frota-veiculos"], queryFn: () => api.frota.listAll() });
  const motoristasQ = useQuery({
    queryKey: ["frota-motoristas"],
    queryFn: () => api.motoristas.listAll(),
  });
  const unidades = unidadesQ.data?.items ?? [];
  const veiculos = veiculosQ.data ?? [];
  const motoristas = motoristasQ.data ?? [];
  const unidadeNome = (id: number | null) =>
    unidades.find((u) => u.id === id)?.unidade_trabalho ?? "—";
  const veiculoLabel = (id: number | null) => {
    const v = veiculos.find((x) => x.id === id);
    return v ? [v.placa, v.marca, v.modelo].filter(Boolean).join(" ") : null;
  };
  const motoristaNome = (id: number | null) =>
    motoristas.find((x) => x.id === id)?.nome ?? null;

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
  const designarM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: DesignacaoInput }) =>
      api.solicitacoes.designar(id, data),
    onSuccess: () => {
      invalidate();
      toast.success("Designação registrada.");
      closeDesignar();
    },
    onError: (e: Error) => setDesignarErr(e.message),
  });
  const limparDesignacaoM = useMutation({
    mutationFn: (id: number) => api.solicitacoes.limparDesignacao(id),
    onSuccess: () => {
      invalidate();
      toast.success("Designação removida.");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const registrarSaidaM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegistrarSaidaInput }) =>
      api.solicitacoes.registrarSaida(id, data),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
      toast.success("Saída registrada.");
      closeSaida();
    },
    onError: (e: Error) => setSaidaErr(e.message),
  });
  const registrarRetornoM = useMutation({
    mutationFn: ({ id, data }: { id: number; data: RegistrarRetornoInput }) =>
      api.solicitacoes.registrarRetorno(id, data),
    onSuccess: () => {
      invalidate();
      qc.invalidateQueries({ queryKey: ["frota-veiculos"] });
      toast.success("Retorno registrado.");
      closeRetorno();
    },
    onError: (e: Error) => setRetornoErr(e.message),
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

  function openDesignar(s: SolicitacaoVeiculo) {
    setDesignarSol(s);
    setDesignarForm({
      id_veiculo: s.id_veiculo_designado,
      id_motorista: s.id_motorista_designado,
      observacoes_designacao: s.observacoes_designacao ?? "",
    });
    setDesignarErr(null);
    setDesignarOpen(true);
  }

  function closeDesignar() {
    setDesignarOpen(false);
    setDesignarSol(null);
    setDesignarForm(DESIGNAR_EMPTY);
    setDesignarErr(null);
  }

  function salvarDesignar() {
    setDesignarErr(null);
    if (!designarSol) return;
    if (!designarForm.id_veiculo) {
      setDesignarErr("Selecione um veículo.");
      return;
    }
    if (designarSol.necessita_motorista && !designarForm.id_motorista) {
      setDesignarErr("Esta solicitação exige motorista.");
      return;
    }
    const data: DesignacaoInput = {
      id_veiculo: designarForm.id_veiculo,
      id_motorista: designarForm.id_motorista ?? null,
      observacoes_designacao: nullify(designarForm.observacoes_designacao),
    };
    designarM.mutate({ id: designarSol.id, data });
  }

  function openSaida(s: SolicitacaoVeiculo) {
    setSaidaSol(s);
    setSaidaForm(SAIDA_EMPTY);
    setSaidaErr(null);
    setSaidaOpen(true);
  }

  function closeSaida() {
    setSaidaOpen(false);
    setSaidaSol(null);
    setSaidaForm(SAIDA_EMPTY);
    setSaidaErr(null);
  }

  function salvarSaida() {
    setSaidaErr(null);
    if (!saidaSol) return;
    if (saidaForm.km_saida.trim() === "") {
      setSaidaErr("Informe a quilometragem de saída.");
      return;
    }
    const km = Number(saidaForm.km_saida);
    if (!Number.isFinite(km) || km < 0) {
      setSaidaErr("Quilometragem de saída inválida.");
      return;
    }
    registrarSaidaM.mutate({
      id: saidaSol.id,
      data: { km_saida: km, observacoes_saida: nullify(saidaForm.observacoes_saida) },
    });
  }

  function openRetorno(s: SolicitacaoVeiculo) {
    setRetornoSol(s);
    setRetornoForm(RETORNO_EMPTY);
    setRetornoErr(null);
    setRetornoOpen(true);
  }

  function closeRetorno() {
    setRetornoOpen(false);
    setRetornoSol(null);
    setRetornoForm(RETORNO_EMPTY);
    setRetornoErr(null);
  }

  function salvarRetorno() {
    setRetornoErr(null);
    if (!retornoSol) return;
    if (retornoForm.km_retorno.trim() === "") {
      setRetornoErr("Informe a quilometragem de retorno.");
      return;
    }
    const km = Number(retornoForm.km_retorno);
    if (!Number.isFinite(km) || km < 0) {
      setRetornoErr("Quilometragem de retorno inválida.");
      return;
    }
    if (retornoSol.km_saida != null && km < retornoSol.km_saida) {
      setRetornoErr(`Quilometragem de retorno não pode ser menor que a de saída (${retornoSol.km_saida}).`);
      return;
    }
    registrarRetornoM.mutate({
      id: retornoSol.id,
      data: { km_retorno: km, observacoes_retorno: nullify(retornoForm.observacoes_retorno) },
    });
  }

  const veiculosDisponiveis = veiculos.filter((v) => v.situacao === "disponivel");
  const motoristasAtivos = motoristas.filter((m) => m.situacao === "ativo");

  return (
    <div className="space-y-4">
      <PageHeader
        icon={ClipboardList}
        title="Solicitações de Veículo"
        description="Pedidos de uso de veículo da frota, com finalidade, destino e datas previstas."
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Solicitações" }]}
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
              <TH>Designado</TH>
              <TH>Saída / Retorno</TH>
              <TH>Status</TH>
              <TH className="text-right">Ações</TH>
            </TR>
          </THead>
          <TBody>
            {listQ.isLoading && (
              <TR>
                <TD colSpan={10} className="text-center text-muted-foreground">
                  Carregando solicitações...
                </TD>
              </TR>
            )}
            {listQ.data?.map((s) => {
              const isSolicitada = s.status === "solicitada";
              const isAprovada = s.status === "aprovada";
              const isEmUso = s.status === "em_uso";
              return (
                <TR key={s.id}>
                  <TD className="font-medium">{s.finalidade}</TD>
                  <TD className="text-muted-foreground">{s.destino}</TD>
                  <TD className="tabular-nums">{fmt(s.data_saida_prevista)}</TD>
                  <TD className="tabular-nums">{fmt(s.data_retorno_prevista)}</TD>
                  <TD className="text-right tabular-nums">{s.quantidade_passageiros}</TD>
                  <TD className="text-muted-foreground">{unidadeNome(s.id_unidade_solicitante)}</TD>
                  <TD>
                    {s.id_veiculo_designado ? (
                      <div className="text-xs">
                        <div className="font-medium">
                          {veiculoLabel(s.id_veiculo_designado) ?? `#${s.id_veiculo_designado}`}
                        </div>
                        {s.id_motorista_designado && (
                          <div className="text-muted-foreground">
                            {motoristaNome(s.id_motorista_designado) ?? `#${s.id_motorista_designado}`}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TD>
                  <TD>
                    {s.data_saida_real || s.data_retorno_real ? (
                      <div className="text-xs">
                        {s.data_saida_real && (
                          <div>
                            <span className="text-muted-foreground">Saída: </span>
                            {fmt(s.data_saida_real)}
                            {s.km_saida != null && (
                              <span className="text-muted-foreground"> · {s.km_saida} km</span>
                            )}
                          </div>
                        )}
                        {s.data_retorno_real && (
                          <div>
                            <span className="text-muted-foreground">Retorno: </span>
                            {fmt(s.data_retorno_real)}
                            {s.km_retorno != null && (
                              <span className="text-muted-foreground"> · {s.km_retorno} km</span>
                            )}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TD>
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
                      {canEdit && isAprovada && (
                        <Button variant="secondary" size="sm" onClick={() => openDesignar(s)}>
                          Designar
                        </Button>
                      )}
                      {canEdit && isAprovada && s.id_veiculo_designado && (
                        <Button
                          variant="secondary"
                          size="sm"
                          disabled={limparDesignacaoM.isPending}
                          onClick={async () => {
                            const ok = await confirm({
                              title: "Limpar designação",
                              message: "Remover o veículo/motorista designados desta solicitação?",
                              confirmLabel: "Limpar",
                            });
                            if (ok) limparDesignacaoM.mutate(s.id);
                          }}
                        >
                          Limpar designação
                        </Button>
                      )}
                      {canEdit && isAprovada && s.id_veiculo_designado && (
                        <Button variant="secondary" size="sm" onClick={() => openSaida(s)}>
                          Registrar saída
                        </Button>
                      )}
                      {canEdit && isEmUso && (
                        <Button variant="secondary" size="sm" onClick={() => openRetorno(s)}>
                          Registrar retorno
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

      <Dialog
        open={designarOpen}
        onClose={closeDesignar}
        title={designarSol ? `Designar — ${designarSol.finalidade}` : "Designar"}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={closeDesignar}>
              Cancelar
            </Button>
            <Button onClick={salvarDesignar} disabled={designarM.isPending}>
              {designarM.isPending ? "Salvando..." : "Designar"}
            </Button>
          </>
        }
      >
        <SectionCard
          icon={Car}
          title="Veículo e motorista"
          description="Apenas veículos disponíveis e motoristas ativos podem ser designados."
        >
          <div className="grid grid-cols-1 gap-4">
            <div>
              <Label htmlFor="d_veiculo" required>
                Veículo
              </Label>
              <Select
                id="d_veiculo"
                value={designarForm.id_veiculo ?? ""}
                onChange={(e) =>
                  setDesignarForm((f) => ({
                    ...f,
                    id_veiculo: e.target.value ? Number(e.target.value) : null,
                  }))
                }
              >
                <option value="">—</option>
                {veiculosDisponiveis.map((v) => (
                  <option key={v.id} value={v.id}>
                    {[v.placa, v.marca, v.modelo].filter(Boolean).join(" ")}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="d_motorista" required={designarSol?.necessita_motorista}>
                Motorista
                {designarSol?.necessita_motorista ? " (obrigatório)" : " (opcional)"}
              </Label>
              <Select
                id="d_motorista"
                value={designarForm.id_motorista ?? ""}
                onChange={(e) =>
                  setDesignarForm((f) => ({
                    ...f,
                    id_motorista: e.target.value ? Number(e.target.value) : null,
                  }))
                }
              >
                <option value="">—</option>
                {motoristasAtivos.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <Label htmlFor="d_obs">Observações da designação</Label>
              <Textarea
                id="d_obs"
                rows={2}
                value={designarForm.observacoes_designacao}
                onChange={(e) =>
                  setDesignarForm((f) => ({ ...f, observacoes_designacao: e.target.value }))
                }
              />
            </div>
            {designarErr && (
              <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
                {designarErr}
              </div>
            )}
          </div>
        </SectionCard>
      </Dialog>

      <Dialog
        open={saidaOpen}
        onClose={closeSaida}
        title={saidaSol ? `Registrar saída — ${saidaSol.finalidade}` : "Registrar saída"}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={closeSaida}>
              Cancelar
            </Button>
            <Button onClick={salvarSaida} disabled={registrarSaidaM.isPending}>
              {registrarSaidaM.isPending ? "Salvando..." : "Registrar saída"}
            </Button>
          </>
        }
      >
        <SectionCard
          icon={Gauge}
          title="Saída do veículo"
          description="A data/hora da saída é registrada automaticamente. A quilometragem deve ser maior ou igual à atual do veículo."
        >
          <div className="grid grid-cols-1 gap-4">
            <div>
              <Label htmlFor="km_saida" required>
                Quilometragem de saída
              </Label>
              <Input
                id="km_saida"
                type="number"
                min={0}
                value={saidaForm.km_saida}
                onChange={(e) => setSaidaForm((f) => ({ ...f, km_saida: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="obs_saida">Observações da saída</Label>
              <Textarea
                id="obs_saida"
                rows={2}
                value={saidaForm.observacoes_saida}
                onChange={(e) =>
                  setSaidaForm((f) => ({ ...f, observacoes_saida: e.target.value }))
                }
              />
            </div>
            {saidaErr && (
              <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
                {saidaErr}
              </div>
            )}
          </div>
        </SectionCard>
      </Dialog>

      <Dialog
        open={retornoOpen}
        onClose={closeRetorno}
        title={retornoSol ? `Registrar retorno — ${retornoSol.finalidade}` : "Registrar retorno"}
        size="md"
        footer={
          <>
            <Button variant="secondary" onClick={closeRetorno}>
              Cancelar
            </Button>
            <Button onClick={salvarRetorno} disabled={registrarRetornoM.isPending}>
              {registrarRetornoM.isPending ? "Salvando..." : "Registrar retorno"}
            </Button>
          </>
        }
      >
        <SectionCard
          icon={Gauge}
          title="Retorno do veículo"
          description="A data/hora do retorno é registrada automaticamente. A quilometragem de retorno atualiza a do veículo e deve ser maior ou igual à de saída."
        >
          <div className="grid grid-cols-1 gap-4">
            {retornoSol?.km_saida != null && (
              <p className="text-sm text-muted-foreground">
                Quilometragem de saída registrada: <strong>{retornoSol.km_saida} km</strong>.
              </p>
            )}
            <div>
              <Label htmlFor="km_retorno" required>
                Quilometragem de retorno
              </Label>
              <Input
                id="km_retorno"
                type="number"
                min={retornoSol?.km_saida ?? 0}
                value={retornoForm.km_retorno}
                onChange={(e) => setRetornoForm((f) => ({ ...f, km_retorno: e.target.value }))}
              />
            </div>
            <div>
              <Label htmlFor="obs_retorno">Observações do retorno</Label>
              <Textarea
                id="obs_retorno"
                rows={2}
                value={retornoForm.observacoes_retorno}
                onChange={(e) =>
                  setRetornoForm((f) => ({ ...f, observacoes_retorno: e.target.value }))
                }
              />
            </div>
            {retornoErr && (
              <div role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger-soft-foreground">
                {retornoErr}
              </div>
            )}
          </div>
        </SectionCard>
      </Dialog>
    </div>
  );
}

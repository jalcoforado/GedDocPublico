"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertOctagon,
  Ban,
  CheckCircle2,
  Inbox,
  Pencil,
  Play,
  Plus,
  SearchX,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";

import { hojeLocal, rotuloVeiculo, useErrosDoFormulario } from "@/components/frota/formulario";
import { fmtData } from "@/components/pagamentos/format";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
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
// Quatro gravidades: à vista no formulário, cada uma com o que quer dizer —
// "média" sozinha não diz a ninguém quando usar.
const GRAVIDADES_ESCOLHA: OpcaoEscolha<OcorrenciaGravidade>[] = [
  { valor: "baixa", rotulo: "Baixa", descricao: "Não atrapalha o uso do veículo." },
  { valor: "media", rotulo: "Média", descricao: "Precisa de atenção, mas o veículo segue rodando." },
  { valor: "alta", rotulo: "Alta", descricao: "Compromete o uso: resolver logo." },
  { valor: "critica", rotulo: "Crítica", descricao: "Risco ou veículo parado: resolver já. Entra no alerta de críticas abertas." },
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
// Mesma régua de cor das demais telas da Frota (ver components/frota/rotulos.ts).
const STATUS_INTENT: Record<string, "info" | "neutral" | "success" | "warning"> = {
  aberta: "warning",
  em_tratamento: "info",
  resolvida: "success",
  cancelada: "neutral",
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
  const campos = useErrosDoFormulario({
    veiculo: !editing && form.id_veiculo == null ? "Escolha o veículo." : undefined,
    descricao: form.descricao.trim() ? undefined : "Conte o que aconteceu.",
  });
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
    setForm({ ...EMPTY, data_ocorrencia: hojeLocal() });
    setErr(null);
    campos.limpar();
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
    campos.limpar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
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

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard
          label="Abertas"
          value={cards.abertas}
          hint="aberta ou em tratamento"
          icon={AlertOctagon}
          intent={cards.abertas > 0 ? "warning" : "default"}
        />
        <KpiCard
          label="Críticas abertas"
          value={cards.criticas}
          icon={ShieldAlert}
          intent={cards.criticas > 0 ? "danger" : "default"}
        />
        <KpiCard label="Resolvidas" value={cards.resolvidas} icon={CheckCircle2} intent="success" />
      </div>

      <FilterBar>
        <FilterBar.Group label="Status">
          <Select aria-label="Status" value={statusFiltro} onChange={(e) => setStatusFiltro(e.target.value)}>
            <option value="">Todos</option>
            {STATUS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        {statusFiltro !== "" && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={() => setStatusFiltro("")}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!listaQ.isLoading && (listaQ.data?.length ?? 0) === 0 && statusFiltro !== "" ? (
        <EmptyState
          icon={SearchX}
          title="Nenhuma ocorrência encontrada"
          description="Nenhuma ocorrência está com o status escolhido."
          action={
            <Button variant="secondary" onClick={() => setStatusFiltro("")}>
              Limpar filtros
            </Button>
          }
        />
      ) : !listaQ.isLoading && (listaQ.data?.length ?? 0) === 0 ? (
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
                    {/* O próximo passo fica à vista (Tratar, depois Resolver); o
                        resto vai para o ⋯. */}
                    <AcoesDaLinha
                      acoes={[
                        {
                          label: "Tratar",
                          icon: Play,
                          oculta: !(canEdit && o.status === "aberta"),
                          onClick: () => actionM.mutate({ id: o.id, acao: "iniciar" }),
                        },
                        {
                          label: "Resolver",
                          icon: CheckCircle2,
                          oculta: !(canEdit && tratavel),
                          onClick: () => {
                            setResolvendo(o);
                            setResForm({ data_resolucao: hojeLocal(), providencias: o.providencias ?? "" });
                          },
                        },
                        {
                          label: "Editar",
                          icon: Pencil,
                          oculta: !(canEdit && tratavel),
                          onClick: () => openEdit(o),
                        },
                        {
                          label: "Cancelar",
                          icon: Ban,
                          perigo: true,
                          oculta: !(canEdit && tratavel),
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Cancelar ocorrência",
                              message: "Cancelar esta ocorrência?",
                              confirmLabel: "Cancelar ocorrência",
                            });
                            if (ok) actionM.mutate({ id: o.id, acao: "cancelar" });
                          },
                        },
                        {
                          label: "Excluir",
                          icon: Trash2,
                          perigo: true,
                          oculta: !canDelete,
                          disabled: deleteM.isPending,
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Excluir ocorrência",
                              message: "Excluir esta ocorrência? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(o.id);
                          },
                        },
                      ]}
                    />
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
        description={
          editing
            ? `${placaDe.get(editing.id_veiculo) ?? `Veículo #${editing.id_veiculo}`} · ${fmtData(editing.data_ocorrencia)}`
            : "Avaria, multa, sinistro ou outro fato com um veículo da frota."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-ocorrencia" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Registrar ocorrência"}
            </Button>
          </>
        }
      >
        <form
          id="form-ocorrencia"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            salvar();
          }}
        >
          {!editing && (
            <FormField label="Veículo" required error={campos.erro("veiculo")}>
              <Select
                id="veiculo"
                value={form.id_veiculo ?? ""}
                onChange={(e) => set("id_veiculo", e.target.value ? Number(e.target.value) : null)}
                onBlur={campos.tocar("veiculo")}
              >
                <option value="">Selecione o veículo</option>
                {(veiculosQ.data ?? []).map((v) => (
                  <option key={v.id} value={v.id}>
                    {rotuloVeiculo(v)}
                  </option>
                ))}
              </Select>
            </FormField>
          )}
          <GradeCampos>
            <FormField label="Tipo" required>
              <Select id="tipo" value={form.tipo} onChange={(e) => set("tipo", e.target.value as OcorrenciaTipo)}>
                {TIPOS.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField
              label="Data"
              hint={!editing && form.data_ocorrencia === hojeLocal() ? "Já vem com a data de hoje." : "Quando aconteceu."}
            >
              <Input
                id="data"
                type="date"
                value={form.data_ocorrencia}
                onChange={(e) => set("data_ocorrencia", e.target.value)}
              />
            </FormField>
          </GradeCampos>
          <EscolhaSegmentada
            nome="gravidade"
            titulo="Gravidade"
            moldura={false}
            valor={form.gravidade}
            opcoes={GRAVIDADES_ESCOLHA}
            onChange={(g) => set("gravidade", g)}
          />
          <FormField label="O que aconteceu" required error={campos.erro("descricao")}>
            <Textarea
              id="descricao"
              rows={3}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
              onBlur={campos.tocar("descricao")}
              placeholder="Ex.: Retrovisor direito quebrado ao manobrar no pátio da Secretaria"
            />
          </FormField>
          <FormField label="Motorista envolvido" opcional>
            <Select
              id="motorista"
              value={form.id_motorista ?? ""}
              onChange={(e) => set("id_motorista", e.target.value ? Number(e.target.value) : null)}
            >
              <option value="">Nenhum ou não se sabe</option>
              {(motoristasQ.data ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.nome}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label="Providências" opcional hint="O que já foi feito ou está combinado.">
            <Textarea
              id="prov"
              rows={2}
              value={form.providencias}
              onChange={(e) => set("providencias", e.target.value)}
              placeholder="Ex.: Orçamento pedido à oficina; boletim de ocorrência registrado"
            />
          </FormField>
          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      </Dialog>

      <Dialog
        open={resolvendo != null}
        onClose={() => setResolvendo(null)}
        title="Resolver ocorrência"
        description={
          resolvendo
            ? `${placaDe.get(resolvendo.id_veiculo) ?? `Veículo #${resolvendo.id_veiculo}`} · ${TIPO_LABEL[resolvendo.tipo] ?? resolvendo.tipo} · ${resolvendo.descricao}`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setResolvendo(null)}>
              Cancelar
            </Button>
            <Button type="submit" form="form-resolver" loading={resolverM.isPending}>
              Marcar como resolvida
            </Button>
          </>
        }
      >
        <form
          id="form-resolver"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            resolver();
          }}
        >
          <FormField label="Data de resolução" hint="Já vem com a data de hoje.">
            <Input
              id="r_data"
              type="date"
              value={resForm.data_resolucao}
              onChange={(e) => setResForm((f) => ({ ...f, data_resolucao: e.target.value }))}
            />
          </FormField>
          <FormField label="Providências" opcional hint="Como foi resolvida — fica no histórico do veículo.">
            <Textarea
              id="r_prov"
              rows={3}
              value={resForm.providencias}
              onChange={(e) => setResForm((f) => ({ ...f, providencias: e.target.value }))}
              placeholder="Ex.: Retrovisor trocado na oficina; multa paga e recurso arquivado"
            />
          </FormField>
        </form>
      </Dialog>
    </div>
  );
}

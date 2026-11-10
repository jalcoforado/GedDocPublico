"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Ban, CheckCircle2, Inbox, Pencil, Play, Plus, SearchX, Trash2, Wrench } from "lucide-react";
import { useMemo, useState } from "react";

import { hojeLocal, numeroOuNulo, rotuloVeiculo, useErrosDoFormulario } from "@/components/frota/formulario";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { EscolhaSegmentada, type OpcaoEscolha } from "@/components/ui/escolha-segmentada";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
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
// Mesma régua de cor das demais telas da Frota (ver components/frota/rotulos.ts).
const STATUS_INTENT: Record<string, "neutral" | "info" | "success" | "warning"> = {
  aberta: "warning",
  em_andamento: "info",
  concluida: "success",
  cancelada: "neutral",
};
const TIPO_LABEL: Record<string, string> = Object.fromEntries(TIPOS.map((t) => [t.value, t.label]));

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

// Dois tipos: à vista, com o que cada um quer dizer.
const TIPOS_ESCOLHA: OpcaoEscolha<ManutencaoTipo>[] = [
  { valor: "preventiva", rotulo: "Preventiva", descricao: "Revisão programada: óleo, filtros, pneus, alinhamento." },
  { valor: "corretiva", rotulo: "Corretiva", descricao: "Conserto de um defeito ou de uma avaria." },
];

const KM_INTEIRO = "Use só números inteiros, sem ponto nem vírgula.";

/** Km opcional digitado como texto: vazio passa; senão, inteiro ≥ 0. */
function erroInteiroOpcional(v: string): string | undefined {
  if (v.trim() === "") return undefined;
  const n = Number(v);
  return Number.isInteger(n) && n >= 0 ? undefined : KM_INTEIRO;
}

/** Valor opcional digitado como texto: vazio passa; senão, ≥ 0. */
function erroValorOpcional(v: string): string | undefined {
  if (v.trim() === "") return undefined;
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? undefined : "Informe um valor de zero para cima.";
}

// Mesmas exigências do backend: veículo e descrição na abertura; km inteiro
// e custo não negativo quando preenchidos.
function validar(form: ManutForm, novo: boolean): Record<string, string | undefined> {
  return {
    veiculo: novo && form.id_veiculo == null ? "Escolha o veículo." : undefined,
    descricao: form.descricao.trim() ? undefined : "Descreva o serviço a fazer.",
    km_atual:
      form.km_atual != null && (!Number.isInteger(form.km_atual) || form.km_atual < 0)
        ? KM_INTEIRO
        : undefined,
    custo_estimado:
      form.custo_estimado != null && form.custo_estimado < 0
        ? "Informe um valor de zero para cima."
        : undefined,
  };
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
  const campos = useErrosDoFormulario(validar(form, editing == null));
  const camposConcluir = useErrosDoFormulario({
    c_km: erroInteiroOpcional(concForm.km_atual),
    c_custo: erroValorOpcional(concForm.custo_final),
  });

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
  const temFiltroAtivo = statusFiltro !== "" || tipoFiltro !== "";
  function limparFiltros() {
    setStatusFiltro("");
    setTipoFiltro("");
  }

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
    campos.limpar();
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
    if (!camposConcluir.podeEnviar()) return;
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
        breadcrumbs={[{ label: "Frota Pública", href: "/m/frota" }, { label: "Manutenções" }]}
        actions={
          canCreate ? (
            <Button onClick={openNew}>
              <Plus className="mr-1 h-4 w-4" />
              Nova manutenção
            </Button>
          ) : undefined
        }
      />

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
        <FilterBar.Group label="Tipo">
          <Select aria-label="Tipo" value={tipoFiltro} onChange={(e) => setTipoFiltro(e.target.value)}>
            <option value="">Todos</option>
            {TIPOS.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </Select>
        </FilterBar.Group>
        {temFiltroAtivo && (
          <FilterBar.Actions>
            <Button variant="ghost" onClick={limparFiltros}>
              Limpar
            </Button>
          </FilterBar.Actions>
        )}
      </FilterBar>

      {!manutQ.isLoading && linhas.length === 0 && temFiltroAtivo ? (
        <EmptyState
          icon={SearchX}
          title="Nenhuma manutenção encontrada"
          description="Nenhuma manutenção corresponde aos filtros aplicados."
          action={
            <Button variant="secondary" onClick={limparFiltros}>
              Limpar filtros
            </Button>
          }
        />
      ) : !manutQ.isLoading && linhas.length === 0 ? (
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
                  <TD>{TIPO_LABEL[m.tipo] ?? m.tipo}</TD>
                  <TD className="max-w-[20rem] truncate" title={m.descricao}>
                    {m.descricao}
                  </TD>
                  <TD className="tabular-nums">{fmtData(m.data_abertura)}</TD>
                  <TD>
                    <Badge intent={STATUS_INTENT[m.status] ?? "neutral"}>
                      {STATUS_LABEL[m.status] ?? m.status}
                    </Badge>
                  </TD>
                  <TD className="text-right tabular-nums">
                    {m.custo_final != null ? fmtMoeda(m.custo_final) : "—"}
                  </TD>
                  <TD className="text-right">
                    {/* O próximo passo fica à vista (Iniciar, depois Concluir); o
                        resto vai para o ⋯. */}
                    <AcoesDaLinha
                      acoes={[
                        {
                          label: "Iniciar",
                          icon: Play,
                          oculta: !(canEdit && aberta),
                          onClick: () => actionM.mutate({ id: m.id, acao: "iniciar" }),
                        },
                        {
                          label: "Concluir",
                          icon: CheckCircle2,
                          oculta: !(canEdit && encerravel),
                          onClick: () => {
                            setConcluindo(m);
                            setConcForm({ data_conclusao: hojeLocal(), custo_final: "", km_atual: "" });
                            camposConcluir.limpar();
                          },
                        },
                        {
                          label: "Editar",
                          icon: Pencil,
                          oculta: !(canEdit && encerravel),
                          onClick: () => openEdit(m),
                        },
                        {
                          label: "Cancelar",
                          icon: Ban,
                          perigo: true,
                          oculta: !(canEdit && encerravel),
                          onClick: async () => {
                            const ok = await confirm({
                              title: "Cancelar manutenção",
                              message: "Cancelar esta manutenção?",
                              confirmLabel: "Cancelar manutenção",
                            });
                            if (ok) actionM.mutate({ id: m.id, acao: "cancelar" });
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
                              title: "Excluir manutenção",
                              message: "Excluir este registro de manutenção? Esta ação não pode ser desfeita.",
                              confirmLabel: "Excluir",
                              intent: "danger",
                            });
                            if (ok) deleteM.mutate(m.id);
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
        title={editing ? "Editar manutenção" : "Nova manutenção"}
        description={
          editing
            ? (placaDe.get(editing.id_veiculo) ?? `Veículo #${editing.id_veiculo}`)
            : "Ao abrir, um veículo disponível passa para a situação Manutenção."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-manutencao" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Abrir manutenção"}
            </Button>
          </>
        }
      >
        <form
          id="form-manutencao"
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
          <EscolhaSegmentada
            nome="tipo_manutencao"
            titulo="Tipo"
            moldura={false}
            valor={form.tipo}
            opcoes={TIPOS_ESCOLHA}
            onChange={(t) => set("tipo", t)}
          />
          <FormField label="O que será feito" required error={campos.erro("descricao")}>
            <Textarea
              id="descricao"
              rows={2}
              value={form.descricao}
              onChange={(e) => set("descricao", e.target.value)}
              onBlur={campos.tocar("descricao")}
              placeholder={
                form.tipo === "preventiva"
                  ? "Ex.: Revisão dos 30.000 km — óleo, filtros e alinhamento"
                  : "Ex.: Embreagem patinando; trocar o kit"
              }
            />
          </FormField>
          <GradeCampos>
            <FormField label="Data prevista" opcional hint="Quando o serviço deve ficar pronto.">
              <Input
                id="data_prevista"
                type="date"
                value={form.data_prevista}
                onChange={(e) => set("data_prevista", e.target.value)}
              />
            </FormField>
            <FormField label="Quilometragem" opcional hint="O que marca o painel na entrada." error={campos.erro("km_atual")}>
              <CampoComUnidade
                id="km_atual"
                type="number"
                inputMode="numeric"
                min={0}
                sufixo="km"
                value={form.km_atual ?? ""}
                onChange={(e) => set("km_atual", numeroOuNulo(e.target.value))}
                onBlur={campos.tocar("km_atual")}
              />
            </FormField>
          </GradeCampos>
          <GradeCampos>
            <FormField label="Oficina ou fornecedor" opcional>
              <Input
                id="fornecedor"
                value={form.fornecedor}
                onChange={(e) => set("fornecedor", e.target.value)}
                placeholder="Ex.: Auto Center Silva"
                maxLength={150}
              />
            </FormField>
            <FormField
              label="Custo estimado"
              opcional
              hint="O do orçamento. O custo final é informado ao concluir."
              error={campos.erro("custo_estimado")}
            >
              <CampoComUnidade
                id="custo_estimado"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                prefixo="R$"
                value={form.custo_estimado ?? ""}
                onChange={(e) => set("custo_estimado", numeroOuNulo(e.target.value))}
                onBlur={campos.tocar("custo_estimado")}
                placeholder="Ex.: 850"
              />
            </FormField>
          </GradeCampos>
          <FormField label="Observações" opcional>
            <Textarea
              id="obs"
              rows={2}
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Ex.: orçamento nº 552 anexado ao processo"
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
        open={concluindo != null}
        onClose={() => setConcluindo(null)}
        title="Concluir manutenção"
        description={
          concluindo
            ? `${placaDe.get(concluindo.id_veiculo) ?? `Veículo #${concluindo.id_veiculo}`} · ${concluindo.descricao}`
            : undefined
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setConcluindo(null)}>
              Cancelar
            </Button>
            <Button type="submit" form="form-concluir" loading={concluirM.isPending}>
              Concluir manutenção
            </Button>
          </>
        }
      >
        <form
          id="form-concluir"
          noValidate
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            concluir();
          }}
        >
          <p className="text-sm text-foreground-muted">
            O veículo volta a ficar disponível. Quilometragem e custo podem ficar em branco.
          </p>
          <GradeCampos>
            <FormField label="Data de conclusão" hint="Já vem com a data de hoje.">
              <Input
                id="c_data"
                type="date"
                value={concForm.data_conclusao}
                onChange={(e) => setConcForm((f) => ({ ...f, data_conclusao: e.target.value }))}
              />
            </FormField>
            <FormField label="Quilometragem" hint="O que marca o painel na saída da oficina." error={camposConcluir.erro("c_km")}>
              <CampoComUnidade
                id="c_km"
                type="number"
                inputMode="numeric"
                min={0}
                sufixo="km"
                value={concForm.km_atual}
                onChange={(e) => setConcForm((f) => ({ ...f, km_atual: e.target.value }))}
                onBlur={camposConcluir.tocar("c_km")}
              />
            </FormField>
          </GradeCampos>
          <FormField
            label="Custo final"
            hint={
              concluindo?.custo_estimado != null
                ? `Estimado na abertura: ${fmtMoeda(concluindo.custo_estimado)}.`
                : "O valor da nota do serviço."
            }
            error={camposConcluir.erro("c_custo")}
          >
            <CampoComUnidade
              id="c_custo"
              type="number"
              inputMode="decimal"
              min={0}
              step="0.01"
              prefixo="R$"
              value={concForm.custo_final}
              onChange={(e) => setConcForm((f) => ({ ...f, custo_final: e.target.value }))}
              onBlur={camposConcluir.tocar("c_custo")}
            />
          </FormField>
        </form>
      </Dialog>
    </div>
  );
}

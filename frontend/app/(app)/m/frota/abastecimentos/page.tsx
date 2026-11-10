"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Calculator, Droplets, Fuel, Inbox, Pencil, Plus, Trash2, Wallet } from "lucide-react";
import { useMemo, useState } from "react";

import { fmtKm, hojeLocal, numeroOuNulo, rotuloVeiculo, useErrosDoFormulario } from "@/components/frota/formulario";
import { COMBUSTIVEIS, fmtLitros } from "@/components/frota/rotulos";
import { fmtData, fmtMoeda } from "@/components/pagamentos/format";
import { AcoesDaLinha } from "@/components/ui/acoes-da-linha";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CampoComUnidade } from "@/components/ui/campo-com-unidade";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { FormField, GradeCampos } from "@/components/ui/form-field";
import { Input } from "@/components/ui/input";
import { KpiCard } from "@/components/ui/kpi-card";
import { PageHeader } from "@/components/ui/page-header";
import { Select } from "@/components/ui/select";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import { api, type VeiculoAbastecimento } from "@/lib/api";
import { useAuth } from "@/lib/auth";

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

// Mesmas exigências do backend (veículo na criação; km ≥ 0 inteiro; litros
// > 0; valor ≥ 0), cada uma sob o seu campo.
function validar(form: AbastForm, novo: boolean): Record<string, string | undefined> {
  return {
    veiculo: novo && form.id_veiculo == null ? "Escolha o veículo." : undefined,
    km:
      form.km_atual == null
        ? "Informe a quilometragem do painel."
        : !Number.isInteger(form.km_atual) || form.km_atual < 0
          ? "Use só números inteiros, sem ponto nem vírgula."
          : undefined,
    litros:
      form.litros == null
        ? "Informe quantos litros foram abastecidos."
        : form.litros <= 0
          ? "Os litros precisam ser maiores que zero."
          : undefined,
    valor:
      form.valor_total == null
        ? "Informe o valor pago."
        : form.valor_total < 0
          ? "O valor não pode ser negativo."
          : undefined,
  };
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
  // O combustível foi preenchido pelo cadastro do veículo (e não por quem digita)?
  const [combustivelDoVeiculo, setCombustivelDoVeiculo] = useState(false);
  const campos = useErrosDoFormulario(validar(form, editing == null));

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
    setForm({ ...EMPTY, data_abastecimento: hojeLocal() });
    setErr(null);
    setCombustivelDoVeiculo(false);
    campos.limpar();
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
    setCombustivelDoVeiculo(false);
    campos.limpar();
    setDialogOpen(true);
  }
  function closeDialog() {
    setDialogOpen(false);
    setEditing(null);
    setForm(EMPTY);
  }
  function escolherVeiculo(id: number | null) {
    set("id_veiculo", id);
    // O combustível do cadastro do veículo é o palpite certo — menos para flex
    // e híbrido, em que quem abastece escolhe na bomba.
    const doVeiculo = (veiculosQ.data ?? []).find((x) => x.id === id)?.tipo_combustivel ?? "";
    const definido = doVeiculo !== "" && doVeiculo !== "flex" && doVeiculo !== "hibrido";
    if (form.tipo_combustivel === "" || combustivelDoVeiculo) {
      set("tipo_combustivel", definido ? doVeiculo : "");
      setCombustivelDoVeiculo(definido);
    }
  }
  function salvar() {
    setErr(null);
    if (!campos.podeEnviar()) return;
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

  const kmVeiculo = editing
    ? null
    : ((veiculosQ.data ?? []).find((x) => x.id === form.id_veiculo)?.quilometragem_atual ?? null);
  // R$/litro ao vivo: confere o cupom antes de salvar (um zero a mais nos
  // litros aparece como um preço absurdo).
  const precoLitro =
    form.litros != null && form.litros > 0 && form.valor_total != null && form.valor_total > 0
      ? form.valor_total / form.litros
      : null;

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
        <KpiCard
          label="Abastecimentos"
          value={r?.total_abastecimentos ?? 0}
          icon={Fuel}
          hint={r?.ultimo_abastecimento ? `Último em ${fmtData(r.ultimo_abastecimento)}` : undefined}
        />
        <KpiCard label="Litros (total)" value={fmtLitros(r?.total_litros ?? 0)} icon={Droplets} />
        <KpiCard label="Custo total" value={fmtMoeda(r?.total_valor ?? 0)} icon={Wallet} />
        <KpiCard
          label="Média por litro"
          value={r?.media_valor_litro != null ? fmtMoeda(r.media_valor_litro) : "—"}
          icon={Calculator}
        />
      </div>

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
                <TD className="text-right tabular-nums">{fmtLitros(a.litros)}</TD>
                <TD className="text-right tabular-nums">{fmtMoeda(a.valor_total)}</TD>
                <TD className="text-muted-foreground">{a.posto ?? "—"}</TD>
                <TD className="text-right">
                  <AcoesDaLinha
                    acoes={[
                      {
                        label: "Editar",
                        icon: Pencil,
                        oculta: !canEdit,
                        onClick: () => openEdit(a),
                      },
                      {
                        label: "Excluir",
                        icon: Trash2,
                        perigo: true,
                        oculta: !canDelete,
                        disabled: deleteM.isPending,
                        onClick: async () => {
                          const ok = await confirm({
                            title: "Excluir abastecimento",
                            message: "Excluir este abastecimento? Esta ação não pode ser desfeita.",
                            confirmLabel: "Excluir",
                            intent: "danger",
                          });
                          if (ok) deleteM.mutate(a.id);
                        },
                      },
                    ]}
                  />
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
        description={
          editing
            ? `${placaDe.get(editing.id_veiculo) ?? `Veículo #${editing.id_veiculo}`} · ${fmtData(editing.data_abastecimento)}`
            : "Os dados do cupom do posto."
        }
        size="lg"
        footer={
          <>
            <Button variant="ghost" onClick={closeDialog}>
              Cancelar
            </Button>
            <Button type="submit" form="form-abastecimento" loading={saveM.isPending}>
              {editing ? "Salvar alterações" : "Registrar abastecimento"}
            </Button>
          </>
        }
      >
        <form
          id="form-abastecimento"
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
                onChange={(e) => escolherVeiculo(e.target.value ? Number(e.target.value) : null)}
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
            <FormField
              label="Data"
              hint={!editing && form.data_abastecimento === hojeLocal() ? "Já vem com a data de hoje." : undefined}
            >
              <Input
                id="data"
                type="date"
                value={form.data_abastecimento}
                onChange={(e) => set("data_abastecimento", e.target.value)}
              />
            </FormField>
            <FormField label="Motorista" opcional hint="Quem abasteceu.">
              <Select
                id="motorista"
                value={form.id_motorista ?? ""}
                onChange={(e) => set("id_motorista", e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">Não informado</option>
                {(motoristasQ.data ?? []).map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.nome}
                  </option>
                ))}
              </Select>
            </FormField>
          </GradeCampos>
          <GradeCampos>
            <FormField
              label="Quilometragem"
              required
              hint={
                kmVeiculo != null
                  ? `O que marca o painel. Último registro do veículo: ${fmtKm(kmVeiculo)}.`
                  : "O que marca o painel no abastecimento."
              }
              error={campos.erro("km")}
            >
              <CampoComUnidade
                id="km"
                type="number"
                inputMode="numeric"
                min={0}
                sufixo="km"
                value={form.km_atual ?? ""}
                onChange={(e) => set("km_atual", numeroOuNulo(e.target.value))}
                onBlur={campos.tocar("km")}
              />
            </FormField>
            <FormField
              label="Combustível"
              opcional
              hint={combustivelDoVeiculo ? "Veio do cadastro do veículo; troque se for outro." : undefined}
            >
              <Select
                id="combustivel"
                value={form.tipo_combustivel}
                onChange={(e) => {
                  setCombustivelDoVeiculo(false);
                  set("tipo_combustivel", e.target.value);
                }}
              >
                <option value="">Não informado</option>
                {COMBUSTIVEIS.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </Select>
            </FormField>
          </GradeCampos>
          <GradeCampos>
            <FormField label="Litros" required error={campos.erro("litros")}>
              <CampoComUnidade
                id="litros"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.001"
                sufixo="L"
                value={form.litros ?? ""}
                onChange={(e) => set("litros", numeroOuNulo(e.target.value))}
                onBlur={campos.tocar("litros")}
                placeholder="Ex.: 40"
              />
            </FormField>
            <FormField
              label="Valor total"
              required
              hint={precoLitro != null ? `${fmtMoeda(precoLitro)} por litro.` : "O total pago, do cupom."}
              error={campos.erro("valor")}
            >
              <CampoComUnidade
                id="valor"
                type="number"
                inputMode="decimal"
                min={0}
                step="0.01"
                prefixo="R$"
                value={form.valor_total ?? ""}
                onChange={(e) => set("valor_total", numeroOuNulo(e.target.value))}
                onBlur={campos.tocar("valor")}
                placeholder="Ex.: 250"
              />
            </FormField>
          </GradeCampos>
          <FormField label="Posto" opcional>
            <Input
              id="posto"
              value={form.posto}
              onChange={(e) => set("posto", e.target.value)}
              placeholder="Ex.: Posto Central"
              maxLength={150}
            />
          </FormField>
          <FormField label="Observações" opcional>
            <Textarea
              id="obs"
              rows={2}
              value={form.observacoes}
              onChange={(e) => set("observacoes", e.target.value)}
              placeholder="Ex.: nota fiscal nº 1234"
            />
          </FormField>
          {err && (
            <Alert intent="danger" title="Não foi possível salvar">
              {err}
            </Alert>
          )}
        </form>
      </Dialog>
    </div>
  );
}
